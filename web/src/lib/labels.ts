// Plain-English names for strategies, stages and modes. Server sends ids; the UI shows these.

interface Meta {
  label: string;
}

export const STRATEGY_META: Record<string, Meta> = {
  "-": { label: "Not started" },
  consultative: { label: "Consultative" },
};

export const STAGE_META: Record<string, Meta> = {
  intent: { label: "Finding out what they want" },
  logical: { label: "Understanding the problem" },
  emotional: { label: "Making it personal" },
  pitch: { label: "Presenting the solution" },
  outcome: { label: "Closing" },
  default: { label: "Not started" },
};

/**
 * The two modes, named for what the learner does. Buy: you are the customer and the AI
 * seller sells to you. Sell: you are the salesperson and the AI buyer answers.
 */
export const MODE_META = {
  buy: { name: "Buy mode", heading: "You're buying", note: "The AI sells to you.", switchLabel: "Switch to selling" },
  sell: { name: "Sell mode", heading: "You're selling", note: "The AI is your buyer.", switchLabel: "Switch to buying" },
} as const;

export const key = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

export const strategyMeta = (s: string) => STRATEGY_META[key(s)] ?? STRATEGY_META["-"];
export const stageMeta = (s: string) => STAGE_META[key(s)] ?? { label: s };
