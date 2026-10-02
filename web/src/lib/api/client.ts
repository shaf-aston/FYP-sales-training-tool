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
  ) {
    super(message);
  }

  /** The server forgot this session (restart or idle timeout). */
  get sessionExpired(): boolean {
    return this.code === "SESSION_EXPIRED";
  }

  get timedOut(): boolean {
    return this.code === "TIMEOUT";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  sessionId?: string | null;
  timeoutMs?: number;
}

async function request<R>(path: string, opts: RequestOptions = {}): Promise<R> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.sessionId) headers["X-Session-ID"] = opts.sessionId;

  const abort = new AbortController();
  const timer = opts.timeoutMs ? setTimeout(() => abort.abort(), opts.timeoutMs) : undefined;
  let res: Response;
  try {
    res = await fetch(config.apiBase + path, {
      method: opts.method ?? (opts.body === undefined ? "GET" : "POST"),
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: abort.signal,
    });
  } catch {
    if (abort.signal.aborted) throw new ApiError("Response timed out. Give it another go.", 0, "TIMEOUT");
    throw new ApiError("Connection dropped. Check your internet and try again.", 0, "NETWORK");
  } finally {
    clearTimeout(timer);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok || !data || data.error || data.success === false) {
    // Server faults get a plain message so internals never reach the screen.
    const message = res.status >= 500 && !data?.code ? "Something went wrong on our side. Try again in a moment." : data?.error;
    throw new ApiError(message ?? `Request failed (${res.status})`, res.status, data?.code);
  }
  return data as R;
}

export function createHttpApi() {
  const chat = config.chatTimeoutMs;
  return {
    // Seller-bot session
    init: (sessionId?: string | null) => request<T.InitRes>("/api/init", { body: sessionId ? { session_id: sessionId } : {} }),
    chat: (sid: string, message: string) => request<T.ChatRes>("/api/chat", { body: { message }, sessionId: sid, timeoutMs: chat }),
    edit: (sid: string, index: number, message: string) =>
      request<T.EditRes>("/api/edit", { body: { index, message }, sessionId: sid, timeoutMs: chat }),
    reset: (sid: string) => request<{ success: true }>("/api/reset", { body: {}, sessionId: sid }),
    stages: (sid: string) => request<{ success: true; stages: string[] }>("/api/stages", { sessionId: sid }),
    setStage: (sid: string, stage: string) => request<T.BotState & { success: true }>("/api/stage", { body: { stage }, sessionId: sid }),
    setStrategy: (sid: string, strategy: string) =>
      request<T.BotState & { success: true }>("/api/strategy", { body: { strategy }, sessionId: sid }),
    publicConfig: () => request<T.PublicConfig>("/api/config"),
    askCoach: (sid: string, question: string, style: T.TrainingStyle) =>
      request<{ success: true; answer: string }>("/api/training/ask", { body: { question, style }, sessionId: sid, timeoutMs: chat }),

    // Quiz (seller-bot)
    quizQuestion: (sid: string, type: T.QuizType) => request<T.QuizQuestion>(`/api/test/question?type=${type}`, { sessionId: sid }),
    quizAnswer: (sid: string, type: T.QuizType, answer: string) => {
      const route = { stage: ["stage", "answer"], next_move: ["next-move", "response"], direction: ["direction", "explanation"] }[type];
      return request<T.QuizResult>(`/api/test/${route[0]}`, { body: { [route[1]]: answer }, sessionId: sid, timeoutMs: chat });
    },

    // Prospect practice
    productGroups: () => request<{ success: true; groups: T.ProductGroups }>("/api/prospect/product-groups"),
    prospectInit: (difficulty: T.Difficulty, productType: string) =>
      request<T.ProspectInitRes>("/api/prospect/init", { body: { difficulty, product_type: productType }, timeoutMs: chat }),
    prospectChat: (sid: string, message: string, showHints: boolean) =>
      request<T.ProspectChatRes>("/api/prospect/chat", { body: { message, show_hints: showHints }, sessionId: sid, timeoutMs: chat }),
    prospectReset: (sid: string) => request<{ success: true }>("/api/prospect/reset", { body: {}, sessionId: sid }),
    evaluate: (sid: string) => request<T.Evaluation>("/api/prospect/evaluate", { body: {}, sessionId: sid, timeoutMs: chat }),
    review: (sid: string) => request<T.Review>("/api/prospect/review", { sessionId: sid, timeoutMs: chat }),
    redo: (sid: string, turn: number, message: string) =>
      request<T.RedoRes>("/api/prospect/redo", { body: { turn, message }, sessionId: sid, timeoutMs: chat }),
    prospectQuizQuestion: (sid: string) => request<T.QuizQuestion>("/api/prospect/quiz", { sessionId: sid }),
    prospectQuizAnswer: (sid: string, turn: number, answer: string) =>
      request<T.QuizResult>("/api/prospect/quiz", { body: { turn, answer }, sessionId: sid, timeoutMs: chat }),
    drills: (sid: string | null) => request<{ success: true; drills: T.Drill[] }>("/api/prospect/drills", { sessionId: sid }),

    // Shared
    feedback: (body: T.FeedbackReq) => request<{ success: true }>("/api/feedback", { body }),
    knowledge: () => request<{ success: true; data: T.KnowledgeData }>("/api/knowledge"),
    saveKnowledge: (data: T.KnowledgeData) => request<{ success: true }>("/api/knowledge", { body: data }),
    clearKnowledge: () => request<{ success: true }>("/api/knowledge", { method: "DELETE" }),
  };
}

export type Api = ReturnType<typeof createHttpApi>;
export const api: Api = createHttpApi();
