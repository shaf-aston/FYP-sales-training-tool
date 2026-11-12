"use client";

// State for the Rep's words tool: the script questions a source (a real call's rep, or an SOP) asks in its own
// words, and which of them the learner keeps. Every change happens in an event handler.

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { RepWordsReq, RepWordsRes } from "@/lib/api/types";
import { useJob } from "@/lib/useJob";

export interface Matched {
  res: RepWordsRes;
  /** Whose words, for the learner: the call's rep, or "your SOP". */
  label: string;
}

/** "Maya Okafor" -> "Maya": how the learner will refer to the rep. */
const firstName = (name: string) => name.trim().split(/\s+/)[0] || name;

export function useRepWords() {
  const [matched, setMatched] = useState<Matched | null>(null);
  /** Steps the learner turned off: the script asks those in its own words. */
  const [off, setOff] = useState<ReadonlySet<string>>(new Set());
  const { busy, error, run, cancel } = useJob<"match">();

  return {
    matched,
    off,
    busy,
    error,
    /** Ask the server which script questions the source asks too. */
    match: async (req: RepWordsReq, label: string) => {
      const res = await run("match", () => api.buyWords(req), "Couldn't match those questions. Try again.");
      if (!res) return;
      setMatched({ res, label: res.rep ? firstName(res.rep) : label });
      setOff(new Set());
    },
    toggle: (step: string) =>
      setOff((o) => {
        const next = new Set(o);
        if (!next.delete(step)) next.add(step);
        return next;
      }),
    /** {step: question} for the matches the learner kept. */
    kept: () => Object.fromEntries((matched?.res.matches ?? []).filter((m) => !off.has(m.step)).map((m) => [m.step, m.theirs])),
    /** Back to choosing a source. */
    back: () => {
      cancel();
      setMatched(null);
    },
  };
}

export type RepWordsState = ReturnType<typeof useRepWords>;
