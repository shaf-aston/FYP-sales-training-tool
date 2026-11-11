// The one seam between the UI and the Flask API. Components call `api.*` only;
// swap `createHttpApi` for a mock or another backend without touching features.

import { config } from "@/lib/config";
import type * as T from "./types";

/** Error thrown for any non-success response. `code` mirrors the server's error code. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    /** The form field the error is about (account sign-up), so the form can show it under that field. */
    readonly field?: string,
  ) {
    super(message);
  }

  /** The server forgot this session (restart or idle timeout). The code comes from backend/routes/_utils.py;
   *  TIMEOUT and NETWORK are made up here in the client. */
  get sessionExpired(): boolean {
    return this.code === "SESSION_EXPIRED";
  }

  /** The route needs a login and there is none (logged out elsewhere, or the login ran out). backend/auth.py */
  get loginRequired(): boolean {
    return this.code === "LOGIN_REQUIRED";
  }
}

/** The server's message for an API error, else the caller's fallback (never a raw JS error). */
export const errorText = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  /** Sent as JSON, or as multipart when it is FormData (the browser sets that content type). */
  body?: unknown;
  sessionId?: string | null;
  timeoutMs?: number;
  /** Another origin for this request (big uploads skip the Vercel rewrite); default the page's. */
  origin?: string;
}

async function request<R>(path: string, opts: RequestOptions = {}): Promise<R> {
  const form = opts.body instanceof FormData;
  const headers: Record<string, string> = {};
  if (opts.body !== undefined && !form) headers["Content-Type"] = "application/json";
  if (opts.sessionId) headers["X-Session-ID"] = opts.sessionId;

  const abort = new AbortController();
  const timer = opts.timeoutMs ? setTimeout(() => abort.abort(), opts.timeoutMs) : undefined;
  let res: Response;
  try {
    res = await fetch((opts.origin ?? config.apiBase) + path, {
      method: opts.method ?? (opts.body === undefined ? "GET" : "POST"),
      headers,
      body: opts.body === undefined ? undefined : form ? (opts.body as FormData) : JSON.stringify(opts.body),
      signal: abort.signal,
    });
  } catch {
    if (abort.signal.aborted) throw new ApiError("Response timed out. Give it another go.", 0, "TIMEOUT");
    throw new ApiError("Connection dropped. Check your internet.", 0, "NETWORK");
  } finally {
    clearTimeout(timer);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok || !data || data.error || data.success === false) {
    // Server faults get a plain message so internals never reach the screen. A 413 from a proxy has no JSON.
    const message =
      res.status === 413 && !data?.error
        ? "That's too big to send. Use a smaller file."
        : res.status >= 500 && !data?.code
          ? "Something went wrong on our side. Try again in a moment."
          : data?.error;
    throw new ApiError(message ?? `Request failed (${res.status})`, res.status, data?.code, data?.field);
  }
  return data as R;
}

/** A multipart body with the one upload the server reads as `file`. */
function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

