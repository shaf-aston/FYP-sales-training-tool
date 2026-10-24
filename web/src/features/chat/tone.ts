// Tone marks in the seller's lines (written in the script, see core/script_engine/tone.py):
//   _word_     stress: italics (markdown does this already)
//   ==words==  the key thing: a soft highlight
//   ¶          a pause: what follows is a new bubble, after typing dots

export const PAUSE = "¶";
const KEY = /==(.+?)==/g;
const STRESS = /(^|[\s("'])_(\w[^_]*?)_(?=[\s.,!?…"']|$)/g; // "_all_", never belief_cost

/** The bubbles one message is said in. */
export const bubbles = (text: string) =>
  text
    .split(PAUSE)
    .map((b) => b.trim())
    .filter(Boolean);

/** Markdown with the key mark drawn as <mark> (a tag the sanitiser keeps). */
export const highlighted = (text: string) => text.replace(KEY, "<mark>$1</mark>");

/** The words to read aloud: no marks, and each bubble ends a sentence so the voice pauses between them. */
export const speakable = (text: string) =>
  bubbles(text)
    .map((b) => b.replace(KEY, "$1").replace(STRESS, "$1$2"))
    .map((b) => (/[.!?…]$/.test(b) ? b : `${b}.`))
    .join(" ");

/** How long the typing dots show before a bubble: longer lines take longer to "type", within limits. */
export const typingMs = (bubble: string) => Math.min(2400, Math.max(600, 350 + 22 * bubble.length));
