const API_ENDPOINTS = {
  GET_PERSONA_CONTEXT: (personaName) => `/api/personas/${personaName}/context`,
  GET_GREETING: "/api/greeting",
  CHAT: "/api/chat",
  INITIALIZE_PROGRESS: (userId) =>
    `/api/v2/progress/initialize?user_id=${userId}`,
  GET_DASHBOARD_PROGRESS: (userId) => `/api/v2/progress/${userId}/dashboard`,
  GET_PERSONAS: "/api/v2/personas",
  GET_TRAINING_RECOMMENDATIONS: (userId) =>
    `/api/v2/training/recommendations/${userId}`,
  GET_FEEDBACK_ANALYTICS: (userId) =>
    `/api/v2/feedback/analytics/dashboard?user_id=${userId}`,
  PERSONA_CHAT: "/api/v2/personas/chat",
  ANALYZE_FEEDBACK: "/api/v2/feedback/analyze",
  VOICE_STATUS: "/api/voice-status",
  ADVANCED_AUDIO_ANALYSIS: "/api/advanced-audio-analysis",
  VOICE_CHAT: "/api/voice-chat",
};

export default API_ENDPOINTS;
