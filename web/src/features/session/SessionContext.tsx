"use client";

// The one store for the conversation: which mode we're in, the messages, the
// seller-bot session (stage, strategy, coaching) and the prospect session.
// Features read it with useSession(). Pure history helpers live in ./history.ts.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { BotState, ChatMsg, Difficulty, Outcome, Persona, ProspectPick, ProspectState, Training } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { useStoredState } from "@/lib/useStoredState";
import { useToast } from "@/components/ui";
import { fromHistory, newId, nextIndex, parseSettings, type ChatMessage, type ProspectSettings } from "./history";

export type { ChatMessage, ProspectSettings };

/** "seller" mode: the bot sells, the learner is the buyer. "prospect" mode: the learner sells. */
export type Mode = "seller" | "prospect";
/** The learner's seat. Each has its own page, so the address says which one you are in. */
export type LearnerRole = "buyer" | "seller";

export interface ProspectSession {
  sessionId: string;
  persona: Persona;
  state: ProspectState;
  difficulty: Difficulty;
  productType: string;
  /** What the learner picked in setup, so "play again" keeps the same buyer and objection. */
  pick: ProspectPick;
  maxTurns: number | null;
  scoringEnabled: boolean;
  ended: boolean;
  outcome: Outcome;
  hint: string;
}

interface SendResult {
  ok: boolean;
  /** Text to put back in the input when the message was rolled back. */
  restore?: string;
}

interface SessionValue {
  role: LearnerRole;
  mode: Mode;
  ready: boolean;
  sessionId: string | null;
  stage: string;
  strategy: string;
  training: Training | null;
  messages: ChatMessage[];
  typing: boolean;
  /** True once the server said the stage/strategy controls are allowed. */
  flowControls: boolean;
  prospect: ProspectSession | null;
  prospectSettings: ProspectSettings;
  setProspectSettings: (s: ProspectSettings) => void;
  send: (text: string) => Promise<SendResult>;
  edit: (historyIndex: number, text: string) => Promise<boolean>;
  reset: () => Promise<void>;
  /** Apply a stage/strategy change made by the flow controls. */
  applyBotState: (s: Partial<BotState> & { training?: Training }) => void;
  startProspect: (difficulty: Difficulty, productType: string, pick?: ProspectPick) => Promise<boolean>;
  /** End the current buyer and go back to setup. */
  exitProspect: () => void;
  /** Called when a prospect request reports the session is gone. */
  handleExpired: (err: unknown) => boolean;
}

const SessionContext = createContext<SessionValue | null>(null);

const debugOn = () => {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(location.search).get("debug") === "1" || readString(storageKeys.debug) === "1";
};

const metaLine = (latency: number | null | undefined, provider?: string) =>
  debugOn() && latency != null ? `${Math.round(latency)}ms · ${provider ?? "?"}` : undefined;

