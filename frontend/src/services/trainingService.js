/**Simple training API service*/
const API_BASE_URL = "http://localhost:8000";

class TrainingService {
  constructor() {
    this.baseURL = API_BASE_URL;
  }

  async request(endpoint, options = {}) {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async startSession() {
    const response = await this.request("/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: null,
        message: "Start training",
      }),
    });

    return {
      session_id: response.conversation_id,
      initial_message: response.response,
    };
  }

  async sendQuestion(sessionId, question) {
    const response = await this.request("/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: sessionId,
        message: question,
      }),
    });

    return {
      response: response.response,
      phase: response.phase || "intent",
      metadata: response.metadata || {},
    };
  }

  async endSession(sessionId) {
    return this.request(`/session/${sessionId}`, {
      method: "DELETE",
    });
  }
}

const trainingService = new TrainingService();
export default trainingService;
