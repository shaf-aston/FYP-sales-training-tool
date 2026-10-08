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
    // Buy mode: the learner is the customer, the AI seller sells.
    buyInit: (sessionId?: string | null) => request<T.InitRes>("/api/buy/init", { body: sessionId ? { session_id: sessionId } : {} }),
    buyChat: (sid: string, message: string) => request<T.ChatRes>("/api/buy/chat", { body: { message }, sessionId: sid, timeoutMs: chat }),
    buyEdit: (sid: string, index: number, message: string) =>
      request<T.EditRes>("/api/buy/edit", { body: { index, message }, sessionId: sid, timeoutMs: chat }),
    buyReset: (sid: string) => request<{ success: true }>("/api/buy/reset", { body: {}, sessionId: sid }),
    askCoach: (sid: string, question: string, style: T.TrainingStyle) =>
      request<{ success: true; answer: string }>("/api/buy/coach", { body: { question, style }, sessionId: sid, timeoutMs: chat }),
    buyQuizQuestion: (sid: string, type: T.QuizType) => request<T.QuizQuestion>(`/api/buy/quiz/question?type=${type}`, { sessionId: sid }),
    buyQuizAnswer: (sid: string, type: T.QuizType, answer: string) => {
      const route = { stage: ["stage", "answer"], next_move: ["next-move", "response"], direction: ["direction", "explanation"] }[type];
      return request<T.QuizResult>(`/api/buy/quiz/${route[0]}`, { body: { [route[1]]: answer }, sessionId: sid, timeoutMs: chat });
    },

    // Sell mode: the learner is the salesperson, the AI buyer answers.
    productGroups: () => request<{ success: true; groups: T.ProductGroups }>("/api/sell/product-groups"),
    personas: (productType: string) =>
      request<{ success: true; personas: T.Persona[] }>(`/api/sell/personas?product_type=${encodeURIComponent(productType)}`),
    sellInit: (difficulty: T.Difficulty, productType: string, pick: T.BuyerPick = {}) =>
      request<T.SellInitRes>("/api/sell/init", {
        body: { difficulty, product_type: productType, persona: pick.persona, objection: pick.objection },
        timeoutMs: chat,
      }),
    sellChat: (sid: string, message: string, showHints: boolean) =>
      request<T.SellChatRes>("/api/sell/chat", { body: { message, show_hints: showHints }, sessionId: sid, timeoutMs: chat }),
    sellReset: (sid: string) => request<{ success: true }>("/api/sell/reset", { body: {}, sessionId: sid }),
    evaluate: (sid: string) => request<T.Evaluation>("/api/sell/evaluate", { body: {}, sessionId: sid, timeoutMs: chat }),
    review: (sid: string) => request<T.Review>("/api/sell/review", { sessionId: sid, timeoutMs: chat }),
    redo: (sid: string, turn: number, message: string) =>
      request<T.RedoRes>("/api/sell/redo", { body: { turn, message }, sessionId: sid, timeoutMs: chat }),
    sellQuizQuestion: (sid: string) => request<T.QuizQuestion>("/api/sell/quiz", { sessionId: sid }),
    sellQuizAnswer: (sid: string, turn: number, answer: string) =>
      request<T.QuizResult>("/api/sell/quiz", { body: { turn, answer }, sessionId: sid, timeoutMs: chat }),
    drills: (sid: string | null) => request<{ success: true; drills: T.Drill[] }>("/api/sell/drills", { sessionId: sid }),

    // Shared
    feedback: (body: T.FeedbackReq) => request<{ success: true }>("/api/feedback", { body }),
    knowledge: () => request<{ success: true; data: T.KnowledgeData }>("/api/knowledge"),
    saveKnowledge: (data: T.KnowledgeData) => request<{ success: true }>("/api/knowledge", { body: data }),
    clearKnowledge: () => request<{ success: true }>("/api/knowledge", { method: "DELETE" }),
  };
}

export type Api = ReturnType<typeof createHttpApi>;
export const api: Api = createHttpApi();
