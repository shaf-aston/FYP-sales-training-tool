// Option lists and labels shown in the sell-mode UI. Tunable numbers live in lib/config.ts.

import { config } from "@/lib/config";

/** One word for how warm the AI buyer is, from readiness in percent. */
export const readinessBand = (pct: number) =>
  pct < config.readinessBands.low ? "At risk" : pct < config.readinessBands.mid ? "Warming up" : "Ready";

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
