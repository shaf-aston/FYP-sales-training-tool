import React, { useState, useEffect } from "react";
import "./EnhancedTrainingDashboard.css";
import VoiceChat from "./VoiceChat";

const EnhancedTrainingDashboard = () => {
  const [currentView, setCurrentView] = useState("dashboard");
  const [userProgress, setUserProgress] = useState(null);
  const [availablePersonas, setAvailablePersonas] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [sessionAnalysis, setSessionAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [messages, setMessages] = useState([]);

  // Mock user ID - in production this would come from authentication
  const userId = "demo_user_123";

  useEffect(() => {
    initializeUserData();
  }, []);

  const initializeUserData = async () => {
    try {
      setLoading(true);
      setLoadingStatus("Initializing dashboard...");
      setLoadingProgress(10);

      // Step 1: Initialize user progress
      setLoadingStatus("Setting up your profile...");
      setLoadingProgress(25);

      const progressInit = fetch(
        `/api/v2/progress/initialize?user_id=${userId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );

      // Step 2: Load progress data
      setLoadingStatus("Loading your progress...");
      setLoadingProgress(50);

      const progressDataPromise = fetch(
        `/api/v2/progress/${userId}/dashboard`
      ).then((res) => (res.ok ? res.json() : null));

      // Step 3: Load personas
      setLoadingStatus("Loading training partners...");
      setLoadingProgress(75);

      const personasDataPromise = fetch("/api/v2/personas").then((res) =>
        res.ok ? res.json() : null
      );

      // Execute all requests in parallel for better performance
      const [progressInitialized, progressData, personasData] =
        await Promise.allSettled([
          progressInit,
          progressDataPromise,
          personasDataPromise,
        ]);

      // Step 4: Finalize setup
      setLoadingStatus("Finalizing setup...");
      setLoadingProgress(90);

      // Set progress data if available
      if (progressData.status === "fulfilled" && progressData.value) {
        setUserProgress(progressData.value);
      }

      // Set personas data if available
      if (personasData.status === "fulfilled" && personasData.value) {
        setAvailablePersonas(personasData.value.personas);
      }

      setLoadingProgress(100);
      setLoadingStatus("Ready!");

      // Brief delay to show completion
      await new Promise((resolve) => setTimeout(resolve, 500));
    } catch (error) {
      console.error("Error initializing user data:", error);
      setLoadingStatus("Error loading dashboard");
    } finally {
      setLoading(false);
    }
  };

  const startTrainingSession = async (personaName) => {
    try {
      setLoading(true);
      const response = await fetch("/api/v2/personas/start-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          persona_name: personaName,
          scenario: "initial_contact",
        }),
      });

      if (response.ok) {
        const sessionData = await response.json();
        setActiveSession(sessionData.session_data);
        setMessages([
          {
            sender: "persona",
            content: sessionData.initial_greeting,
            timestamp: new Date(),
          },
        ]);
        setCurrentView("training");
      }
    } catch (error) {
      console.error("Error starting training session:", error);
    } finally {
      setLoading(false);
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

      {userProgress && (
        <div className="progress-overview">
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
              {userProgress.overall_progress.completion_percentage.toFixed(1)}%
              Complete
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
        </div>
      )}

      <div className="personas-section">
        <h3>Choose Your Training Partner</h3>
        <div className="personas-grid">
          {availablePersonas.map((persona) => (
            <div key={persona.name} className="persona-card">
              <h4>{persona.name}</h4>
              <p className="persona-type">
                Type: {persona.type.replace("_", " ")}
              </p>
              <p className="persona-difficulty">
                Difficulty: {persona.difficulty}
              </p>
              <p className="persona-background">{persona.background}</p>
              <button
                className="start-session-btn"
                onClick={() => startTrainingSession(persona.name)}
                disabled={loading}
              >
                Start Training
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderTraining = () => (
    <div className="training-view">
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

  const renderFeedback = () => (
    <div className="feedback-view">
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
            setCurrentView("dashboard");
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
      <nav className="dashboard-nav">
        <button
          className={currentView === "dashboard" ? "active" : ""}
          onClick={() => setCurrentView("dashboard")}
        >
          Dashboard
        </button>
        <button
          className={currentView === "training" ? "active" : ""}
          onClick={() => setCurrentView("training")}
          disabled={!activeSession}
        >
          Training
        </button>
        <button
          className={currentView === "feedback" ? "active" : ""}
          onClick={() => setCurrentView("feedback")}
          disabled={!sessionAnalysis}
        >
          Feedback
        </button>
      </nav>

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
