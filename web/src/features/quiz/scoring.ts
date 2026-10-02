import { config } from "@/lib/config";
import type { QuizType } from "@/lib/api/types";

export type Band = "success" | "warning" | "danger";
export type QuizKind = QuizType | "prospect";

/** Percent for display, or null when the server gave no score. Stage quiz sends 0..1. */
export function scorePercent(kind: QuizKind, score: number | null | undefined): number | null {
  if (score === null || score === undefined) return null;
  return kind === "stage" ? Math.round(score * 100) : Math.round(score);
}

export function scoreBand(kind: QuizKind, percent: number | null): Band {
  if (percent === null) return "warning";
  const { correct, partial } = kind === "stage" ? config.quizBands.stage : config.quizBands;
  return percent >= correct ? "success" : percent >= partial ? "warning" : "danger";
}
