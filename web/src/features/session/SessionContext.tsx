"use client";

// The one store for the conversation: which mode we're in, the messages, the
// buy-mode session (stage, coaching) and the sell-mode session.
// Features read it with useSession(). Pure history helpers live in ./history.ts.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, errorText } from "@/lib/api/client";
import type { BotState, BuyerPick, BuyerState, ChatMsg, CoachNotes, Difficulty, Outcome, Persona, WordsChoice } from "@/lib/api/types";
import { useAccount } from "@/features/account/AccountContext";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { useStoredState } from "@/lib/useStoredState";
import { useToast } from "@/components/ui";
import { fromHistory, newId, nextIndex, parseSettings, type ChatMessage, type SellSettings } from "./history";
import { readLocalKnowledge } from "@/features/knowledge/knowledgeStore";

export type { ChatMessage };

/**
 * What the learner does. "buy": the learner is the customer and the AI seller sells to them.
 * "sell": the learner is the salesperson and the AI buyer answers. Each has its own page.
 */
export type Mode = "buy" | "sell";

/** Buy mode: the questions new calls ask in someone else's words (the Rep's words tool): the tab's own choice, or
 *  the team's (a manager set them) when the tab made none. */
export interface RepWords extends WordsChoice {
  /** These are the team's words, not this tab's own choice. */
  team?: boolean;
}

/** Stored in place of words when the learner chose the script's own: it beats the team's words for this tab. */
const SCRIPT_WORDS = "none";

/** This tab's choice: someone's words, the script's own (SCRIPT_WORDS), or null when it made none. */
type TabChoice = WordsChoice | typeof SCRIPT_WORDS | null;

function savedRepWords(): TabChoice {
  const raw = readString(storageKeys.buyWords, "session");
  if (raw === SCRIPT_WORDS) return SCRIPT_WORDS;
  try {
    const v = JSON.parse(raw ?? "null");
    if (!v || typeof v.product !== "string" || typeof v.label !== "string" || !v.words || typeof v.words !== "object") return null;
    return { product: v.product, label: v.label, words: v.words, probes: v.probes && typeof v.probes === "object" ? v.probes : {} };
  } catch {
    return null;
  }
}

const saveRepWords = (c: TabChoice) =>
  writeString(
    storageKeys.buyWords,
    c === SCRIPT_WORDS ? SCRIPT_WORDS : c ? JSON.stringify({ product: c.product, label: c.label, words: c.words, probes: c.probes }) : null,
    "session",
  );

/** The words a new call uses: the tab's own choice when it was matched for `product`, else the team's for that
 *  product (any product when the tab has not picked one: the call then sells the team's). */
function wordsFor(product: string | null, team: WordsChoice | null): RepWords | undefined {
  const own = savedRepWords();
  if (own === SCRIPT_WORDS) return undefined;
  if (own) return own.product === product ? own : undefined;
  return team && (product === null || team.product === product) ? { ...team, team: true } : undefined;
}

const sameWords = (a: Record<string, string>, b: Record<string, string>) =>
  Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([k, v]) => b[k] === v);

