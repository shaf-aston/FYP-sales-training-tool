// Plain-English names for strategies and stages. Server sends ids; the UI shows these.

interface Meta {
  label: string;
  note: string;
}

export const STRATEGY_META: Record<string, Meta> = {
  "-": { label: "Not started", note: "Begin the conversation to start tracking the flow." },
  intent: { label: "Finding out what they want", note: "The salesperson is working out what you need before choosing an approach." },
  consultative: {
    label: "Consultative",
    note: "Advice-led sale: what you want, the problem, why it matters, the solution, concerns, closing.",
  },
  transactional: { label: "Transactional", note: "Quick sale: what you want, the solution, agreeing the terms, concerns, closing." },
  prospect: { label: "Prospect practice", note: "You are in roleplay mode with a live buyer persona." },
};

export const STAGE_META: Record<string, Meta> = {
  intent: { label: "Finding out what they want", note: "Working out what you are looking for." },
  logical: { label: "Understanding the problem", note: "Digging into what is not working for you today." },
  emotional: { label: "Making it personal", note: "Why it matters to you and what happens if nothing changes." },
  pitch: { label: "Presenting the solution", note: "Showing the offer and its price." },
  negotiation: { label: "Agreeing the terms", note: "Settling payment and terms." },
  objection: { label: "Handling concerns", note: "Answering your doubts before moving on." },
  outcome: { label: "Closing", note: "You decide: buy, walk away, or think it over." },
  default: { label: "Not started", note: "Begin the conversation to start tracking the flow." },
};

export const STAGE_ORDER: Record<string, string[]> = {
  consultative: ["intent", "logical", "emotional", "pitch", "objection", "outcome"],
  transactional: ["intent", "pitch", "objection", "outcome"],
  intent: ["intent"],
};

export const key = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

export const strategyMeta = (s: string) => STRATEGY_META[key(s)] ?? STRATEGY_META["-"];
/** The server sends "----" while it is still working out the strategy; show that as the intent stage. */
const UNDETERMINED_STAGE = "----";

export const stageMeta = (s: string) =>
  STAGE_META[key(s)] ?? (s === UNDETERMINED_STAGE ? STAGE_META.intent : { label: s, note: "" });
export const stagesFor = (strategy: string) => STAGE_ORDER[key(strategy)] ?? STAGE_ORDER.consultative;
