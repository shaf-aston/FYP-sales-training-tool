// Pure helpers for turning the server's history into on-screen messages. No React, no I/O.

import type { ChatMsg } from "../../lib/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "divider";
  content: string;
  /** Position in the server's full history; used by edit. -1 for dividers. */
  historyIndex: number;
  /** Debug line (latency · provider), shown only with ?debug=1. */
  meta?: string;
  /** Greyed out: replaced by an edit. */
  historical?: boolean;
}

let seq = 0;
export const newId = () => `m${Date.now().toString(36)}${(seq++).toString(36)}`;

/**
 * Show at most `cap` of the newest messages, keeping each one's true index in the server
 * history (`start` = index of history[0]) so edits target the right turn.
 */
export function fromHistory(history: ChatMsg[], cap: number, start = 0): ChatMessage[] {
  const skipped = Math.max(0, history.length - cap);
  return history.slice(skipped).map((m, i) => ({ id: newId(), role: m.role, content: m.content, historyIndex: start + skipped + i }));
}

/** Index the next message will have in the server history. */
export function nextIndex(messages: ChatMessage[]): number {
  const live = messages.filter((m) => m.role !== "divider" && !m.historical);
  return live.length ? live[live.length - 1].historyIndex + 1 : 0;
}

/** Sell-mode preferences (hints and where the score shows). */
export interface SellSettings {
  showHints: boolean;
  evalDisplay: "inline" | "modal" | "panel";
}

const DISPLAYS: SellSettings["evalDisplay"][] = ["inline", "modal", "panel"];

export function parseSettings(raw: string): SellSettings | undefined {
  try {
    const v = JSON.parse(raw);
    return { showHints: v?.showHints !== false, evalDisplay: DISPLAYS.includes(v?.evalDisplay) ? v.evalDisplay : "inline" };
  } catch {
    return undefined;
  }
}
