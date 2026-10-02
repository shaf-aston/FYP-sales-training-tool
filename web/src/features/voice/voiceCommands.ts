// Pure text helpers for dictation: spoken flow commands and spoken punctuation. No imports, no browser.

export type FlowCommand = { type: "stage" | "strategy"; value: string };

const STAGE = /\b(?:jump|go|move|switch)\s+(?:to\s+)?(?:the\s+)?(?:stage\s+)?(intent|logical|emotional|pitch|objection)\b/;
const STRATEGY = /\b(?:switch|set)\s+(?:strategy\s+)?(?:to\s+)?(intent|consultative|transactional)\b/;

/** "jump to pitch" -> stage, "switch strategy to consultative" -> strategy. Anything else -> null. */
export function parseFlowCommand(raw: string): FlowCommand | null {
  const text = String(raw || "").trim().toLowerCase();
  if (!text) return null;
  const strategy = text.match(STRATEGY);
  if (strategy) return { type: "strategy", value: strategy[1] };
  const stage = text.match(STAGE);
  if (stage) return { type: "stage", value: stage[1] };
  return null;
}

/** Turns spoken " period " / " comma " / " new line " into the real characters. */
export function parsePunctuation(text: string): string {
  return text.replace(/ period /g, ". ").replace(/ comma /g, ", ").replace(/ new line /g, "\n");
}
