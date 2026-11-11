// The learner's skill history on this device: one entry per scored sell session (see skillLog.ts). A module-level
// store, so the dialog and the recorder share one log without a provider.

import { useSyncExternalStore } from "react";
import type { Evaluation } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { parseLog, record, type SkillLog } from "./skillLog";

const EMPTY: SkillLog = [];   // the server render's log: storage is browser-only
let log: SkillLog | null = null;   // read from storage on first use in the browser
const listeners = new Set<() => void>();

function current(): SkillLog {
  log ??= parseLog(readString(storageKeys.skillLog));
  return log;
}

function set(next: SkillLog) {
  log = next;
  writeString(storageKeys.skillLog, JSON.stringify(next));
  listeners.forEach((l) => l());
}

export const skillStore = {
  get: current,
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  /** Keep a scored session's skill scores (scoring it again replaces them). */
  recordEvaluation(sessionId: string, evaluation: Evaluation, now = Date.now()) {
    const scores = Object.fromEntries(Object.entries(evaluation.criteria_scores).map(([id, c]) => [id, c.score]));
    set(record(current(), { sessionId, at: now, overall: evaluation.overall_score, scores }, config.skills.historyCap));
  },
};

export const useSkillLog = () => useSyncExternalStore(skillStore.subscribe, skillStore.get, () => EMPTY);
