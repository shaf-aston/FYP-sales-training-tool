// Spaced-repetition schedule for the drills. Pure functions: callers pass the intervals and the clock.

export interface DrillEntry {
  level: number;
  due: number;
}
export type DrillSchedule = Record<string, DrillEntry>;

const DAY_MS = 86_400_000;

/** Reads saved JSON defensively: anything that is not a valid entry is dropped. */
export function parseSchedule(raw: string | null): DrillSchedule {
  if (!raw) return {};
  try {
    const data: unknown = JSON.parse(raw);
    if (!data || typeof data !== "object") return {};
    const out: DrillSchedule = {};
    for (const [id, e] of Object.entries(data as Record<string, Partial<DrillEntry>>)) {
      if (e && Number.isFinite(e.level) && Number.isFinite(e.due)) out[id] = { level: e.level as number, due: e.due as number };
    }
    return out;
  } catch {
    return {};
  }
}

/** A drill with no entry has never been practised, so it is due. */
export function isDue(schedule: DrillSchedule, id: string, now: number): boolean {
  const entry = schedule[id];
  return !entry || entry.due <= now;
}

/** Yes moves one level up (capped at the last interval); Not quite goes back to level 0. */
export function grade(schedule: DrillSchedule, id: string, gotIt: boolean, now: number, intervalsDays: readonly number[]): DrillSchedule {
  const current = schedule[id]?.level ?? 0;
  const level = gotIt ? Math.min(current + 1, intervalsDays.length - 1) : 0;
  return { ...schedule, [id]: { level, due: now + intervalsDays[level] * DAY_MS } };
}
