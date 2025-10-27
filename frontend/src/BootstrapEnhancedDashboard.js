import React, { useState, useEffect } from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import "./BootstrapDashboard.css";

const BootstrapEnhancedDashboard = () => {
  const [currentView, setCurrentView] = useState("dashboard");
  const [userProgress, setUserProgress] = useState(null);
  const [availablePersonas, setAvailablePersonas] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [sessionAnalysis, setSessionAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState("");

  // Mock user ID - in production this would come from authentication
  const userId = "demo_user_123";

  useEffect(() => {
    initializeUserData();
  }, []); // Intentionally empty - initializeUserData is stable

  // Fallback data for immediate display
  const fallbackPersonas = [
    {
      name: "Mary",
      description:
        "Professional sales manager with 10+ years experience in B2B sales. Specializes in objection handling and closing techniques.",
      personality_traits: ["Professional", "Direct", "Results-Oriented"],
      communication_style: "Professional Communication",
    },
    {
      name: "Jake",
      description:
        "Experienced enterprise sales representative focused on relationship building and consultative selling approaches.",
      personality_traits: ["Professional", "Friendly", "Consultative"],
      communication_style: "Professional Communication",
    },
    {
      name: "Sarah",
      description:
        "Senior account executive specializing in complex sales cycles and strategic account management.",
      personality_traits: ["Professional", "Strategic", "Detail-Oriented"],
      communication_style: "Professional Communication",
    },
    {
      name: "David",
      description:
        "Sales training specialist with expertise in role-playing scenarios and skill development exercises.",
      personality_traits: ["Professional", "Encouraging", "Analytical"],
      communication_style: "Professional Communication",
    },
  ];

  const fallbackProgress = {
    total_sessions: 0,
    training_hours: "0.0",
    skills_mastered: 0,
    average_rating: "0.0",
  };

  const initializeUserData = async () => {
    try {
      setLoading(true);
      setLoadingStatus("Initializing dashboard...");
      setLoadingProgress(15);

      // Immediately show fallback data for better UX
      setAvailablePersonas(fallbackPersonas);
      setUserProgress(fallbackProgress);
      setLoadingProgress(40);
      setLoadingStatus("Loading your progress...");

      // Use shorter timeouts and parallel requests
      const requestTimeout = (promise, timeout = 2000) => {
        return Promise.race([
          promise,
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("Request timeout")), timeout)
          ),
        ]);
      };

      setLoadingProgress(60);
      setLoadingStatus("Connecting to training system...");

      // Parallel requests with timeout protection
      const requests = [
        requestTimeout(
          fetch(`/api/v2/progress/initialize?user_id=${userId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
          })
        ).catch(() => null),

        requestTimeout(
          fetch(`/api/v2/progress/${userId}/dashboard`).then((res) =>
            res.ok ? res.json() : null
          )
        ).catch(() => null),

        requestTimeout(
          fetch("/api/v2/personas").then((res) => (res.ok ? res.json() : null))
        ).catch(() => null),
      ];

      setLoadingProgress(85);
      setLoadingStatus("Finalizing setup...");

      const [, progressData, personasData] = await Promise.allSettled(requests);

      // Update with real data if available, keep fallback otherwise
      if (progressData.status === "fulfilled" && progressData.value) {
        setUserProgress(progressData.value);
      }

      if (personasData.status === "fulfilled" && personasData.value?.personas) {
        setAvailablePersonas(personasData.value.personas);
      }

      setLoadingProgress(100);
      setLoadingStatus("Ready!");

      // Minimal delay for smooth transition
      await new Promise((resolve) => setTimeout(resolve, 200));
    } catch (error) {
      console.error("Error initializing user data:", error);
      setLoadingStatus("Ready with offline mode");
      // Keep fallback data on error
    } finally {
      setLoading(false);
    }
  };

  const startTrainingSession = async (persona) => {
    try {
      setLoading(true);
      const response = await fetch("/api/v2/personas/start-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, persona_name: persona.name }),
      });

      if (response.ok) {
        const sessionData = await response.json();
        setActiveSession(sessionData);
        setMessages([]);
        setCurrentView("training");
      }
    } catch (error) {
      console.error("Error starting session:", error);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim() || !activeSession) return;

    const userMessage = {
      role: "user",
      content: currentMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setCurrentMessage("");

    try {
      const response = await fetch("/api/v2/personas/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMessage,
          user_id: userId,
          session_id: activeSession.session_id,
          persona_name: activeSession.persona_name,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const personaMessage = {
          role: "persona",
          content: data.response,
          timestamp: new Date().toISOString(),
          feedback: data.feedback,
        };
        setMessages((prev) => [...prev, personaMessage]);
      }
    } catch (error) {
      console.error("Error sending message:", error);
    }
  };

  const endSession = async (rating) => {
    try {
      setLoading(true);
      const response = await fetch("/api/v2/personas/end-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          session_id: activeSession.session_id,
          persona_name: activeSession.persona_name,
          rating: rating,
        }),
      });

      if (response.ok) {
        const analysis = await response.json();
        setSessionAnalysis(analysis);
        setCurrentView("feedback");
      }
    } catch (error) {
      console.error("Error ending session:", error);
    } finally {
      setLoading(false);
    }
  };

  const renderDashboard = () => (
    <div className="container-fluid py-4">
      {/* Header */}
      <div className="row mb-4">
        <div className="col-12 text-center">
          <h1 className="display-4 fw-bold text-light mb-3">
            <i
              className="fas fa-chart-line me-3"
              style={{ color: "var(--success-color)" }}
            ></i>
            AI Sales Training Dashboard
          </h1>
          <p className="lead text-muted">
            Track your progress and improve your sales skills
          </p>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="row mb-5">
        <div className="col-12">
          <div className="card card-custom">
            <div className="card-header card-header-custom">
              <h5 className="mb-0">
                <i className="fas fa-chart-bar me-2"></i>Progress Overview
              </h5>
            </div>
            <div className="card-body">
              <div className="row">
                <div className="col-md-3 col-6 mb-3">
                  <div className="stat-card">
                    <div className="stat-value">
                      {userProgress?.total_sessions || 0}
                    </div>
                    <div className="stat-label">Total Sessions</div>
                  </div>
                </div>
                <div className="col-md-3 col-6 mb-3">
                  <div className="stat-card">
                    <div className="stat-value">
                      {userProgress?.training_hours || "0.0"}
                    </div>
                    <div className="stat-label">Training Hours</div>
                  </div>
                </div>
                <div className="col-md-3 col-6 mb-3">
                  <div className="stat-card">
                    <div className="stat-value">
                      {userProgress?.skills_mastered || 0}
                    </div>
                    <div className="stat-label">Skills Mastered</div>
                  </div>
                </div>
                <div className="col-md-3 col-6 mb-3">
                  <div className="stat-card">
                    <div className="stat-value">
                      {userProgress?.average_rating || "0.0"}
                    </div>
                    <div className="stat-label">Average Rating</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Available Personas */}
      <div className="row">
        <div className="col-12">
          <h3 className="text-light mb-4">
            <i className="fas fa-users me-2"></i>Choose Your Training Partner
          </h3>
          <div className="row">
            {availablePersonas.map((persona, index) => (
              <div
                key={persona.name || index}
                className="col-lg-4 col-md-6 mb-4"
              >
                <div
                  className="persona-card fade-in-up"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <h5 className="persona-title">{persona.name}</h5>
                    <span className="badge persona-badge">
                      {persona.personality_traits?.[0] || "Professional"}
                    </span>
                  </div>
                  <p className="persona-communication mb-2">
                    <i className="fas fa-briefcase me-1"></i>
                    {persona.communication_style ||
                      "Professional Communication"}
                  </p>
                  <p className="persona-description mb-3">
                    {persona.description}
                  </p>
                  <button
                    className="btn btn-custom-primary w-100"
                    onClick={() => startTrainingSession(persona)}
                    disabled={loading}
                  >
                    <i className="fas fa-play me-2"></i>
                    Start Training Session
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderTraining = () => (
    <div className="container-fluid py-4">
      {/* Training Header */}
      <div className="row mb-4">
        <div className="col-12">
          <div className="card card-custom">
            <div className="card-header card-header-custom d-flex justify-content-between align-items-center">
              <div>
                <h5 className="mb-0">
                  <i className="fas fa-comments me-2"></i>
                  Training Session: {activeSession?.persona_name}
                </h5>
              </div>
              <div>
                <button
                  className="btn btn-outline-light btn-sm me-2"
                  onClick={() => setCurrentView("dashboard")}
                >
                  <i className="fas fa-arrow-left me-1"></i>Back
                </button>
              </div>
            </div>
            <div className="card-body">
              <p className="mb-0 text-muted">
                <i className="fas fa-info-circle me-2"></i>
                Practice your sales skills with {activeSession?.persona_name}.
                Ask questions, handle objections, and receive real-time
                feedback.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Chat Interface */}
      <div className="row">
        <div className="col-12">
          <div className="chat-container">
            <div className="chat-messages">
              {messages.map((message, index) => (
                <div key={index} className="d-flex mb-3">
                  <div
                    className={`message-bubble ${
                      message.role === "user"
                        ? "message-user ms-auto"
                        : "message-persona me-auto"
                    }`}
                  >
                    <div className="fw-bold mb-1">
                      {message.role === "user" ? (
                        <>
                          <i className="fas fa-user me-2"></i>You
                        </>
                      ) : (
                        <>
                          <i className="fas fa-robot me-2"></i>
                          {activeSession?.persona_name}
                        </>
                      )}
                    </div>
                    <p className="mb-0">{message.content}</p>
                    {message.feedback && (
                      <div
                        className="mt-2 p-2 rounded"
                        style={{ background: "rgba(34, 197, 94, 0.1)" }}
                      >
                        <small className="text-success">
                          <i className="fas fa-lightbulb me-1"></i>
                          {message.feedback}
                        </small>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="chat-input-area">
              <div className="input-group">
                <input
                  type="text"
                  className="form-control form-control-lg"
                  placeholder="Type your message..."
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                  style={{
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid var(--card-border)",
                    color: "var(--text-light)",
                  }}
                />
                <button
                  className="btn btn-custom-primary"
                  onClick={sendMessage}
                  disabled={!currentMessage.trim()}
                >
                  <i className="fas fa-paper-plane"></i>
                </button>
              </div>
              <div className="d-flex justify-content-center mt-3 gap-2">
                <button
                  className="btn btn-success btn-sm"
                  onClick={() => endSession("good")}
                >
                  <i className="fas fa-thumbs-up me-1"></i>Good Session
                </button>
                <button
                  className="btn btn-warning btn-sm"
                  onClick={() => endSession("average")}
                >
                  <i className="fas fa-meh me-1"></i>Average Session
                </button>
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => endSession("poor")}
                >
                  <i className="fas fa-thumbs-down me-1"></i>Poor Session
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderFeedback = () => (
    <div className="container-fluid py-4">
      {/* Feedback Header */}
      <div className="row mb-4">
        <div className="col-12 text-center">
          <h2 className="display-5 fw-bold text-light mb-3">
            <i
              className="fas fa-chart-pie me-3"
              style={{ color: "var(--success-color)" }}
            ></i>
            Session Analysis
          </h2>
          <p className="lead text-muted">
            Here's how you performed in your training session
          </p>
        </div>
      </div>

      {/* Analysis Results */}
      {sessionAnalysis && (
        <div className="row">
          <div className="col-12">
            <div className="card card-custom">
              <div className="card-header card-header-custom">
                <h5 className="mb-0">
                  <i className="fas fa-analytics me-2"></i>Performance Scores
                </h5>
              </div>
              <div className="card-body">
                <div className="row">
                  {sessionAnalysis.scores &&
                    Object.entries(sessionAnalysis.scores).map(
                      ([key, value], index) => (
                        <div key={index} className="col-md-3 col-6 mb-3">
                          <div className="stat-card">
                            <div className="stat-value">
                              {(value * 100).toFixed(0)}%
                            </div>
                            <div className="stat-label">
                              {key.replace("_", " ").toUpperCase()}
                            </div>
                            <div className="progress progress-custom mt-2">
                              <div
                                className="progress-bar progress-bar-custom"
                                style={{ width: `${value * 100}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>
                      )
                    )}
                </div>

                {/* Feedback Items */}
                {sessionAnalysis.feedback &&
                  sessionAnalysis.feedback.length > 0 && (
                    <div className="mt-4">
                      <h6 className="text-light mb-3">
                        <i className="fas fa-comments me-2"></i>Detailed
                        Feedback
                      </h6>
                      {sessionAnalysis.feedback.map((item, index) => (
                        <div
                          key={index}
                          className={`feedback-item p-3 ${
                            item.type || "positive"
                          }`}
                        >
                          <h6 className="fw-bold">{item.title}</h6>
                          <p className="mb-0">{item.message}</p>
                          {item.confidence && (
                            <small className="text-muted">
                              Confidence: {(item.confidence * 100).toFixed(0)}%
                            </small>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                <div className="text-center mt-4">
                  <button
                    className="btn btn-custom-primary btn-lg"
                    onClick={() => setCurrentView("dashboard")}
                  >
                    <i className="fas fa-redo me-2"></i>
                    Continue Training
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="enhanced-training-dashboard">
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg dashboard-navbar">
        <div className="container-fluid">
          <button className="navbar-brand border-0 bg-transparent">
            <i className="fas fa-graduation-cap"></i>
            AI Sales Training
          </button>
          <div className="navbar-nav ms-auto">
            <button
              className={`btn btn-custom-outline me-2 ${
                currentView === "dashboard" ? "active" : ""
              }`}
              onClick={() => setCurrentView("dashboard")}
            >
              <i className="fas fa-tachometer-alt me-1"></i>Dashboard
            </button>
            <button
              className={`btn btn-custom-outline me-2 ${
                currentView === "training" ? "active" : ""
              }`}
              disabled={!activeSession}
            >
              <i className="fas fa-chalkboard-teacher me-1"></i>Training
            </button>
            <button
              className={`btn btn-custom-outline ${
                currentView === "feedback" ? "active" : ""
              }`}
              disabled={!sessionAnalysis}
            >
              <i className="fas fa-chart-bar me-1"></i>Feedback
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main>
        {currentView === "dashboard" && renderDashboard()}
        {currentView === "training" && renderTraining()}
        {currentView === "feedback" && renderFeedback()}
      </main>

      {/* Loading Overlay */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <div className="loading-spinner"></div>
            <div className="loading-text">{loadingStatus}</div>
            <div className="progress progress-custom mb-3">
              <div
                className="progress-bar progress-bar-custom"
                style={{ width: `${loadingProgress}%` }}
              ></div>
            </div>
            <div className="text-muted">{loadingProgress}%</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BootstrapEnhancedDashboard;
