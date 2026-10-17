// Plain-English names for stages and modes. Server sends ids; the UI shows these.

interface Meta {
  label: string;
}

const STAGE_META: Record<string, Meta> = {
  intent: { label: "Finding out what they want" },
  logical: { label: "Understanding the problem" },
  emotional: { label: "Making it personal" },
  pitch: { label: "Presenting the solution" },
  outcome: { label: "Closing" },
  default: { label: "Not started" },
};

/** The buy-mode call in order, with a one-word name each for the progress tracker. */
export const STAGE_STEPS = [
  { id: "intent", short: "Want" },
  { id: "logical", short: "Problem" },
  { id: "emotional", short: "Personal" },
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

export const stageMeta = (s: string) => STAGE_META[key(s)] ?? { label: s };

/** Where `stage` sits in STAGE_STEPS; -1 before the call starts. */
export const stageIndex = (s: string) => STAGE_STEPS.findIndex((step) => step.id === key(s));
