// Option lists and labels shown in the sell-mode UI. Tunable numbers live in lib/config.ts.

import { config } from "@/lib/config";

/** One word for how warm the AI buyer is, from readiness in percent. */
export const readinessBand = (pct: number) =>
  pct < config.readinessBands.low ? "At risk" : pct < config.readinessBands.mid ? "Warming up" : "Ready";

/** Badge colour for a letter grade (A-F from core/sell_evaluator.py). Red grades count as a weak session. */
export const gradeTone = (g: string) => (g === "A" || g === "B" ? "success" : g === "C" ? "warning" : "danger");

/** A change in points with its sign, e.g. "+5" or "-3". */
export const signed = (n: number) => (n > 0 ? `+${n}` : `${n}`);

export const difficultyOptions = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
] as const;

export const difficultyTone = { easy: "success", medium: "warning", hard: "danger" } as const;

export const evalDisplayOptions = [
  { value: "inline", label: "Inline" },
  { value: "modal", label: "Modal" },
  { value: "panel", label: "Panel" },
] as const;
