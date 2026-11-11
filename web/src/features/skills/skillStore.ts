// The learner's skill history on this device: one entry per scored sell session (see skillLog.ts). A module-level
// store, so the dialog and the recorder share one log without a provider. Storage is the source of truth: every
// write starts from what is stored now, and another tab's write reaches this one through the "storage" event.

import { useSyncExternalStore } from "react";
import type { Evaluation } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { parseLog, record, type SkillLog } from "./skillLog";

const EMPTY: SkillLog = [];   // the server render's log: storage is browser-only
let log: SkillLog | null = null;
const listeners = new Set<() => void>();

const load = () => (log = parseLog(readString(storageKeys.skillLog)));
const notify = () => listeners.forEach((l) => l());

function onStorage(e: StorageEvent) {
  if (e.key !== storageKeys.skillLog) return;
  load();
  notify();
}

export const skillStore = {
  get: () => log ?? load(),
  subscribe(l: () => void) {
    if (!listeners.size) window.addEventListener("storage", onStorage);
    listeners.add(l);
    return () => {
      listeners.delete(l);
      if (!listeners.size) window.removeEventListener("storage", onStorage);
    };
  },
  /** Keep a scored session's measured skill scores (a stand-in score, e.g. no objection raised, is left out). */
  recordEvaluation(sessionId: string, evaluation: Evaluation, now = Date.now()) {
    const scores = Object.fromEntries(
      Object.entries(evaluation.criteria_scores)
        .filter(([, c]) => c.measured !== false)
        .map(([id, c]) => [id, c.score]),
    );
    if (!Object.keys(scores).length) return;
    log = record(load(), { sessionId, at: now, overall: evaluation.overall_score, scores }, config.skills.historyCap);
    writeString(storageKeys.skillLog, JSON.stringify(log));
    notify();
  },
  /** Swap in a whole log (the account's history after login), oldest first; the oldest drop past the cap. */
  replace(next: SkillLog) {
    set(next.slice(-config.skills.historyCap));
  },
};

export const useSkillLog = () => useSyncExternalStore(skillStore.subscribe, skillStore.get, () => EMPTY);
