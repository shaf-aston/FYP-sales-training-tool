// Shapes of the Flask JSON API (backend/routes/*). Field names match the server exactly.

export type Difficulty = "easy" | "medium" | "hard";
export type CoachStyle = "tactical" | "socratic" | "teacher";
export type QuizType = "stage" | "next_move" | "direction";
export type Outcome = "active" | "sold" | "walked";

export interface BotState {
  stage: string; // UPPERCASE stage id
}

/** Buy-mode coach notes; the server sends them under the key "training". */
export interface CoachNotes {
  what_happened: string;
  next_move: string;
}

export interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

export interface InitRes extends BotState {
  success: true;
  session_id: string;
  message: string | null; // greeting for a new session, null on restore
  history: ChatMsg[];
  training?: CoachNotes;
  /** What the rep is selling on this call (an id from /api/buy/products). */
  product_type?: string;
}

/** Something the rep can sell in buy mode; each runs its own call script. */
export interface BuyProduct {
  id: string;
  label: string;
  blurb: string;
  price: string;
  /** The one a call sells when none is picked. */
  default: boolean;
}

/** A script step the learner can start a fresh call at (to test it). */
export interface ScriptStep {
  id: string;
  name: string;
  /** UI stage the step belongs to. */
  stage: string;
}

export interface JumpRes extends BotState {
  success: true;
  message: string;
  history: ChatMsg[];
  training: CoachNotes;
}

export interface ChatRes extends BotState {
  success: true;
  message: string;
  latency_ms: number | null;
  provider: string;
  model: string;
  training: CoachNotes;
}

export interface EditRes extends BotState {
  success: true;
  message: string;
  history: ChatMsg[];
  latency_ms: number | null;
  provider: string;
  model: string;
  training: CoachNotes;
}

export interface ProductOption {
  id: string;
  label: string;
}

export interface ProductGroups {
  transactional: ProductOption[];
  consultative: ProductOption[];
}

export interface QuizQuestion {
  success: true;
  question: string;
  type?: string;
  turn?: number; // sell-mode quiz only
}

export interface QuizResult {
  success: true;
  score: number | null;
  feedback?: string;
  strengths?: string[];
  improvements?: string[];
  key_concepts_got?: string[];
  key_concepts_missed?: string[];
  coach_tip?: string;
  expected?: { stage: string };
  before?: { text: string; good: boolean }[];
}

/** The AI buyer's state in sell mode. */
export interface BuyerState {
  readiness: number; // 0..1
  turn_count: number;
}

export interface Persona {
  name: string;
  background: string;
  personality: string;
}

/** Which AI buyer the learner chose in setup. Empty fields mean "pick for me". */
export interface BuyerPick {
  persona?: string;
  objection?: string;
  /** A buyer built from a real call (sent as custom_buyer); replaces persona when set. */
  custom?: CustomBuyer;
  /** Start inside a real call instead of at an opening line: its lines so far, ending with the buyer's. */
  replay?: ChatMsg[];
}

export type ObjectionType = "price" | "skepticism" | "timing" | "partner" | "fear";

/** An objection the prospect raised on the call, in their own words. */
export interface CallObjection {
  type: ObjectionType;
  text: string;
}

/** A buyer the learner describes (built from a real call); /api/sell/init custom_buyer. */
export interface CustomBuyer {
  name: string;
  background: string;
  personality: string;
  budget: string;
  needs: string[];
  pain_points: string[];
  objections: CallObjection[];
}

export interface SellInitRes {
  success: true;
  session_id: string;
  message: string;
  persona: Persona;
  state: BuyerState;
  difficulty: Difficulty;
  product_type: string;
  latency_ms: number;
  provider: string;
  model: string;
}

export interface SellChatRes {
  success: true;
  message: string;
  state: BuyerState;
  latency_ms: number;
  provider: string;
  model: string;
  ended: boolean;
  outcome: Outcome;
  coaching?: { hint: string };
}

export interface Evaluation {
  success: true;
  overall_score: number;
  grade: string;
  outcome: Outcome;
  criteria_scores: Record<string, { score: number; feedback: string }>;
  strengths: string[];
  improvements: string[];
  summary: string;
  coach_tip: string;
}

/** A skill every sell session is scored on (buyer.yaml evaluation.criteria), tracked by Skill Radar. */
export interface Skill {
  id: string;
  label: string;
  /** What to try when this is the weakest skill. */
  tip: string;
  weight: number;
  /** The session that trains it: a difficulty, and an objection the buyer raises on turn 1. */
  practice: { difficulty: Difficulty; objection?: string };
}

export interface SkillsRes {
  success: true;
  /** The score that counts as strong: the default target. */
  target: number;
  skills: Skill[];
}

export interface ReviewTurn {
  turn: number;
  seller: string;
  buyer: string | null;
  rating: number; // 1-5
  reasons: string[];
  readiness_change: number;
}

export interface Review {
  success: true;
  turns: ReviewTurn[];
  pivotal_turns: number[];
  summary: {
    turn_count: number;
    average_rating: number;
    went_well: boolean;
    work_on: string;
  };
}

export interface RedoRes {
  success: true;
  turn: number;
  message: string;
  state: BuyerState;
  outcome: Outcome;
}

export interface Drill {
  id: string;
  label: string;
  segments: string[]; // segments.length === answers.length + 1
  answers: string[];
}

/** A real sales call the learner pasted or uploaded (/api/calls/read and /api/calls/review). */
export interface CallReq {
  text: string;
  filename?: string;
  /** The speaker who is the learner; the server guesses when it is missing. */
  rep?: string;
}

export interface CallSpeaker {
  name: string;
  turns: number;
  words: number;
  questions: number;
}

/** How the server picked the rep: the learner's name, the most questions, or who spoke first. */
export type RepGuess = "named" | "most_questions" | "first_speaker";

export interface CallTurn {
  speaker: string;
  role: "rep" | "prospect" | "other";
  text: string;
  at: string | null;
}

/** The prospect as read from the call, with the short quotes or reasons behind each field. */
export interface CallProfile extends CustomBuyer {
  difficulty: Difficulty;
  evidence: Partial<Record<string, string[]>>;
}

export interface CallReadRes {
  success: true;
  format: "vtt" | "srt" | "speaker_lines" | "speaker_blocks";
  speakers: CallSpeaker[];
  rep: { name: string; how: RepGuess; sure: boolean };
  prospect: string;
  turns: CallTurn[];
  profile: CallProfile;
}

export type KnowledgeField =
  | "product_name"
  | "pricing"
  | "specifications"
  | "company_info"
  | "selling_points"
  | "additional_notes";

export type KnowledgeData = Partial<Record<KnowledgeField, string>>;

export interface FeedbackReq {
  rating: number | null;
  comment: string | null;
  /** The mode the feedback was sent from. */
  page: "buy" | "sell";
}
