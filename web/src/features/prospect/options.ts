// Option lists and labels shown in the prospect UI. Tunable numbers live in lib/config.ts.

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
