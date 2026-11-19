// Plain-English names for stages and modes. Server sends ids; the UI shows these.

interface Meta {
  label: string;
  /** How to recognise the stage from what the seller is saying (shown after a stage quiz pick). */
  hint?: string;
  /** Sell mode: what the learner (the rep) does in the stage. */
  sellHint?: string;
}

const STAGE_META: Record<string, Meta> = {
  intent: { label: "Finding out what they want", hint: "The seller asks what you want to achieve.", sellHint: "Find out what they want, and why." },
  logical: { label: "Understanding the problem", hint: "The seller asks for facts: how much, how long, what you have tried.", sellHint: "Get the facts: the problem, how long, what it costs them." },
  emotional: { label: "Making it personal", hint: "The seller looks for the belief holding you back, and what staying stuck would cost you.", sellHint: "Find why it matters now, and what staying put would cost them." },
  pitch: { label: "Presenting the solution", hint: "The seller explains the offer and how it fits what you said.", sellHint: "Show how your offer fits what they told you." },
  outcome: { label: "Closing", hint: "The seller asks you to decide.", sellHint: "Ask for the decision." },
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
  buy: { name: "Buy mode", heading: "You're buying", note: "A virtual rep sells to you.", switchLabel: "Switch to selling" },
  sell: { name: "Sell mode", heading: "You're selling", note: "A virtual buyer pushes back.", switchLabel: "Switch to buying" },
} as const;

const key = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

/** Meta for a stage given its id ("logical") or its plain name ("Understanding the problem"). */
export const stageMeta = (s: string) =>
  STAGE_META[key(s)] ?? Object.values(STAGE_META).find((m) => key(m.label) === key(s)) ?? { label: s };

/** A stage's one-word name from the progress tracker ("Belief"); the id itself when it has none. */
export const stageShort = (s: string) => STAGE_STEPS.find((step) => step.id === key(s))?.short ?? s;

/** Where `stage` sits in STAGE_STEPS; -1 before the call starts. */
export const stageIndex = (s: string) => STAGE_STEPS.findIndex((step) => step.id === key(s));
