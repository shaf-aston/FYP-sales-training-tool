// Plain-English names for strategies and stages. Server sends ids; the UI shows these.

interface Meta {
  label: string;
}

export const STRATEGY_META: Record<string, Meta> = {
  "-": { label: "Not started" },
  consultative: { label: "Consultative" },
  prospect: { label: "Prospect practice" },
};

export const STAGE_META: Record<string, Meta> = {
  intent: { label: "Finding out what they want" },
  logical: { label: "Understanding the problem" },
  emotional: { label: "Making it personal" },
  pitch: { label: "Presenting the solution" },
  outcome: { label: "Closing" },
  default: { label: "Not started" },
};

/** The two practice modes: heading + one-line "who does what". */
export const MODE_META = {
  seller: { label: "Seller bot", note: "You're the customer → an AI salesperson sells to you" },
  prospect: { label: "Prospect practice", note: "You're the salesperson → an AI buyer answers" },
} as const;

export const key = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

export const strategyMeta = (s: string) => STRATEGY_META[key(s)] ?? STRATEGY_META["-"];
export const stageMeta = (s: string) => STAGE_META[key(s)] ?? { label: s };
