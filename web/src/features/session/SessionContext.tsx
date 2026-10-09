"use client";

// The one store for the conversation: which mode we're in, the messages, the
// buy-mode session (stage, coaching) and the sell-mode session.
// Features read it with useSession(). Pure history helpers live in ./history.ts.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, errorText } from "@/lib/api/client";
import type { BotState, BuyerPick, BuyerState, ChatMsg, CoachNotes, Difficulty, Outcome, Persona } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { useStoredState } from "@/lib/useStoredState";
import { useToast } from "@/components/ui";
import { fromHistory, newId, nextIndex, parseSettings, type ChatMessage, type SellSettings } from "./history";

export type { ChatMessage, SellSettings };

/**
 * What the learner does. "buy": the learner is the customer and the AI seller sells to them.
 * "sell": the learner is the salesperson and the AI buyer answers. Each has its own page.
 */
export type Mode = "buy" | "sell";

/** A live AI buyer in sell mode. */
export interface SellSession {
  sessionId: string;
  persona: Persona;
  state: BuyerState;
  difficulty: Difficulty;
  productType: string;
  /** What the learner picked in setup, so "play again" keeps the same buyer and objection. */
  pick: BuyerPick;
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
  mode: Mode;
  /** Sell mode keeps its own id in sellSession. */
  buySessionId: string | null;
  /** Buy-mode script stage; the sidebar stage card shows it. */
  stage: string;
  /** Buy-mode coach notes for the latest turn (wire key "training"). */
  coachNotes: CoachNotes | null;
  messages: ChatMessage[];
  typing: boolean;
  /** The AI buyer in sell mode; null until the learner sets one up. */
  sellSession: SellSession | null;
  sellSettings: SellSettings;
  setSellSettings: (s: SellSettings) => void;
  send: (text: string) => Promise<SendResult>;
  edit: (historyIndex: number, text: string) => Promise<boolean>;
  reset: () => Promise<void>;
  /** Start a new AI buyer (sell mode). */
  startBuyer: (difficulty: Difficulty, productType: string, pick?: BuyerPick) => Promise<boolean>;
  /** End the current buyer and go back to setup. */
  endBuyer: () => void;
  /** Called when a request reports the session is gone. */
  handleExpired: (err: unknown) => boolean;
}

const SessionContext = createContext<SessionValue | null>(null);

/** Every buy-mode script starts here (first stage in core/enums.py Stage). */
const FIRST_STAGE = "intent";

const debugOn = () => {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(location.search).get("debug") === "1" || readString(storageKeys.debug) === "1";
};

const metaLine = (latency: number | null | undefined, provider?: string) =>
  debugOn() && latency != null ? `${Math.round(latency)}ms · ${provider ?? "?"}` : undefined;

