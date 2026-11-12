// How the app names someone's words, and which seller lines were said in them. Pure: no React.

import type { WordsChoice } from "@/lib/api/types";

/** "Maya" -> "Maya's", "your SOP" -> "your SOP's". */
export const whose = (label: string) => `${label}'s`;

/** The tag on a seller line said in someone's words: "Maya's words", "Your SOP's words". */
export const wordsTag = (label: string) => {
  const w = `${whose(label)} words`;
  return w.charAt(0).toUpperCase() + w.slice(1);
};

export const questionCount = (n: number) => `${n} question${n === 1 ? "" : "s"}`;

/** Lowercase words only, so punctuation and spacing don't hide a match. */
const plain = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();

/** True when the seller's line says one of the chosen questions (or their asked-again lines). */
export function saysTheirWords(text: string, choice: Pick<WordsChoice, "words" | "probes">): boolean {
  const line = plain(text);
  return [...Object.values(choice.words), ...Object.values(choice.probes)].some((q) => {
    const p = plain(q);
    return p.length > 0 && line.includes(p);
  });
}