export function SessionProvider({ children, role }: { children: ReactNode; role: LearnerRole }) {
  const toast = useToast();
  const mode: Mode = role === "seller" ? "prospect" : "seller";
  // The selling page has nothing to load before setup, so it is ready at once.
  const [ready, setReady] = useState(role === "seller");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [bot, setBot] = useState<BotState>({ stage: "intent", strategy: "-" as BotState["strategy"] });
  const [training, setTraining] = useState<Training | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [typing, setTyping] = useState(false);
  const [flowControls, setFlowControls] = useState(false);
  const [prospect, setProspect] = useState<ProspectSession | null>(null);
  const [prospectSettings, setProspectSettings] = useStoredState<ProspectSettings>(
    storageKeys.prospectSettings,
    { showHints: true, evalDisplay: "inline" },
    parseSettings,
  );
  const recovering = useRef(false);
  /** True while a send or edit is in flight; blocks a second one before React re-renders. */
  const busy = useRef(false);
  /** Bumped whenever the conversation is replaced, so late replies from the old one are dropped. */
  const epoch = useRef(0);
  const started = useRef(false);

  const adopt = useCallback((res: { session_id: string; message: string | null; history: ChatMsg[]; training?: Training } & BotState) => {
    setSessionId(res.session_id);
    writeString(storageKeys.sessionId, res.session_id);
    setBot({ stage: res.stage, strategy: res.strategy });
    setTraining(res.training ?? null);
    const history = res.history?.length ? res.history : res.message ? [{ role: "assistant" as const, content: res.message }] : [];
    setMessages(fromHistory(history, config.historyCap));
  }, []);

  /** Start or restore a seller-bot session. Retries once without the saved id. */
  const initSeller = useCallback(
    async (useSaved = true) => {
      const saved = useSaved ? readString(storageKeys.sessionId) : null;
      // Try the saved session first; if the server refuses it, start a fresh one.
      for (const id of saved ? [saved, null] : [null]) {
        try {
          adopt(await api.init(id));
          break;
        } catch (err) {
          // Only a refused id is thrown away; a network blip keeps it for the next try.
          if (id && err instanceof ApiError && err.status === 400) {
            writeString(storageKeys.sessionId, null);
            continue;
          }
          toast(err instanceof ApiError ? err.message : "Connection error. Refresh the page.", "error");
        }
      }
      setReady(true);
    },
    [adopt, toast],
  );

  useEffect(() => {
    // The selling page starts at setup: no bot session, and no stage controls to unlock.
    if (role !== "buyer") return;
    if (started.current) return; // StrictMode mounts twice in dev; connect once.
    started.current = true;
    // Mount-time connect to the server; state is set after the request resolves.
    initSeller();
    api
      .publicConfig()
      .then((c) => setFlowControls(c.features.flow_controls_enabled))
      .catch(() => setFlowControls(false));
  }, [initSeller, role]);

  const handleExpired = useCallback(
    (err: unknown) => {
      if (!(err instanceof ApiError) || !err.sessionExpired || recovering.current) return false;
      recovering.current = true;
      if (mode === "prospect") {
        setProspect(null);
        setMessages([]);
        toast("Prospect session expired. Start a new one.", "error");
        recovering.current = false;
      } else {
        toast("Session expired. Reconnecting…", "info");
        writeString(storageKeys.sessionId, null);
        initSeller(false).finally(() => (recovering.current = false));
      }
      return true;
    },
    [mode, toast, initSeller],
  );

  const send = useCallback(
    async (text: string): Promise<SendResult> => {
      const message = text.trim();
      // The selling seat has no one to talk to until a buyer is set up.
      if (!message || busy.current || (mode === "prospect" && !prospect)) return { ok: false };
      if (message.length > config.maxMessageLength) {
        toast(`Keep it under ${config.maxMessageLength} characters.`, "error");
        return { ok: false, restore: text };
      }
      busy.current = true;
      const my = epoch.current;
      const optimisticId = newId();
      const before = nextIndex(messages);
      setMessages((m) => [...m, { id: optimisticId, role: "user", content: message, historyIndex: before }]);
      setTyping(true);
      try {
        if (mode === "prospect" && prospect) {
          const res = await api.prospectChat(prospect.sessionId, message, prospectSettings.showHints);
          if (epoch.current !== my) return { ok: true };
          setMessages((m) => [...m, { id: newId(), role: "assistant", content: res.message, historyIndex: before + 1, meta: metaLine(res.latency_ms, res.provider) }]);
          setProspect((p) =>
            p && { ...p, state: res.state, ended: res.ended, outcome: res.outcome, hint: res.coaching?.hint ?? p.hint },
          );
        } else {
          if (!sessionId) throw new ApiError("No active session", 400, "SESSION_EXPIRED");
          const res = await api.chat(sessionId, message);
          if (epoch.current !== my) return { ok: true };
          setMessages((m) => [...m, { id: newId(), role: "assistant", content: res.message, historyIndex: before + 1, meta: metaLine(res.latency_ms, res.provider) }]);
          setBot({ stage: res.stage, strategy: res.strategy });
          setTraining(res.training);
        }
        return { ok: true };
      } catch (err) {
        if (epoch.current !== my) return { ok: false };
        if (handleExpired(err)) return { ok: false, restore: message };
        // The server may have accepted the message before failing; check before rolling back.
        if (mode === "seller" && sessionId) {
          try {
            const server = await api.init(sessionId);
            if (server.history.length > before + 1) {
              adopt(server);
              toast("Recovered the latest server state.", "info");
              return { ok: true };
            }
          } catch {
            /* fall through to rollback */
          }
        }
        setMessages((m) => m.filter((x) => x.id !== optimisticId));
        toast(err instanceof ApiError ? err.message : "Message failed. Try again.", "error");
        return { ok: false, restore: message };
      } finally {
        busy.current = false;
        setTyping(false);
      }
    },
    [messages, mode, prospect, prospectSettings.showHints, sessionId, handleExpired, adopt, toast],
  );

  const edit = useCallback(
    async (historyIndex: number, text: string) => {
      const message = text.trim();
      if (mode !== "seller" || !sessionId || !message || busy.current) return false;
      busy.current = true;
      const my = epoch.current;
      const affected = new Set(
        messages.filter((x) => x.role !== "divider" && !x.historical && x.historyIndex >= historyIndex).map((x) => x.id),
      );
      const grey = (on: boolean) => setMessages((m) => m.map((x) => (affected.has(x.id) ? { ...x, historical: on } : x)));
      grey(true);
      setTyping(true);
      try {
        const res = await api.edit(sessionId, historyIndex, message);
        if (epoch.current !== my) return false;
        setMessages((m) => [
          ...m,
          { id: newId(), role: "divider", content: "Edited", historyIndex: -1 },
          ...fromHistory(res.history.slice(historyIndex), config.historyCap, historyIndex),
        ]);
        setBot({ stage: res.stage, strategy: res.strategy });
        setTraining(res.training);
        return true;
      } catch (err) {
        if (handleExpired(err)) return false;
        grey(false);
        toast(err instanceof ApiError ? `Edit failed: ${err.message}` : "Edit didn't go through. Try again.", "error");
        return false;
      } finally {
        busy.current = false;
        setTyping(false);
      }
    },
    [mode, messages, sessionId, handleExpired, toast],
  );

  const startProspect = useCallback(
    async (difficulty: Difficulty, productType: string, pick: ProspectPick = {}) => {
      // Block sends while the buyer loads; a message sent now would be wiped when it arrives.
      epoch.current++;
      setTyping(true);
      try {
        const res = await api.prospectInit(difficulty, productType, pick);
        if (prospect) api.prospectReset(prospect.sessionId).catch(() => {});
        setProspect({
          sessionId: res.session_id,
          persona: res.persona,
          state: res.state,
          difficulty: res.difficulty,
          productType: res.product_type,
          pick,
          maxTurns: res.max_turns,
          scoringEnabled: res.scoring_enabled,
          ended: false,
          outcome: "active",
          hint: "",
        });
        setMessages([{ id: newId(), role: "assistant", content: res.message, historyIndex: 0, meta: metaLine(res.latency_ms, res.provider) }]);
        return true;
      } catch (err) {
        toast(err instanceof ApiError ? err.message : "Couldn't start prospect practice.", "error");
        return false;
      } finally {
        setTyping(false);
      }
    },
    [prospect, toast],
  );

  const exitProspect = useCallback(() => {
    if (prospect) api.prospectReset(prospect.sessionId).catch(() => {});
    setProspect(null);
    setMessages([]);
    epoch.current++;
  }, [prospect]);

  const reset = useCallback(async () => {
    if (mode === "prospect" && prospect) {
      await startProspect(prospect.difficulty, prospect.productType, prospect.pick);
      return;
    }
    try {
      if (sessionId) await api.reset(sessionId);
    } catch (err) {
      if (!handleExpired(err)) {
        toast("Reset didn't stick. Try one more time.", "error");
        return;
      }
    }
    writeString(storageKeys.sessionId, null);
    epoch.current++;
    setMessages([]);
    setBot({ stage: "intent", strategy: "-" as BotState["strategy"] });
    setTraining(null);
    setTyping(true);
    await initSeller(false);
    setTyping(false);
  }, [mode, prospect, sessionId, startProspect, handleExpired, toast, initSeller]);

  const applyBotState = useCallback((s: Partial<BotState> & { training?: Training }) => {
    setBot((b) => ({ stage: s.stage ?? b.stage, strategy: s.strategy ?? b.strategy }));
    if (s.training) setTraining(s.training);
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      role,
      mode,
      ready,
      sessionId,
      stage: mode === "prospect" ? "default" : bot.stage,
      strategy: mode === "prospect" ? "prospect" : bot.strategy,
      training,
      messages,
      typing,
      flowControls,
      prospect,
      prospectSettings,
      setProspectSettings,
      send,
      edit,
      reset,
      applyBotState,
      startProspect,
      exitProspect,
      handleExpired,
    }),
    [role, mode, ready, sessionId, bot, training, messages, typing, flowControls, prospect, prospectSettings, setProspectSettings, send, edit, reset, applyBotState, startProspect, exitProspect, handleExpired],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
