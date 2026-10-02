"use client";

// The one store for the conversation: which mode we're in, the messages, the
// seller-bot session (stage, strategy, coaching) and the prospect session.
// Features read it with useSession(); only this file talks to the chat endpoints.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { BotState, ChatMsg, Difficulty, Outcome, Persona, ProspectState, Training } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { useStoredState } from "@/lib/useStoredState";
import { useToast } from "@/components/ui";

export type Mode = "seller" | "prospect";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "divider";
  content: string;
  /** Position in the server's history; used by edit. -1 for dividers. */
  historyIndex: number;
  /** Debug line (latency · provider), shown only with ?debug=1. */
  meta?: string;
  /** Greyed out: replaced by an edit. */
  historical?: boolean;
}

export interface ProspectSession {
  sessionId: string;
  persona: Persona;
  state: ProspectState;
  difficulty: Difficulty;
  productType: string;
  maxTurns: number | null;
  scoringEnabled: boolean;
  ended: boolean;
  outcome: Outcome;
  hint: string;
}

export interface ProspectSettings {
  showHints: boolean;
  evalDisplay: "inline" | "modal" | "panel";
}

interface SendResult {
  ok: boolean;
  /** Text to put back in the input when the message was rolled back. */
  restore?: string;
}

interface SessionValue {
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
  startProspect: (difficulty: Difficulty, productType: string) => Promise<boolean>;
  exitProspect: () => Promise<void>;
  /** Called when a prospect request reports the session is gone. */
  handleExpired: (err: unknown) => boolean;
}

const SessionContext = createContext<SessionValue | null>(null);

let seq = 0;
const newId = () => `m${Date.now().toString(36)}${(seq++).toString(36)}`;

const debugOn = () => {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(location.search).get("debug") === "1" || readString(storageKeys.debug) === "1";
};

const metaLine = (latency: number | null | undefined, provider?: string) =>
  debugOn() && latency != null ? `${Math.round(latency)}ms · ${provider ?? "?"}` : undefined;

function fromHistory(history: ChatMsg[], offset = 0): ChatMessage[] {
  return history.slice(-config.historyCap).map((m, i) => ({ id: newId(), role: m.role, content: m.content, historyIndex: offset + i }));
}

const liveCount = (msgs: ChatMessage[]) => msgs.filter((m) => m.role !== "divider" && !m.historical).length;

