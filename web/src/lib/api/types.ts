// Shapes of the Flask JSON API (backend/routes/*). Field names match the server exactly.

export type Strategy = "CONSULTATIVE";
export type Difficulty = "easy" | "medium" | "hard";
export type TrainingStyle = "tactical" | "socratic" | "teacher";
export type QuizType = "stage" | "next_move" | "direction";
export type Outcome = "active" | "sold" | "walked" | "incomplete";

export interface BotState {
  stage: string; // UPPERCASE stage id
  strategy: Strategy;
}

export interface Training {
  what_happened: string;
  next_move: string;
  watch_for: string[];
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
  training?: Training;
}

export interface ChatRes extends BotState {
  success: true;
  message: string;
  latency_ms: number | null;
  provider: string;
  model: string;
  metrics?: { input_length: number; output_length: number };
  training: Training;
}

export interface EditRes extends BotState {
  success: true;
  message: string;
  history: ChatMsg[];
  latency_ms: number | null;
  provider: string;
  model: string;
  training: Training;
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
  expected?: { stage: string; strategy: string };
  before?: { text: string; good: boolean }[];
}

/** The AI buyer's state in sell mode. */
export interface BuyerState {
  readiness: number; // 0..1
  objections_raised: number;
  turn_count: number;
  has_committed: boolean;
  has_walked: boolean;
  difficulty: Difficulty;
  product_type: string;
  persona_name: string;
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
  max_turns: number | null;
  scoring_enabled: boolean;
  feedback_style: string;
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
