// Pure text helper for dictation: spoken punctuation. No imports, no browser.

/** Turns spoken " period " / " comma " / " new line " into the real characters. */
export function parsePunctuation(text: string): string {
  return text.replace(/ period /g, ". ").replace(/ comma /g, ", ").replace(/ new line /g, "\n");
}
