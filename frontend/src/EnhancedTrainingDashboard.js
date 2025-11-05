import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import "bootstrap/dist/css/bootstrap.min.css";
import "./EnhancedTrainingDashboard.css";
import VoiceChat from "./VoiceChat";
import ChatInterface from "./ChatInterface";
import Header from "./Header";

// Note: Reusable UI components are defined in the CSS and markup below.

const EnhancedTrainingDashboard = ({
  onSwitchInterface = () => {},
  selectedPersona = null,
  viewMode = "dashboard",
}) => {
  const navigate = useNavigate();
  const [currentView, setCurrentView] = useState(viewMode);
  const [userProgress, setUserProgress] = useState(null);
  const [availablePersonas, setAvailablePersonas] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [sessionAnalysis, setSessionAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [messages, setMessages] = useState([]);
  const [selectedPersonaForChat, setSelectedPersonaForChat] = useState(null);
  const [, setSelectedPersonaContext] = useState(null);

  // Mock user ID - in production this would come from authentication
  const userId = "demo_user_123";

  // Helper: fetch with timeout
  const fetchWithTimeout = async (resource, options = {}) => {
    const { timeout = 6000 } = options;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(resource, {
        ...options,
        signal: controller.signal,
      });
      return response;
    } finally {
      clearTimeout(id);
    }
  };

  const initializeUserData = useCallback(async () => {
    const progressKey = `dashboard_progress_${userId}`;
    const personasKey = `personas_cache`;

    // 1) Try cache first for instant paint
    try {
      const cachedProgress = sessionStorage.getItem(progressKey);
      const cachedPersonas = sessionStorage.getItem(personasKey);

      if (cachedProgress) {
        setUserProgress(JSON.parse(cachedProgress));
      }
      if (cachedPersonas) {
        const parsed = JSON.parse(cachedPersonas);
        if (parsed?.personas) setAvailablePersonas(parsed.personas);
      }

      // If we had cache, avoid blocking overlay and refresh in background
      const shouldBlock = !(cachedProgress && cachedPersonas);
      if (shouldBlock) {
        setLoading(true);
        setLoadingStatus("Initializing dashboard...");
        setLoadingProgress(10);
      }

      // 2) Initialize on server (non-blocking if cached)
      const progressInit = fetchWithTimeout(
        `/api/v2/progress/initialize?user_id=${userId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          timeout: 5000,
        }
      );

      // 3) Fetch latest progress and personas in parallel
      if (shouldBlock) {
        setLoadingStatus("Loading your progress...");
        setLoadingProgress(50);
      }

      const progressDataPromise = fetchWithTimeout(
        `/api/v2/progress/${userId}/dashboard`,
        { timeout: 6000 }
      ).then((res) => (res.ok ? res.json() : null));

      if (shouldBlock) {
        setLoadingStatus("Loading training partners...");
        setLoadingProgress(75);
      }

      const personasDataPromise = fetchWithTimeout(`/api/v2/personas`, {
        timeout: 6000,
      }).then((res) => (res.ok ? res.json() : null));

      const [, progressData, personasData] = await Promise.allSettled([
        progressInit,
        progressDataPromise,
        personasDataPromise,
      ]);

      if (shouldBlock) {
        setLoadingStatus("Finalizing setup...");
        setLoadingProgress(90);
      }

      if (progressData.status === "fulfilled" && progressData.value) {
        setUserProgress(progressData.value);
        sessionStorage.setItem(progressKey, JSON.stringify(progressData.value));
      }

      if (personasData.status === "fulfilled" && personasData.value) {
        setAvailablePersonas(personasData.value.personas);
        sessionStorage.setItem(personasKey, JSON.stringify(personasData.value));
      }

      if (shouldBlock) {
        setLoadingProgress(100);
        setLoadingStatus("Ready!");
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
    } catch (error) {
      console.error("Error initializing user data:", error);
      setLoadingStatus("Error loading dashboard");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  // Kick off initialization (placed after declaration to avoid TDZ)
  useEffect(() => {
    initializeUserData();
  }, [initializeUserData]);

  const startTrainingSession = useCallback(
    async (personaName) => {
      // Navigate to training URL with persona
      navigate(`/training/${personaName.toLowerCase()}`);
    },
    [navigate]
  );

  // Handle selectedPersona from URL routing
  useEffect(() => {
    if (selectedPersona && viewMode === "training") {
      // Auto-start training session with the selected persona
      // Directly navigate here to avoid referencing the callback before
      // it's initialized when hot-reloading during development.
      navigate(`/training/${selectedPersona.toLowerCase()}`);
    }
  }, [selectedPersona, viewMode, navigate]);

  const preloadPersonaContext = async (personaName) => {
    try {
      const cacheKey = `persona_context_${personaName}`;
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) {
        const parsed = JSON.parse(cached);
        setSelectedPersonaContext(parsed);
        return parsed;
      }

      const res = await fetchWithTimeout(
        `/api/v2/personas/${personaName}/context`,
        { timeout: 6000 }
      );
      if (res.ok) {
        const ctx = await res.json();
        sessionStorage.setItem(cacheKey, JSON.stringify(ctx));
        setSelectedPersonaContext(ctx);
        return ctx;
      }
    } catch (e) {
      console.error("Failed to preload persona context", e);
    }
    return null;
  };

  const startChatSession = (persona) => {
    // Navigate to chat URL with persona
    navigate(`/chat/${persona.name.toLowerCase()}`);
  };

  const handleTabChange = async (view) => {
    // Navigate to dedicated URLs for each section
    if (view === "dashboard") {
      navigate("/dashboard");
    } else if (view === "training") {
      if (selectedPersona) {
        navigate(`/training/${selectedPersona.toLowerCase()}`);
      } else {
        navigate("/training");
      }
    } else if (view === "feedback") {
      navigate("/feedback");
    } else if (view === "general-chat") {
      navigate("/general-chat");
    }

    // Update current view for rendering
    setCurrentView(view);

    try {
      // Fire lightweight API calls on tab switches for testability and readiness
      if (view === "dashboard") {
        // refresh progress silently
        fetchWithTimeout(`/api/v2/progress/${userId}/dashboard`, {
          timeout: 6000,
        })
          .then((r) => (r.ok ? r.json() : null))
          .then((data) => {
            if (data) setUserProgress(data);
          })
          .catch(() => {});
      } else if (view === "training") {
        // Get training recommendations and, if session exists, preload its persona context
        fetchWithTimeout(`/api/v2/training/recommendations/${userId}`, {
          timeout: 6000,
        }).catch(() => {});
        if (activeSession?.persona?.name) {
          preloadPersonaContext(activeSession.persona.name);
        }
      } else if (view === "feedback") {
        // Prime analytics data (non-blocking)
        fetchWithTimeout(
          `/api/v2/feedback/analytics/dashboard?user_id=${userId}`,
          { timeout: 6000 }
        ).catch(() => {});
      }
    } catch (e) {
      // non-blocking
    }
  };

  const sendMessage = async (message) => {
    if (!activeSession || !message.trim()) return;

    try {
      setLoading(true);

      // Add user message to chat
      setMessages((prev) => [
        ...prev,
        {
          sender: "user",
          content: message,
          timestamp: new Date(),
        },
      ]);

      const response = await fetch("/api/v2/personas/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          message: message,
          session_id: activeSession.session_id,
        }),
      });

      if (response.ok) {
        const responseData = await response.json();

        // Add persona response to chat
        setMessages((prev) => [
          ...prev,
          {
            sender: "persona",
            content: responseData.persona_response,
            timestamp: new Date(),
            analysis: responseData.analysis,
            feedback: responseData.training_feedback,
          },
        ]);
      }
    } catch (error) {
      console.error("Error sending message:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceMessage = (voiceData) => {
    // Add user's transcribed speech to chat
    setMessages((prev) => [
      ...prev,
      {
        sender: "user",
        content: voiceData.userText,
        timestamp: new Date(),
        isVoice: true,
      },
    ]);

    // Add AI response to chat
    setMessages((prev) => [
      ...prev,
      {
        sender: "persona",
        content: voiceData.aiResponse,
        timestamp: new Date(),
        hasAudio: voiceData.hasAudio,
        isVoice: true,
      },
    ]);
  };

  const endTrainingSession = async (successRating = 5) => {
    if (!activeSession) return;

    try {
      setLoading(true);
      const response = await fetch("/api/v2/feedback/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: activeSession.session_id,
          user_id: userId,
          success_rating: successRating,
        }),
      });

      if (response.ok) {
        const analysisData = await response.json();
        setSessionAnalysis(analysisData);
        setCurrentView("feedback");

        // Refresh user progress
        await initializeUserData();
      }
    } catch (error) {
      console.error("Error ending training session:", error);
    } finally {
      setLoading(false);
    }
  };

  const renderDashboard = () => (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <h1>AI Sales Training Dashboard</h1>
        <p>Track your progress and improve your sales skills</p>
      </div>

      <div className="progress-overview">
        {userProgress ? (
          <>
            <div className="progress-card">
              <h3>Overall Progress</h3>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${userProgress.overall_progress.completion_percentage}%`,
                  }}
                ></div>
              </div>
              <p>
                {userProgress.overall_progress.completion_percentage.toFixed(1)}
                % Complete
              </p>
            </div>

            <div className="stats-grid">
              <div className="stat-card">
                <h4>Total Sessions</h4>
                <span className="stat-value">
                  {userProgress.session_statistics.total_sessions}
                </span>
              </div>
              <div className="stat-card">
                <h4>Training Hours</h4>
                <span className="stat-value">
                  {userProgress.session_statistics.total_hours.toFixed(1)}
                </span>
              </div>
              <div className="stat-card">
                <h4>Skills Mastered</h4>
                <span className="stat-value">
                  {userProgress.overall_progress.skills_mastered}
                </span>
              </div>
              <div className="stat-card">
                <h4>Average Rating</h4>
                <span className="stat-value">
                  {userProgress.session_statistics.average_success_rating.toFixed(
                    1
                  )}
                </span>
              </div>
            </div>

            <div className="skills-breakdown">
              <h3>Skills Progress</h3>
              <div className="skills-grid">
                {Object.entries(userProgress.skills_breakdown).map(
                  ([skill, data]) => (
                    <div key={skill} className="skill-card">
                      <h4>{skill.replace("_", " ").toUpperCase()}</h4>
                      <div className="skill-level">{data.current_level}</div>
                      <div className="skill-progress">
                        <div
                          className="skill-progress-bar"
                          style={{ width: `${data.progress_percentage}%` }}
                        ></div>
                      </div>
                      <p>
                        {data.progress_percentage.toFixed(1)}% to{" "}
                        {data.target_level}
                      </p>
                    </div>
                  )
                )}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="progress-card">
              <div
                className="loading-skeleton"
                style={{ height: 20, width: 180, marginBottom: 12 }}
              ></div>
              <div className="progress-bar">
                <div
                  className="loading-skeleton"
                  style={{ height: 12, width: "100%" }}
                ></div>
              </div>
              <div
                className="loading-skeleton"
                style={{ height: 16, width: 120, marginTop: 8 }}
              ></div>
            </div>
            <div className="stats-grid">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="stat-card">
                  <div
                    className="loading-skeleton"
                    style={{ height: 16, width: 120, margin: "0 auto 8px" }}
                  ></div>
                  <div
                    className="loading-skeleton"
                    style={{ height: 28, width: 80, margin: "0 auto" }}
                  ></div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Personas */}
      <div className="personas-section">
        <h3>Choose Your Training Partner</h3>
        <div className="personas-grid">
          {availablePersonas && availablePersonas.length > 0
            ? availablePersonas.map((persona) => (
                <div key={persona.name} className="persona-card">
                  <h4
                    role="button"
                    onClick={() => preloadPersonaContext(persona.name)}
                    title="Load persona context"
                  >
                    {persona.name}
                  </h4>
                  <p className="persona-type">
                    Type: {persona.type.replace("_", " ")}
                  </p>
                  <p className="persona-difficulty">
                    Difficulty: {persona.difficulty}
                  </p>
                  <p className="persona-background">{persona.background}</p>
                  <div className="persona-actions">
                    <button
                      className="start-session-btn"
                      onClick={() => startTrainingSession(persona.name)}
                      disabled={loading}
                    >
                      <i className="fas fa-play"></i>
                      Start Training
                    </button>
                    <button
                      className="chat-session-btn"
                      onClick={() => startChatSession(persona)}
                      disabled={loading}
                    >
                      <i className="fas fa-comments"></i>
                      Chat Now
                    </button>
                  </div>
                </div>
              ))
            : Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="persona-card">
                  <div
                    className="loading-skeleton"
                    style={{ height: 24, width: 160, marginBottom: 16 }}
                  ></div>
                  <div
                    className="loading-skeleton"
                    style={{ height: 14, width: 120, marginBottom: 8 }}
                  ></div>
                  <div
                    className="loading-skeleton"
                    style={{ height: 14, width: 140, marginBottom: 8 }}
                  ></div>
                  <div
                    className="loading-skeleton"
                    style={{ height: 60, width: "100%", marginBottom: 16 }}
                  ></div>
                  <div
                    className="loading-skeleton"
                    style={{ height: 44, width: "100%", marginBottom: 10 }}
                  ></div>
                  <div
                    className="loading-skeleton"
                    style={{ height: 44, width: "100%" }}
                  ></div>
                </div>
              ))}
        </div>
      </div>
    </div>
  );

  const renderTraining = () => (
    <div className="training-view">
      {!activeSession && (
        <div className="empty-state training-empty">
          <h2>Start a training session</h2>
          <p>Select a persona from the Dashboard to begin practicing.</p>
          <button
            className="start-session-btn"
            onClick={() => navigate("/dashboard")}
          >
            Go to Dashboard
          </button>
        </div>
      )}
      <div className="training-header">
        <h2>Training with {activeSession?.persona.name}</h2>
        <div className="persona-info">
          <p>
            <strong>Background:</strong> {activeSession?.persona.background}
          </p>
          <p>
            <strong>Key Concerns:</strong>{" "}
            {activeSession?.persona.concerns.join(", ")}
          </p>
          <p>
            <strong>Budget Range:</strong> {activeSession?.persona.budget_range}
          </p>
        </div>
      </div>

      <div className="chat-container">
        <div className="messages">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.sender}`}>
              <div className="message-content">
                <p>{message.content}</p>
                <small>{message.timestamp.toLocaleTimeString()}</small>
              </div>
              {message.feedback && (
                <div className="message-feedback">
                  <small>
                    <strong>Feedback:</strong>{" "}
                    {message.feedback.interaction_type} | Engagement:{" "}
                    {message.feedback.engagement_level}
                  </small>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="chat-input">
          <VoiceChat onVoiceMessage={handleVoiceMessage} />
          <MessageInput onSend={sendMessage} disabled={loading} />
        </div>
      </div>

      <div className="training-controls">
        <button
          className="end-session-btn good"
          onClick={() => endTrainingSession(8)}
          disabled={loading}
        >
          End Session (Good)
        </button>
        <button
          className="end-session-btn average"
          onClick={() => endTrainingSession(5)}
          disabled={loading}
        >
          End Session (Average)
        </button>
        <button
          className="end-session-btn poor"
          onClick={() => endTrainingSession(2)}
          disabled={loading}
        >
          End Session (Needs Work)
        </button>
      </div>
    </div>
  );

  const renderChat = () => (
    <div className="chat-view">
      <ChatInterface
        selectedPersona={selectedPersonaForChat}
        onClose={() => {
          if (selectedPersona) {
            navigate("/dashboard");
          } else {
            setCurrentView("dashboard");
          }
          setSelectedPersonaForChat(null);
        }}
        isStandalone={false}
      />
    </div>
  );

  const renderFeedback = () => (
    <div className="feedback-view">
      {!sessionAnalysis && (
        <div className="empty-state feedback-empty">
          <h2>No feedback yet</h2>
          <p>
            Finish a training session to see detailed analysis and next steps.
          </p>
          <button
            className="start-session-btn"
            onClick={() =>
              selectedPersona
                ? navigate("/dashboard")
                : setCurrentView("dashboard")
            }
          >
            Start Training
          </button>
        </div>
      )}
      <div className="feedback-header">
        <h2>Training Session Analysis</h2>
        <p>Here's how you performed and areas for improvement</p>
      </div>

      {sessionAnalysis && (
        <div className="analysis-results">
          <div className="overall-scores">
            <h3>Overall Performance</h3>
            <div className="scores-grid">
              {Object.entries(
                sessionAnalysis.feedback_analysis.overall_scores
              ).map(([key, value]) => (
                <div key={key} className="score-card">
                  <h4>{key.replace("_", " ").toUpperCase()}</h4>
                  <span className="score-value">
                    {typeof value === "number" ? value.toFixed(1) : value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="feedback-items">
            <h3>Detailed Feedback</h3>
            {sessionAnalysis.feedback_analysis.feedback_items.map(
              (item, index) => (
                <div
                  key={index}
                  className={`feedback-item ${item.feedback_type}`}
                >
                  <h4>{item.title}</h4>
                  <p>{item.description}</p>
                  <div className="feedback-details">
                    <p>
                      <strong>Example:</strong> {item.specific_example}
                    </p>
                    <p>
                      <strong>Suggestion:</strong> {item.improvement_suggestion}
                    </p>
                  </div>
                  <div className="confidence-score">
                    Confidence: {(item.confidence_score * 100).toFixed(0)}%
                  </div>
                </div>
              )
            )}
          </div>

          <div className="next-steps">
            <h3>Next Steps</h3>
            <ul>
              {sessionAnalysis.recommendations.immediate_focus.map(
                (rec, index) => (
                  <li key={index}>
                    {rec.area}: {rec.recommendations?.[0]}
                  </li>
                )
              )}
            </ul>
          </div>
        </div>
      )}

      <div className="feedback-controls">
        <button
          className="continue-training-btn"
          onClick={() => {
            if (selectedPersona) {
              navigate("/dashboard");
            } else {
              setCurrentView("dashboard");
            }
            setActiveSession(null);
            setSessionAnalysis(null);
            setMessages([]);
          }}
        >
          Continue Training
        </button>
      </div>
    </div>
  );

  return (
    <div className="enhanced-training-dashboard">
      <Header
        leftItems={[
          {
            label: "Dashboard",
            active: currentView === "dashboard",
            onClick: () => handleTabChange("dashboard"),
          },
          {
            label: "Training",
            active: currentView === "training",
            onClick: () => handleTabChange("training"),
          },
          {
            label: "Feedback",
            active: currentView === "feedback",
            onClick: () => handleTabChange("feedback"),
          },
          {
            label: "General Chat",
            active: currentView === "general-chat",
            onClick: () => handleTabChange("general-chat"),
          },
        ]}
        currentInterface={"enhanced"}
        onSwitchInterface={onSwitchInterface}
      />

      <main className="dashboard-content">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-content">
              <div className="loading-spinner"></div>
              <div className="loading-text">{loadingStatus}</div>
              <div className="loading-progress-bar">
                <div
                  className="loading-progress-fill"
                  style={{ width: `${loadingProgress}%` }}
                ></div>
              </div>
              <div className="loading-percentage">{loadingProgress}%</div>
            </div>
          </div>
        )}

        {currentView === "dashboard" && renderDashboard()}
        {currentView === "training" && renderTraining()}
        {currentView === "chat" && renderChat()}
        {currentView === "feedback" && renderFeedback()}
      </main>
    </div>
  );
};

// Message Input Component
const MessageInput = ({ onSend, disabled }) => {
  const [message, setMessage] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim()) {
      onSend(message);
      setMessage("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="message-input-form">
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Type your response..."
        disabled={disabled}
        className="message-input-field"
      />
      <button
        type="submit"
        disabled={disabled || !message.trim()}
        className="send-button"
      >
        Send
      </button>
    </form>
  );
};

export default EnhancedTrainingDashboard;