const parseSettings = (raw: string): ProspectSettings | undefined => {
  try {
    const v = JSON.parse(raw);
    return { showHints: v.showHints !== false, evalDisplay: ["inline", "modal", "panel"].includes(v.evalDisplay) ? v.evalDisplay : "inline" };
  } catch {
    return undefined;
  }
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [mode, setMode] = useState<Mode>("seller");
  const [ready, setReady] = useState(false);
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

  const adopt = useCallback((res: { session_id: string; message: string | null; history: ChatMsg[]; training?: Training } & BotState) => {
    setSessionId(res.session_id);
    writeString(storageKeys.sessionId, res.session_id);
    setBot({ stage: res.stage, strategy: res.strategy });
    setTraining(res.training ?? null);
    const history = res.history?.length ? res.history : res.message ? [{ role: "assistant" as const, content: res.message }] : [];
    setMessages(fromHistory(history));
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
          if (id) {
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
    // Mount-time connect to the server; state is set after the request resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    initSeller();
    api
      .publicConfig()
      .then((c) => setFlowControls(c.features.flow_controls_enabled))
      .catch(() => setFlowControls(false));
  }, [initSeller]);

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
      if (!message || typing) return { ok: false };
      if (message.length > config.maxMessageLength) {
        toast(`Keep it under ${config.maxMessageLength} characters.`, "error");
        return { ok: false, restore: text };
      }
      const optimisticId = newId();
      const before = liveCount(messages);
      setMessages((m) => [...m, { id: optimisticId, role: "user", content: message, historyIndex: before }]);
      setTyping(true);
      try {
        if (mode === "prospect" && prospect) {
          const res = await api.prospectChat(prospect.sessionId, message, prospectSettings.showHints);
          setMessages((m) => [...m, { id: newId(), role: "assistant", content: res.message, historyIndex: before + 1, meta: metaLine(res.latency_ms, res.provider) }]);
          setProspect((p) =>
            p && { ...p, state: res.state, ended: res.ended, outcome: res.outcome, hint: res.coaching?.hint ?? p.hint },
          );
        } else {
          if (!sessionId) throw new ApiError("No active session", 400, "SESSION_EXPIRED");
          const res = await api.chat(sessionId, message);
          setMessages((m) => [...m, { id: newId(), role: "assistant", content: res.message, historyIndex: before + 1, meta: metaLine(res.latency_ms, res.provider) }]);
          setBot({ stage: res.stage, strategy: res.strategy });
          setTraining(res.training);
        }
        return { ok: true };
      } catch (err) {
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
        setTyping(false);
      }
    },
    [messages, typing, mode, prospect, prospectSettings.showHints, sessionId, handleExpired, adopt, toast],
  );

  const edit = useCallback(
    async (historyIndex: number, text: string) => {
      const message = text.trim();
      if (!sessionId || !message) return false;
      const affected = new Set(
        messages.filter((x) => x.role !== "divider" && !x.historical && x.historyIndex >= historyIndex).map((x) => x.id),
      );
      const grey = (on: boolean) => setMessages((m) => m.map((x) => (affected.has(x.id) ? { ...x, historical: on } : x)));
      grey(true);
      setTyping(true);
      try {
        const res = await api.edit(sessionId, historyIndex, message);
        setMessages((m) => [
          ...m,
          { id: newId(), role: "divider", content: "Edited", historyIndex: -1 },
          ...fromHistory(res.history.slice(historyIndex), historyIndex),
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
        setTyping(false);
      }
    },
    [messages, sessionId, handleExpired, toast],
  );

  const startProspect = useCallback(
    async (difficulty: Difficulty, productType: string) => {
      try {
        const res = await api.prospectInit(difficulty, productType);
        if (prospect) api.prospectReset(prospect.sessionId).catch(() => {});
        setProspect({
          sessionId: res.session_id,
          persona: res.persona,
          state: res.state,
          difficulty: res.difficulty,
          productType: res.product_type,
          maxTurns: res.max_turns,
          scoringEnabled: res.scoring_enabled,
          ended: false,
          outcome: "active",
          hint: "",
        });
        setMessages([{ id: newId(), role: "assistant", content: res.message, historyIndex: 0, meta: metaLine(res.latency_ms, res.provider) }]);
        setMode("prospect");
        return true;
      } catch (err) {
        toast(err instanceof ApiError ? err.message : "Couldn't start prospect practice.", "error");
        return false;
      }
    },
    [prospect, toast],
  );

  const exitProspect = useCallback(async () => {
    if (prospect) api.prospectReset(prospect.sessionId).catch(() => {});
    setProspect(null);
    setMode("seller");
    setMessages([]);
    writeString(storageKeys.sessionId, null);
    await initSeller(false);
  }, [prospect, initSeller]);

  const reset = useCallback(async () => {
    if (mode === "prospect" && prospect) {
      await startProspect(prospect.difficulty, prospect.productType);
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
    setMessages([]);
    setBot({ stage: "intent", strategy: "-" as BotState["strategy"] });
    setTraining(null);
    await initSeller(false);
  }, [mode, prospect, sessionId, startProspect, handleExpired, toast, initSeller]);

  const applyBotState = useCallback((s: Partial<BotState> & { training?: Training }) => {
    setBot((b) => ({ stage: s.stage ?? b.stage, strategy: s.strategy ?? b.strategy }));
    if (s.training) setTraining(s.training);
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
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
    [mode, ready, sessionId, bot, training, messages, typing, flowControls, prospect, prospectSettings, setProspectSettings, send, edit, reset, applyBotState, startProspect, exitProspect, handleExpired],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
