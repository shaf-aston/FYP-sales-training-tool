// Every finished sell session's skill scores, oldest first, so progress shows over time. Pure functions:
// callers pass the log, the clock and the limits; skillStore.ts keeps it in storage.

export interface SkillEntry {
  sessionId: string;
  /** When the session was scored (ms since epoch). */
  at: number;
  overall: number;
  /** Skill id (buyer.yaml evaluation.criteria) -> 0-100. Only measured skills: a stand-in score is left out. */
  scores: Record<string, number>;
}

export type SkillLog = SkillEntry[];

const isScore = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 100;

/** Reads saved JSON defensively: anything that is not a valid entry is dropped. */
export function parseLog(raw: string | null): SkillLog {
  if (!raw) return [];
  try {
    const data: unknown = JSON.parse(raw);
    if (!Array.isArray(data)) return [];
    return data.filter(
      (e): e is SkillEntry =>
        !!e &&
        typeof e.sessionId === "string" &&
        typeof e.at === "number" &&
        Number.isFinite(e.at) &&
        isScore(e.overall) &&
        !!e.scores &&
        typeof e.scores === "object" &&
        Object.values(e.scores).every(isScore),
    );
  } catch {
    return [];
  }
}

/** Adds a session's scores; the oldest drop past `cap`. Scoring the same session again replaces its scores in place,
 * keeping when it was first scored, so the history stays in session order. */
export function record(log: SkillLog, entry: SkillEntry, cap: number): SkillLog {
  const at = log.findIndex((e) => e.sessionId === entry.sessionId);
  if (at >= 0) return log.map((e, i) => (i === at ? { ...entry, at: e.at } : e));
  return [...log, entry].slice(-cap);
}

/** Each skill's average over the last `window` sessions that scored it. */
export function averages(log: SkillLog, ids: readonly string[], window: number): Record<string, number> {
  const out: Record<string, number> = {};
  for (const id of ids) {
    const seen = log.map((e) => e.scores[id]).filter(isScore).slice(-window);
    if (seen.length) out[id] = Math.round(seen.reduce((a, b) => a + b, 0) / seen.length);
  }
  return out;
}

/** One skill's scores in session order (for its trend line). */
export function trend(log: SkillLog, id: string): number[] {
  return log.map((e) => e.scores[id]).filter(isScore);
}

/** The skill furthest below its target: what to practise next. Ties go to the earlier skill. Null when none is below. */
export function weakest(scores: Record<string, number>, ids: readonly string[], targets: Record<string, number>): string | null {
  let pick: string | null = null;
  let gap = 0;
  for (const id of ids) {
    const short = (targets[id] ?? 0) - (scores[id] ?? targets[id] ?? 0);
    if (short > gap) [pick, gap] = [id, short];
  }
  return pick;
}

/** Change between the average of the previous `window` sessions and the latest one (positive = better). */
export function change(log: SkillLog, id: string, window: number): number | null {
  const all = trend(log, id);
  if (all.length < 2) return null;
  const before = all.slice(-1 - window, -1);
  return Math.round(all[all.length - 1] - before.reduce((a, b) => a + b, 0) / before.length);
}
