// Plain-English names for stages and modes. Server sends ids; the UI shows these.

interface Meta {
  label: string;
  /** How to recognise the stage from what the seller is saying (shown after a stage quiz pick). */
  hint?: string;
}

const STAGE_META: Record<string, Meta> = {
  intent: { label: "Finding out what they want", hint: "The seller asks what you want to achieve." },
  logical: { label: "Understanding the problem", hint: "The seller asks for facts: how much, how long, what you have tried." },
  emotional: { label: "Making it personal", hint: "The seller looks for the belief holding you back, and what staying stuck would cost you." },
  pitch: { label: "Presenting the solution", hint: "The seller explains the offer and how it fits what you said." },
  outcome: { label: "Closing", hint: "The seller asks you to decide." },
  default: { label: "Not started" },
};

/** The buy-mode call in order, with a one-word name each for the progress tracker. */
export const STAGE_STEPS = [
  { id: "intent", short: "Want" },
  { id: "logical", short: "Problem" },
  { id: "emotional", short: "Belief" },
  { id: "pitch", short: "Solution" },
  { id: "outcome", short: "Close" },
] as const;

/**
 * The two modes, named for what the learner does. Buy: you are the customer and the AI
 * seller sells to you. Sell: you are the salesperson and the AI buyer answers.
 */
export const MODE_META = {
  buy: { name: "Buy mode", heading: "You're buying", note: "The AI sells to you.", switchLabel: "Switch to selling" },
  sell: { name: "Sell mode", heading: "You're selling", note: "The AI is your buyer.", switchLabel: "Switch to buying" },
} as const;

const key = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

/** Meta for a stage given its id ("logical") or its plain name ("Understanding the problem"). */
export const stageMeta = (s: string) =>
  STAGE_META[key(s)] ?? Object.values(STAGE_META).find((m) => key(m.label) === key(s)) ?? { label: s };

/** Where `stage` sits in STAGE_STEPS; -1 before the call starts. */
export const stageIndex = (s: string) => STAGE_STEPS.findIndex((step) => step.id === key(s));
