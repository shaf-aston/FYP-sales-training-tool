// Shapes of the Flask JSON API (backend/routes/*). Field names match the server exactly.

import type { SkillEntry } from "@/features/skills/skillLog";

/** The server keeps the web's skill log as is (/api/account/skills): skillLog.ts owns the shape. */
export type { SkillEntry };

export type Difficulty = "easy" | "medium" | "hard";
export type CoachStyle = "tactical" | "socratic" | "teacher";
export type QuizType = "stage" | "next_move" | "direction";
/** "ended": the learner ended the call ("End and score") before the buyer said yes or walked. */
export type Outcome = "active" | "sold" | "walked" | "ended";

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
  /** The script questions this call asks in someone else's words ({step: question}; empty: the script's own). */
  words?: Record<string, string>;
  /** Whose those words are ("Maya", "your SOP"), as the client named them when the call started. */
  words_label?: string;
  /** The same steps asked again in their words ({step: question}). */
  probes?: Record<string, string>;
}

/** One of the script's questions the rep can ask in someone else's words (POST /api/buy/words). */
export interface RepWordsMatch {
  step: string;
  /** The step's name in the script ("" when it has none). */
  name: string;
  stage: string;
  /** The script's question there. */
  script: string;
  /** The top rep's or the SOP's question that asks the same thing. */
  theirs: string;
  /** How alike the two are, 0-1. */
  score: number;
  /** The source asking the same again in other words ("" when it doesn't): said when the step is asked again. */
  probe: string;
}

/** Someone's words as kept: in this tab, saved to an account, or set for a team. */
export interface WordsChoice {
  /** The product (script) the words were matched against: other products' calls use the script's own. */
  product: string;
  /** Whose words, for the learner: "Maya" (a call's rep) or "your SOP". */
  label: string;
  /** {step: question} said instead of the script's. */
  words: Record<string, string>;
  /** {step: question} said when those steps are asked again (only steps in `words`). */
  probes: Record<string, string>;
}

/** A WordsChoice saved to the account (GET /api/account/words). */
export interface SavedWords extends WordsChoice {
  id: number;
  /** Seconds since epoch. */
  created_at: number;
}

/** Where the rep's words come from: a real call (its top rep) or an SOP outline (from /api/sop/read). */
export type RepWordsReq = { product_type: string | null } & ({ call: CallReq } | { stages: SopStage[] });

export interface RepWordsRes {
  success: true;
  product_type: string;
  /** The rep's name in the call (null for an SOP). */
  rep: string | null;
  /** Questions found in the source. */
  questions: number;
  /** Question steps in the script. */
  steps: number;
  matches: RepWordsMatch[];
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

/** GET /api/sell/state: a live sell call, to pick it back up after a reload. */
export interface SellStateRes {
  success: true;
  session_id: string;
  persona: Persona;
  state: BuyerState;
  difficulty: Difficulty;
  product_type: string;
  history: ChatMsg[];
  ended: boolean;
  outcome: Outcome;
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
  /** `measured` false: a stand-in score (no evidence in this session, e.g. no objection was raised). */
  criteria_scores: Record<string, { score: number; feedback: string; measured?: boolean }>;
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
  /** The targets a learner can pick (the default is one of them). */
  targets: number[];
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

/** How a stage of the call went (core/sell_mode/call_stages.py, config/call_stages.yaml). */
export type StageStatus = "strong" | "partly" | "missed" | "early" | "weak" | "none";
export interface CallStage {
  id: string;
  name: string;
  status: StageStatus;
  /** What happened, in a line. */
  says: string;
  /** Why the stage matters, the human reason behind it. */
  why: string;
  /** One thing to try next time; empty when there is nothing to work on. */
  next: string;
  /** The evidence: turn numbers. */
  turns: number[];
}

export interface Review {
  success: true;
  turns: ReviewTurn[];
  pivotal_turns: number[];
  /** The call stage by stage, in call order; and the earliest one to work on. */
  stages?: CallStage[];
  stage_focus?: string | null;
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

// SOP review (/api/sop): a team's sales SOP read into stages and steps.

export interface SopStage {
  title: string;
  steps: string[];
}

/** One element of a good call (core/sop/checklist.py), and the SOP step that covers it. */
export interface SopElement {
  id: string;
  label: string;
  covered: boolean;
  step: string | null;
  /** Why it matters: shown when the SOP misses it. */
  why: string;
}

export interface SopReadRes {
  success: true;
  stages: SopStage[];
  elements: SopElement[];
  /** Share of elements covered, 0-100. */
  coverage: number;
  /** A short paragraph summing it up, the costliest gap first (written by rules). */
  critique?: string;
}

/** One SOP step in a real call: done at the rep's turn `turn` (1-based) with what they said, or not heard. */
export interface SopStepResult {
  stage: string;
  step: string;
  done: boolean;
  /** An "If they…" step: left out of the score when not done (the call may never have needed it). */
  conditional: boolean;
  turn: number | null;
  said: string | null;
}

export interface SopCheckRes {
  success: true;
  /** The speaker taken as the rep. */
  rep: string;
  /** Share of steps done, 0-100. */
  score: number;
  /** The done steps happened in the SOP's order. */
  in_order: boolean;
  steps: SopStepResult[];
  /** A short paragraph summing it up: the share done, the first step skipped (written by rules). */
  critique?: string;
}

// Accounts (/api/account, /api/team): optional; everything works logged out.

export interface AccountUser {
  id: number;
  email: string;
  name: string;
  /** False for an account made by an email link or Google: it signs in only that way. */
  has_password: boolean;
}

/** Which ways of signing in without a password the server has set up. */
export interface SignInOptions {
  success: true;
  link: boolean;
  google: boolean;
}

/** The learner's team. Only a manager gets the invite code. */
export interface Team {
  id: number;
  name: string;
  role: "member" | "manager";
  invite_code: string | null;
  /** The team's Rep's words, set by a manager (null: none): members' new calls on that product use them. */
  words: WordsChoice | null;
}

/** Who is logged in (nulls when no one is): /api/account/me, signup and login. */
export interface AccountMe {
  user: AccountUser | null;
  team: Team | null;
}

/** A manager sees every member with their email; a rep sees the managers only. */
export interface TeamMember {
  id: number;
  name: string;
  role: Team["role"];
  email?: string;
}

/** One member in a manager's insights: skill levels are their recent averages (config/insights.yaml window). */
export interface MemberInsight {
  user_id: number;
  name: string;
  sessions: number;
  /** Latest scored session, ms since epoch. */
  last_at: number | null;
  levels: Record<string, number>;
  weakest: string | null;
  /** Enough sessions to rank. */
  judged: boolean;
}

export interface TeamInsights {
  success: true;
  target: number;
  targets: number[];
  skills: Skill[];
  /** Skill id -> the team's average level (members with enough sessions). */
  team: Record<string, number>;
  members: MemberInsight[];
  /** Coaching guidelines, each with the numbers behind it. */
  guidelines: string[];
}

/** A custom buyer kept to practise against again. Blank text fields are not stored. */
export interface SavedProspect {
  id: number;
  name: string;
  profile: Partial<CustomBuyer> & { name: string };
  /** Seconds since epoch. */
  created_at: number;
}

export interface AccountExport extends AccountMe {
  skills: SkillEntry[];
  prospects: SavedProspect[];
  words: SavedWords[];
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
