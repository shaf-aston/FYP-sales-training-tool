/** Turn coach text into one short plain line: strip markdown, collapse whitespace, truncate. */
export function cleanCoachText(raw: string | null | undefined, max = 120): string {
  const text = (raw ?? "")
    .replace(/^\s*(?:[-*+]|\d+\.)\s+/gm, "")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > max ? `${text.slice(0, max - 3)}...` : text;
}
