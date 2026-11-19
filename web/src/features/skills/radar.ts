// Geometry for the skill radar: one axis per skill, the first pointing straight up, going clockwise.
// Pure: values in, SVG coordinates out, so the chart component only draws.

export interface Point {
  x: number;
  y: number;
}

/** Where `value` (0..max) sits on axis `i` of `n`, for a chart of `radius` centred on (radius, radius). */
export function axisPoint(i: number, n: number, value: number, max: number, radius: number): Point {
  const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
  const r = (Math.min(Math.max(value, 0), max) / max) * radius;
  return { x: round(radius + r * Math.cos(angle)), y: round(radius + r * Math.sin(angle)) };
}

/** An SVG `points` attribute for one value per axis (a missing value sits at the centre). */
export function polygon(values: readonly (number | undefined)[], max: number, radius: number): string {
  // A skill never measured has no point: drawn at the centre it read as a score of 0.
  return values
    .map((v, i) => (v === undefined ? null : axisPoint(i, values.length, v, max, radius)))
    .filter((p): p is Point => p !== null)
    .map((p) => `${p.x},${p.y}`)
    .join(" ");
}

/** Where an axis label sits, a little outside the chart edge, and how it should anchor so it never overlaps the chart. */
export function labelPlace(i: number, n: number, radius: number, gap: number): Point & { anchor: "start" | "middle" | "end" } {
  const p = axisPoint(i, n, 1, 1, radius + gap);
  const dx = p.x - (radius + gap);
  const anchor = Math.abs(dx) < 1 ? "middle" : dx > 0 ? "start" : "end";
  return { x: round(p.x - gap), y: round(p.y - gap), anchor };
}

/** "needs discovery" -> "Needs discovery": skill labels come lower case from config. */
export const sentenceCase = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** An axis label on two lines when it has two or more words, so labels at the sides stay inside narrow screens. */
export function labelLines(label: string): string[] {
  const words = sentenceCase(label).split(" ");
  if (words.length < 2) return words;
  const half = Math.ceil(words.length / 2);
  return [words.slice(0, half).join(" "), words.slice(half).join(" ")];
}

const round = (n: number) => Math.round(n * 100) / 100;