/** A live AI buyer in sell mode. */
export interface SellSession {
  sessionId: string;
  persona: Persona;
  state: BuyerState;
  difficulty: Difficulty;
  productType: string;
  /** What the learner picked in setup, so "play again" keeps the same buyer and objection (or the buyer from a real call, from the same point in it). */
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
  /** Buy mode: what the rep sells on this call (an id from /api/buy/products); null until the call starts. */
  buyProduct: string | null;
  /** Buy mode: the rep's words this call uses, or null for the script's own. */
  repWords: RepWords | null;
  /** Buy mode: start a fresh call in these words (null: the script's own, even when the team has words); later new
   *  calls in this tab keep them. */
  chooseRepWords: (w: WordsChoice | null) => Promise<void>;
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
  /** A new call in place of this one; false when the old one could not be ended. */
  reset: () => Promise<boolean>;
  /** Buy mode: start a fresh call where the rep sells this product (it stays picked for later calls). */
  switchProduct: (productType: string) => Promise<void>;
  /** Buy mode: start a fresh call at one script step (nothing said before it). */
  jumpTo: (step: string) => Promise<void>;
  /** Start a new AI buyer (sell mode). */
  startBuyer: (difficulty: Difficulty, productType: string, pick?: BuyerPick) => Promise<boolean>;
  /** End the current buyer and go back to setup. */
  endBuyer: () => void;
  /** Sell mode: the call was ended and scored ("End and score"): the box locks until a new buyer or a redo. */
  markSellEnded: (outcome: Outcome) => void;
  /** Sell mode: take the chat from the server again (after a redo rewrote it). */
  refreshSell: () => Promise<void>;
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

/** The live sell call in this tab (sessionStorage), so a reload or Back picks it up instead of losing it. */
const saveSellCall = (id: string | null, pick: BuyerPick = {}) =>
  writeString(storageKeys.sellCall, id ? JSON.stringify({ id, pick }) : null, "session");

function savedSellCall(): { id: string; pick: BuyerPick } | null {
  try {
    const saved = JSON.parse(readString(storageKeys.sellCall, "session") ?? "null");
    return saved && typeof saved.id === "string" ? { id: saved.id, pick: saved.pick ?? {} } : null;
  } catch {
    return null;
  }
}

const metaLine = (latency: number | null | undefined, provider?: string) =>
  debugOn() && latency != null ? `${Math.round(latency)}ms · ${provider ?? "?"}` : undefined;

export function SessionProvider({ children, mode }: { children: ReactNode; mode: Mode }) {
  const toast = useToast();
  // A member's new calls use the team's words, so a buy call waits for the first account answer.
  const { ready: accountReady, team } = useAccount();
  const teamWords = team?.words ?? null;
  const [buySessionId, setBuySessionId] = useState<string | null>(null);
  const [buyProduct, setBuyProduct] = useState<string | null>(null);
  const [stage, setStage] = useState(FIRST_STAGE);
  const [coachNotes, setCoachNotes] = useState<CoachNotes | null>(null);
  const [repWords, setRepWords] = useState<RepWords | null>(null);
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

  const adopt = useCallback((res: { session_id: string; message: string | null; history: ChatMsg[]; training?: CoachNotes; product_type?: string; words?: Record<string, string>; words_label?: string; probes?: Record<string, string> } & BotState) => {
    setBuySessionId(res.session_id);
    if (res.product_type) setBuyProduct(res.product_type);
    // The server says which words this call uses (a jump keeps the call's, so it sends none). The tab takes them
    // on, so its next call matches what the card shows (another tab may have started this one). The team's words
    // stay the team's: the tab has not chosen them, so a manager's change reaches its next call.
    if (res.words) {
      const own = savedRepWords();
      if (Object.keys(res.words).length) {
        const ownLabel = own && own !== SCRIPT_WORDS ? own.label : "";
        const got: WordsChoice = {
          product: res.product_type ?? "",
          label: res.words_label || ownLabel || "a top rep",
          words: res.words,
          probes: res.probes ?? {},
        };
        const team = own === null && !!teamWords && teamWords.label === got.label && sameWords(teamWords.words, got.words);
        if (!team) saveRepWords(got);
        setRepWords({ ...got, team });
      } else {
        setRepWords(null);
        if (own && own !== SCRIPT_WORDS) saveRepWords(null);
      }
    }
    writeString(storageKeys.buySessionId, res.session_id);
    setStage(res.stage);
    setCoachNotes(res.training ?? null);
    const history = res.history?.length ? res.history : res.message ? [{ role: "assistant" as const, content: res.message }] : [];
    setMessages(fromHistory(history, config.historyCap));
  }, [teamWords]);

  /** A new buy-mode call, in the tab's rep's words when they were matched for this product, else the team's.
   *  Words the script no longer takes (it changed since) are dropped and the call starts in the script's own. */
  const startBuy = useCallback(async () => {
    const product = readString(storageKeys.buyProduct);
    const words = wordsFor(product, teamWords);
    try {
      return await api.buyInit(null, words?.product ?? product, words);
    } catch (err) {
      if (!words || !(err instanceof ApiError) || err.code !== "REP_WORDS_INVALID") throw err;
      if (!words.team) saveRepWords(null);
      toast(`${words.team ? "Your team's" : "Those"} questions no longer fit the script, so the rep uses its own.`, "info");
      return api.buyInit(null, product);
    }
  }, [teamWords, toast]);

  /** Restore a call by id, sending this tab's product and words: the server starts a new call from them when it
   *  no longer has that one (it restarted, or the call sat idle too long). */
  const restoreBuy = useCallback(
    (id: string) => {
      const product = readString(storageKeys.buyProduct);
      const words = wordsFor(product, teamWords);
      return api.buyInit(id, words?.product ?? product, words);
    },
    [teamWords],
  );

  /** Start or restore a buy-mode session. Retries once without the saved id. */
  const initBuy = useCallback(
    async (useSaved = true) => {
      const saved = useSaved ? readString(storageKeys.buySessionId) : null;
      for (const id of saved ? [saved, null] : [null]) {
        try {
          adopt(id ? await restoreBuy(id) : await startBuy());
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
    [adopt, restoreBuy, startBuy, toast],
  );

  /** Sell mode: pick the tab's live call back up (after a reload, or Back from another page). */
  const restoreSell = useCallback(async () => {
    const saved = savedSellCall();
    if (!saved) return;
    const my = epoch.current;
    setTyping(true);
    try {
      const res = await api.sellState(saved.id);
      if (epoch.current !== my) return;   // the learner started another buyer meanwhile
      setSellSession({
        sessionId: res.session_id,
        persona: res.persona,
        state: res.state,
        difficulty: res.difficulty,
        productType: res.product_type,
        pick: saved.pick,
        ended: res.ended,
        outcome: res.outcome,
        hint: "",
      });
      setMessages(fromHistory(res.history, config.historyCap));
    } catch (err) {
      // Gone on the server (timed out or restarted): back to setup. A network blip keeps it for the next load.
      if (err instanceof ApiError && err.sessionExpired) saveSellCall(null);
    } finally {
      if (epoch.current === my) setTyping(false);
    }
  }, []);

  useEffect(() => {
    // Sell mode starts at buyer setup, unless this tab already has a live call (restored below).
    if (mode !== "buy" || !accountReady) return;
    if (started.current) return; // StrictMode mounts twice in dev; connect once.
    started.current = true;
    initBuy();
  }, [initBuy, mode, accountReady]);

  useEffect(() => {
    if (mode !== "sell" || started.current) return;
    started.current = true;
    restoreSell();
  }, [restoreSell, mode]);

  const markSellEnded = useCallback((outcome: Outcome) => setSellSession((p) => p && { ...p, ended: true, outcome }), []);

  const handleExpired = useCallback(
    (err: unknown) => {
      if (!(err instanceof ApiError) || !err.sessionExpired || recovering.current) return false;
      recovering.current = true;
      if (mode === "sell") {
        saveSellCall(null);
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
        // The draft stays in the box, so say so: the learner should not wonder whether it went.
        toast(`${errorText(err, "Message failed.")} Not sent: it's still in the box, press Send to retry.`, "error");
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
        const res = await api.sellInit(difficulty, productType, pick, readLocalKnowledge());
        if (sellSession) api.sellReset(sellSession.sessionId).catch(() => {});
        saveSellCall(res.session_id, pick);
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
        // A replayed real call shows its lines so far (the last is the prospect's, which the learner answers);
        // a normal start shows the buyer's opening line.
        const shown = fromHistory(pick.replay ?? [{ role: "assistant", content: res.message }], config.historyCap);
        shown[shown.length - 1].meta = metaLine(res.latency_ms, res.provider);
        setMessages(pick.replay ? [{ id: newId(), role: "divider", content: "From your real call", historyIndex: -1 }, ...shown] : shown);
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
    saveSellCall(null);
    setSellSession(null);
    setMessages([]);
    epoch.current++;
  }, [sellSession]);

  /** A new call in place of this one; false when the old call could not be ended (it carries on). */
  const reset = useCallback(async (): Promise<boolean> => {
    if (mode === "sell" && sellSession) {
      return startBuyer(sellSession.difficulty, sellSession.productType, sellSession.pick);
    }
    try {
      if (buySessionId) await api.buyReset(buySessionId);
    } catch (err) {
      if (!handleExpired(err)) {
        toast("Reset didn't stick. Try one more time.", "error");
        return false;
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
    return true;
  }, [mode, sellSession, buySessionId, startBuyer, handleExpired, toast, initBuy]);

  const chooseRepWords = useCallback(
    async (w: WordsChoice | null) => {
      const before = { words: readString(storageKeys.buyWords, "session"), product: readString(storageKeys.buyProduct) };
      // The script's own is a choice too: it beats the team's words in this tab.
      saveRepWords(w ?? SCRIPT_WORDS);
      if (w) writeString(storageKeys.buyProduct, w.product);
      if (!(await reset())) {
        // the old call carries on, so its words and product stay the tab's choice
        writeString(storageKeys.buyWords, before.words, "session");
        writeString(storageKeys.buyProduct, before.product);
      }
    },
    [reset],
  );

  const switchProduct = useCallback(
    async (productType: string) => {
      const before = readString(storageKeys.buyProduct);
      writeString(storageKeys.buyProduct, productType);
      if (!(await reset())) writeString(storageKeys.buyProduct, before);
    },
    [reset],
  );

  const jumpTo = useCallback(
    async (step: string) => {
      if (!buySessionId || busy.current) return;
      busy.current = true;
      epoch.current++;
      try {
        const res = await api.buyJump(buySessionId, step);
        adopt({ ...res, session_id: buySessionId });
      } catch (err) {
        if (!handleExpired(err)) toast("Couldn't jump to that step. Try again.", "error");
      } finally {
        busy.current = false;
      }
    },
    [buySessionId, adopt, handleExpired, toast],
  );

  const value = useMemo<SessionValue>(
    () => ({
      mode,
      buySessionId,
      buyProduct,
      repWords,
      chooseRepWords,
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
      switchProduct,
      jumpTo,
      startBuyer,
      endBuyer,
      markSellEnded,
      refreshSell: restoreSell,
      handleExpired,
    }),
    [mode, buySessionId, buyProduct, repWords, chooseRepWords, stage, coachNotes, messages, typing, sellSession, sellSettings, setSellSettings, send, edit, reset, switchProduct, jumpTo, startBuyer, endBuyer, markSellEnded, restoreSell, handleExpired],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