export function SessionProvider({ children, mode }: { children: ReactNode; mode: Mode }) {
  const toast = useToast();
  const [buySessionId, setBuySessionId] = useState<string | null>(null);
  const [stage, setStage] = useState(FIRST_STAGE);
  const [coachNotes, setCoachNotes] = useState<CoachNotes | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [typing, setTyping] = useState(false);
  const [sellSession, setSellSession] = useState<SellSession | null>(null);
  const [sellSettings, setSellSettings] = useStoredState<SellSettings>(
    storageKeys.sellSettings,
    { showHints: true, evalDisplay: "inline" },
    parseSettings,
  );
  const recovering = useRef(false);
  /** True while a send or edit is in flight; blocks a second one before React re-renders. */
  const busy = useRef(false);
  /** Bumped whenever the conversation is replaced, so late replies from the old one are dropped. */
  const epoch = useRef(0);
  const started = useRef(false);

  const adopt = useCallback((res: { session_id: string; message: string | null; history: ChatMsg[]; training?: CoachNotes } & BotState) => {
    setBuySessionId(res.session_id);
    writeString(storageKeys.buySessionId, res.session_id);
    setStage(res.stage);
    setCoachNotes(res.training ?? null);
    const history = res.history?.length ? res.history : res.message ? [{ role: "assistant" as const, content: res.message }] : [];
    setMessages(fromHistory(history, config.historyCap));
  }, []);

  /** Start or restore a buy-mode session. Retries once without the saved id. */
  const initBuy = useCallback(
    async (useSaved = true) => {
      const saved = useSaved ? readString(storageKeys.buySessionId) : null;
      for (const id of saved ? [saved, null] : [null]) {
        try {
          adopt(await api.buyInit(id));
          break;
        } catch (err) {
          // 400 = the server refused the saved id (expired or unknown): drop it and start fresh.
          // A network blip keeps it for the next try.
          if (id && err instanceof ApiError && err.status === 400) {
            writeString(storageKeys.buySessionId, null);
            continue;
          }
          toast(errorText(err, "Connection error. Refresh the page."), "error");
        }
      }
    },
    [adopt, toast],
  );

  useEffect(() => {
    // Sell mode starts at buyer setup: there is no session to connect to yet.
    if (mode !== "buy") return;
    if (started.current) return; // StrictMode mounts twice in dev; connect once.
    started.current = true;
    initBuy();
  }, [initBuy, mode]);

  const handleExpired = useCallback(
    (err: unknown) => {
      if (!(err instanceof ApiError) || !err.sessionExpired || recovering.current) return false;
      recovering.current = true;
      if (mode === "sell") {
        setSellSession(null);
        setMessages([]);
        toast("Your buyer timed out. Set up a new one.", "error");
        recovering.current = false;
      } else {
        toast("Session expired. Reconnecting…", "info");
        writeString(storageKeys.buySessionId, null);
        initBuy(false).finally(() => (recovering.current = false));
      }
      return true;
    },
    [mode, toast, initBuy],
  );

  const send = useCallback(
    async (text: string): Promise<SendResult> => {
      const message = text.trim();
      // In sell mode there is no one to talk to until a buyer is set up.
      if (!message || busy.current || (mode === "sell" && !sellSession)) return { ok: false };
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
        if (mode === "sell" && sellSession) {
          const res = await api.sellChat(sellSession.sessionId, message, sellSettings.showHints);
          if (epoch.current !== my) return { ok: true };
          setMessages((m) => [...m, { id: newId(), role: "assistant", content: res.message, historyIndex: before + 1, meta: metaLine(res.latency_ms, res.provider) }]);
          setSellSession((p) =>
            p && { ...p, state: res.state, ended: res.ended, outcome: res.outcome, hint: res.coaching?.hint ?? p.hint },
          );
        } else {
          // No session yet (connect failed): reuse the expired path so handleExpired reconnects.
          if (!buySessionId) throw new ApiError("No active session", 400, "SESSION_EXPIRED");
          const res = await api.buyChat(buySessionId, message);
          if (epoch.current !== my) return { ok: true };
          setMessages((m) => [...m, { id: newId(), role: "assistant", content: res.message, historyIndex: before + 1, meta: metaLine(res.latency_ms, res.provider) }]);
          setStage(res.stage);
          setCoachNotes(res.training);
        }
        return { ok: true };
      } catch (err) {
        if (epoch.current !== my) return { ok: false };
        if (handleExpired(err)) return { ok: false, restore: message };
        // The server may have accepted the message before failing; check before rolling back.
        if (mode === "buy" && buySessionId) {
          try {
            const server = await api.buyInit(buySessionId);
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
        toast(errorText(err, "Message failed. Try again."), "error");
        return { ok: false, restore: message };
      } finally {
        busy.current = false;
        setTyping(false);
      }
    },
    [messages, mode, sellSession, sellSettings.showHints, buySessionId, handleExpired, adopt, toast],
  );

  const edit = useCallback(
    async (historyIndex: number, text: string) => {
      const message = text.trim();
      if (mode !== "buy" || !buySessionId || !message || busy.current) return false;
      busy.current = true;
      const my = epoch.current;
      const affected = new Set(
        messages.filter((x) => x.role !== "divider" && !x.historical && x.historyIndex >= historyIndex).map((x) => x.id),
      );
      const grey = (on: boolean) => setMessages((m) => m.map((x) => (affected.has(x.id) ? { ...x, historical: on } : x)));
      grey(true);
      setTyping(true);
      try {
        const res = await api.buyEdit(buySessionId, historyIndex, message);
        if (epoch.current !== my) return false;
        setMessages((m) => [
          ...m,
          { id: newId(), role: "divider", content: "Edited", historyIndex: -1 },
          ...fromHistory(res.history.slice(historyIndex), config.historyCap, historyIndex),
        ]);
        setStage(res.stage);
        setCoachNotes(res.training);
        return true;
      } catch (err) {
        if (handleExpired(err)) return false;
        grey(false);
        toast(`Edit failed: ${errorText(err, "try again.")}`, "error");
        return false;
      } finally {
        busy.current = false;
        setTyping(false);
      }
    },
    [mode, messages, buySessionId, handleExpired, toast],
  );

  const startBuyer = useCallback(
    async (difficulty: Difficulty, productType: string, pick: BuyerPick = {}) => {
      // Block sends while the buyer loads; a message sent now would be wiped when it arrives.
      epoch.current++;
      setTyping(true);
      try {
        const res = await api.sellInit(difficulty, productType, pick);
        if (sellSession) api.sellReset(sellSession.sessionId).catch(() => {});
        setSellSession({
          sessionId: res.session_id,
          persona: res.persona,
          state: res.state,
          difficulty: res.difficulty,
          productType: res.product_type,
          pick,
          ended: false,
          outcome: "active",
          hint: "",
        });
        setMessages([{ id: newId(), role: "assistant", content: res.message, historyIndex: 0, meta: metaLine(res.latency_ms, res.provider) }]);
        return true;
      } catch (err) {
        toast(errorText(err, "Couldn't start your buyer."), "error");
        return false;
      } finally {
        setTyping(false);
      }
    },
    [sellSession, toast],
  );

  const endBuyer = useCallback(() => {
    if (sellSession) api.sellReset(sellSession.sessionId).catch(() => {});
    setSellSession(null);
    setMessages([]);
    epoch.current++;
  }, [sellSession]);

  const reset = useCallback(async () => {
    if (mode === "sell" && sellSession) {
      await startBuyer(sellSession.difficulty, sellSession.productType, sellSession.pick);
      return;
    }
    try {
      if (buySessionId) await api.buyReset(buySessionId);
    } catch (err) {
      if (!handleExpired(err)) {
        toast("Reset didn't stick. Try one more time.", "error");
        return;
      }
    }
    writeString(storageKeys.buySessionId, null);
    epoch.current++;
    setMessages([]);
    setStage(FIRST_STAGE);
    setCoachNotes(null);
    setTyping(true);
    await initBuy(false);
    setTyping(false);
  }, [mode, sellSession, buySessionId, startBuyer, handleExpired, toast, initBuy]);

  const value = useMemo<SessionValue>(
    () => ({
      mode,
      buySessionId,
      stage,
      coachNotes,
      messages,
      typing,
      sellSession,
      sellSettings,
      setSellSettings,
      send,
      edit,
      reset,
      startBuyer,
      endBuyer,
      handleExpired,
    }),
    [mode, buySessionId, stage, coachNotes, messages, typing, sellSession, sellSettings, setSellSettings, send, edit, reset, startBuyer, endBuyer, handleExpired],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
