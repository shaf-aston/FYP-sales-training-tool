// Holds the latest session evaluation so the panel, the dialogs and the review all read the same one.
// A tiny external store (no provider needed: AppShell is shared and read-only).

import { useSyncExternalStore } from "react";
import type { Evaluation } from "@/lib/api/types";

export interface EvalState {
  /** The sell-mode session this evaluation belongs to. */
  sessionId: string | null;
  status: "idle" | "loading" | "ready" | "error";
  result: Evaluation | null;
  error: string;
  /** Inline card closed by the user. */
  dismissed: boolean;
}

const IDLE: EvalState = { sessionId: null, status: "idle", result: null, error: "", dismissed: false };

let state: EvalState = IDLE;
const listeners = new Set<() => void>();

function set(next: EvalState) {
  state = next;
  listeners.forEach((l) => l());
}

export const evalStore = {
  get: () => state,
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  begin: (sessionId: string) => set({ ...IDLE, sessionId, status: "loading" }),
  succeed: (sessionId: string, result: Evaluation) => {
    if (state.sessionId === sessionId) set({ ...state, status: "ready", result, error: "" });
  },
  fail: (sessionId: string, error: string) => {
    if (state.sessionId === sessionId) set({ ...state, status: "error", error });
  },
  dismiss: () => set({ ...state, dismissed: true }),
  reset: () => set(IDLE),
};

export const useEvalState = () => useSyncExternalStore(evalStore.subscribe, evalStore.get, () => IDLE);

/** Grade letter of the finished session ("" until scored). */
export const gradeOf = (s: EvalState) => (s.result?.grade ?? "").toUpperCase();