/** Each call is named mode + action, after its path: buyChat = /api/buy/chat, sellReview = /api/sell/review. */
export function createHttpApi() {
  const chat = config.chatTimeoutMs;
  return {
    // Buy mode: the learner is the customer, the AI seller sells.
    buyInit: (sessionId?: string | null, productType?: string | null) =>
      request<T.InitRes>("/api/buy/init", { body: sessionId ? { session_id: sessionId } : productType ? { product_type: productType } : {} }),
    buyProducts: () => request<{ success: true; products: T.BuyProduct[] }>("/api/buy/products"),
    buyChat: (sid: string, message: string) => request<T.ChatRes>("/api/buy/chat", { body: { message }, sessionId: sid, timeoutMs: chat }),
    buyEdit: (sid: string, index: number, message: string) =>
      request<T.EditRes>("/api/buy/edit", { body: { index, message }, sessionId: sid, timeoutMs: chat }),
    buySteps: (sid: string) => request<{ success: true; steps: T.ScriptStep[] }>("/api/buy/steps", { sessionId: sid }),
    buyJump: (sid: string, step: string) => request<T.JumpRes>("/api/buy/jump", { body: { step }, sessionId: sid }),
    buyReset: (sid: string) => request<{ success: true }>("/api/buy/reset", { body: {}, sessionId: sid }),
    buyCoach: (sid: string, question: string, style: T.CoachStyle) =>
      request<{ success: true; answer: string }>("/api/buy/coach", { body: { question, style }, sessionId: sid, timeoutMs: chat }),
    buyQuizQuestion: (sid: string, type: T.QuizType) => request<T.QuizQuestion>(`/api/buy/quiz/question?type=${type}`, { sessionId: sid }),
    buyQuizAnswer: (sid: string, type: T.QuizType, answer: string) => {
      // Path and answer field per quiz type; must match the quiz routes in backend/routes/buy.py.
      const route = { stage: ["stage", "answer"], next_move: ["next-move", "response"], direction: ["direction", "explanation"] }[type];
      return request<T.QuizResult>(`/api/buy/quiz/${route[0]}`, { body: { [route[1]]: answer }, sessionId: sid, timeoutMs: chat });
    },

    // Sell mode: the learner is the salesperson, the AI buyer answers.
    sellProductGroups: () => request<{ success: true; groups: T.ProductGroups }>("/api/sell/product-groups"),
    sellPersonas: (productType: string) =>
      request<{ success: true; personas: T.Persona[] }>(`/api/sell/personas?product_type=${encodeURIComponent(productType)}`),
    sellInit: (difficulty: T.Difficulty, productType: string, pick: T.BuyerPick = {}) =>
      request<T.SellInitRes>("/api/sell/init", {
        body: { difficulty, product_type: productType, persona: pick.persona, objection: pick.objection, custom_buyer: pick.custom, replay: pick.replay },
        timeoutMs: chat,
      }),
    sellChat: (sid: string, message: string, showHints: boolean) =>
      request<T.SellChatRes>("/api/sell/chat", { body: { message, show_hints: showHints }, sessionId: sid, timeoutMs: chat }),
    sellReset: (sid: string) => request<{ success: true }>("/api/sell/reset", { body: {}, sessionId: sid }),
    sellEvaluate: (sid: string) => request<T.Evaluation>("/api/sell/evaluate", { body: {}, sessionId: sid, timeoutMs: chat }),
    sellSkills: () => request<T.SkillsRes>("/api/sell/skills"),
    sellReview: (sid: string) => request<T.Review>("/api/sell/review", { sessionId: sid, timeoutMs: chat }),
    sellRedo: (sid: string, turn: number, message: string) =>
      request<T.RedoRes>("/api/sell/redo", { body: { turn, message }, sessionId: sid, timeoutMs: chat }),
    sellQuizQuestion: (sid: string) => request<T.QuizQuestion>("/api/sell/quiz", { sessionId: sid }),
    sellQuizAnswer: (sid: string, turn: number, answer: string) =>
      request<T.QuizResult>("/api/sell/quiz", { body: { turn, answer }, sessionId: sid, timeoutMs: chat }),
    sellDrills: (sid: string | null) => request<{ success: true; drills: T.Drill[] }>("/api/sell/drills", { sessionId: sid }),

    // Calls: a real sales call the learner brings in, read by rules on the server (no AI).
    callsSample: () => request<{ success: true; text: string; filename: string }>("/api/calls/sample"),
    callsRead: (call: T.CallReq) => request<T.CallReadRes>("/api/calls/read", { body: call, timeoutMs: chat }),
    /** Replayed at `difficulty` (the one the learner picked), else the one read from the call. */
    callsReview: (call: T.CallReq, difficulty?: T.Difficulty) =>
      request<T.Review>("/api/calls/review", { body: { ...call, difficulty }, timeoutMs: chat }),
    /** A call recording -> a transcript with AI-labelled speakers. Uploaded straight to the API host (config.api). */
    callsTranscribe: (file: File) =>
      request<{ success: true; text: string; filename: string }>("/api/calls/transcribe", {
        body: fileForm(file),
        origin: config.api.uploadOrigin(),
        timeoutMs: config.calls.audio.timeoutMs,
      }),

    // SOP review: a team's sales SOP, what it covers, and how a real call follows it.
    sopSample: () => request<{ success: true; text: string; filename: string }>("/api/sop/sample"),
    /** The SOP as a file (PDF, Word, Markdown, text) or as pasted text. */
    sopRead: (sop: { file: File } | { text: string }) =>
      request<T.SopReadRes>("/api/sop/read", { body: "file" in sop ? fileForm(sop.file) : { text: sop.text }, timeoutMs: chat }),
    sopCheck: (stages: T.SopStage[], call: { text: string; rep?: string }) =>
      request<T.SopCheckRes>("/api/sop/check", { body: { stages, call }, timeoutMs: chat }),

    // Account: an optional login (a same-origin cookie) that keeps skill history and saved prospects.
    accountMe: () => request<T.AccountMe>("/api/account/me"),
    accountSignup: (body: { email: string; name: string; password: string }) => request<T.AccountMe>("/api/account/signup", { body }),
    accountLogin: (body: { email: string; password: string }) => request<T.AccountMe>("/api/account/login", { body }),
    accountLogout: () => request<{ success: true }>("/api/account/logout", { body: {} }),
    accountDelete: (password: string) => request<{ success: true }>("/api/account/delete", { body: { password } }),
    accountExport: () => request<T.AccountExport>("/api/account/export"),
    accountSkills: () => request<{ success: true; entries: T.SkillEntry[] }>("/api/account/skills"),
    accountSaveSkills: (entries: T.SkillEntry[]) => request<{ success: true; stored: number }>("/api/account/skills", { body: { entries } }),
    accountProspects: () => request<{ success: true; prospects: T.SavedProspect[] }>("/api/account/prospects"),
    accountSaveProspect: (profile: T.CustomBuyer) =>
      request<{ success: true; prospect: T.SavedProspect }>("/api/account/prospects", { body: { profile } }),
    accountDeleteProspect: (id: number) => request<{ success: true }>(`/api/account/prospects/${id}`, { method: "DELETE" }),

    // Team: a manager creates one and shares the invite code; reps join with it.
    team: () => request<{ success: true; team: T.Team | null; members: T.TeamMember[] }>("/api/team"),
    teamCreate: (name: string) => request<{ success: true; team: T.Team }>("/api/team/create", { body: { name } }),
    teamJoin: (code: string) => request<{ success: true; team: T.Team }>("/api/team/join", { body: { code } }),
    teamLeave: () => request<{ success: true }>("/api/team/leave", { body: {} }),
    teamRemove: (userId: number) => request<{ success: true }>("/api/team/remove", { body: { user_id: userId } }),
    teamNewCode: () => request<{ success: true; invite_code: string }>("/api/team/code", { body: {} }),

    // Shared
    /** The text as audio, or null when the server has no voice for it (the browser reads it instead). */
    speech: async (text: string): Promise<Blob | null> => {
      const res = await fetch(config.apiBase + "/api/speech", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) }).catch(() => null);
      return res?.status === 200 ? res.blob() : null;
    },
    feedback: (body: T.FeedbackReq) => request<{ success: true }>("/api/feedback", { body }),
    knowledge: () => request<{ success: true; data: T.KnowledgeData }>("/api/knowledge"),
    saveKnowledge: (data: T.KnowledgeData) => request<{ success: true }>("/api/knowledge", { body: data }),
    clearKnowledge: () => request<{ success: true }>("/api/knowledge", { method: "DELETE" }),
  };
}

type Api = ReturnType<typeof createHttpApi>;
export const api: Api = createHttpApi();
