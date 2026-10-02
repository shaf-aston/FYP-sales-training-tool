// Tunables for the prospect feature (motion timings, labels). Change behaviour here, not in components.

export const prospectConfig = {
  deltaChipMs: 1_600,
  confetti: { count: 90, durationMs: 2_200, gravity: 0.18 },
  /** Grades that earn the celebration (together with a sale). */
  celebrateGrades: ["A"],
} as const;

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
