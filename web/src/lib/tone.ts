// Tone marks in the seller's lines (written in the script, see core/script_engine/tone.py):
//   **word**   loud stress: bold (markdown does this already)
//   _word_     stretched stress: italics (markdown does this already)
//   ==words==  the key thing: a soft highlight
//   ... …      a short pause: kept, the voice pauses on it
//   ¶ [pause]  a long pause: what follows is a new bubble, after typing dots
//   (slow)     a tone note in front of a line: never shown or said, it sets how fast the voice reads
// The server's voice hears the stress marks (louder, drawn out, a beat before); the browser's own voice reads words.

export const PAUSE = "¶";
const KEY = /==(.+?)==/g;
const LOUD = /\*\*(\S(?:.*?\S)?)\*\*/g;
const LONG_PAUSE = /\s*\[pause[^\]]*\]\s*/g;
/** Tone words and how they change the voice's speed (1 = as set). Same words as tone.py TONES. */
const TONES: Record<string, number> = {
  slow: 0.85, deliberate: 0.9, calm: 0.92, gentle: 0.92, soft: 0.92, warm: 0.95, serious: 0.95,
  firm: 1, curious: 1, playful: 1.08, excited: 1.12, upbeat: 1.08,
};
const TONE = Object.keys(TONES).join("|");
const NOTE = new RegExp(`\\((?:${TONE})(?:,\\s*(?:${TONE}))*\\)\\s*`, "g");
const STRESS = /(^|[\s("'“‘])_(\w[^_]*?)_(?=[\s.,!?…:;)—\-"'”’]|$)/g; // "_all_", never belief_cost

/** The bubbles one message is said in. */
export const bubbles = (text: string) =>
  text
    .replace(LONG_PAUSE, PAUSE)
    .replace(NOTE, "")
    .split(PAUSE)
    .map((b) => b.trim())
    .filter(Boolean);

/** Markdown with the key mark drawn as <mark> (a tag the sanitiser keeps). */
export const highlighted = (text: string) => text.replace(KEY, "<mark>$1</mark>");

/** The words to read aloud, each bubble ending a sentence so the voice pauses between them. The stress marks stay
 *  (the server's voice says them: core/infra/providers/voice_marks.py); tone notes and pauses go. */
export const speakable = (text: string) =>
  bubbles(text)
    .map((b) => (/[.!?…]$/.test(b) ? b : `${b}.`))
    .join(" ");

/** The words alone, for a voice that can't say the marks (the browser's own). */
export const unmarked = (text: string) => text.replace(KEY, "$1").replace(LOUD, "$1").replace(STRESS, "$1$2");

/** How long the typing dots show before a bubble: longer lines take longer to "type", within limits. */
const TYPING = { baseMs: 350, perCharMs: 22, minMs: 600, maxMs: 2400 };
export const typingMs = (bubble: string) =>
  Math.min(TYPING.maxMs, Math.max(TYPING.minMs, TYPING.baseMs + TYPING.perCharMs * bubble.length));

/** How fast to read a line, from its tone note: "(slow, deliberate)" → slower. 1 when it has none. */
export const toneRate = (text: string) => {
  const note = text.match(NOTE)?.[0] ?? "";
  return Object.entries(TONES).reduce((rate, [word, r]) => (new RegExp(`\\b${word}\\b`).test(note) ? rate * r : rate), 1);
};
