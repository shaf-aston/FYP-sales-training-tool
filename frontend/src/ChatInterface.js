import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import "./ChatInterface.css";
import personaGreetings from "./utils/personaGreetings";
import API_ENDPOINTS from "./config/apiConfig";

const ChatInterface = ({
  selectedPersona = null,
  onClose = () => {},
  isStandalone = false,
}) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const initializedRef = useRef(false);
  const loadingIntervalRef = useRef(null);
  const [, setLoadingDots] = useState(0);

  // Default to Mary if no persona selected, handle both string and object inputs
  const activePersona = useMemo(() => {
    if (!selectedPersona) {
      return {
        name: "Mary",
        age: 65,
        description:
          "65-year-old recently retired teacher interested in safe fitness options",
        background:
          "Recently retired teacher who walked regularly but hasn't done structured exercise in years. Cautious but motivated to start a safe fitness routine.",
      };
    }

    // If selectedPersona is a string (from URL params), convert to object
    if (typeof selectedPersona === "string") {
      const personaName =
        selectedPersona.charAt(0).toUpperCase() +
        selectedPersona.slice(1).toLowerCase();
      return {
        name: personaName,
        age: personaName === "Mary" ? 65 : 35, // Default ages
        description: `Sales training with ${personaName}`,
        background: `Training persona: ${personaName}`,
      };
    }

    // If selectedPersona is already an object, use it
    return selectedPersona;
  }, [selectedPersona]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // helper timeout
  const fetchWithTimeout = async (url, options = {}) => {
    const { timeout = 6000 } = options;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      return res;
    } finally {
      clearTimeout(id);
    }
  };

  // Build a friendly persona greeting; memoized and defensive
  const createPersonalizedGreeting = useCallback(
    (context) => {
      const persona = (context && context.persona_info) || {
        name: activePersona?.name || "Customer",
        age: activePersona?.age,
        background:
          activePersona?.background ||
          "I'm looking to understand if your training is a good fit for me.",
      };

      return (
        personaGreetings[persona.name] ||
        `Hello! I'm ${persona.name}. ${persona.background}`
      );
    },
    [activePersona]
  );

  const initializeChat = useCallback(async () => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    setSessionId(`session_${Date.now()}_${activePersona.name}`);

    try {
      setIsLoading(true);

      const cacheKey = `persona_context_${activePersona.name}`;

      // Show animated loading bubble while model initializes
      const loadingId = `loading_${Date.now()}`;
      setMessages([
        {
          id: loadingId,
          sender: "persona",
          content: "Loading model...",
          timestamp: new Date(),
          persona: activePersona,
        },
      ]);

      // Start dots animation (0..5)
      loadingIntervalRef.current = setInterval(() => {
        setLoadingDots((d) => {
          const newDots = d >= 5 ? 0 : d + 1;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === loadingId
                ? {
                    ...m,
                    content: `Loading model${".".repeat(newDots)}`,
                    timestamp: new Date(),
                  }
                : m
            )
          );
          return newDots;
        });
      }, 500);

      // Fetch persona context in parallel (for personalized greeting and later use)
      const contextPromise = fetchWithTimeout(
        API_ENDPOINTS.GET_PERSONA_CONTEXT(activePersona.name),
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          timeout: 6000,
        }
      )
        .then((res) => (res.ok ? res.json() : null))
        .catch(() => null);

      // Trigger model load via greeting API
      const greetingPromise = fetchWithTimeout(API_ENDPOINTS.GET_GREETING, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        timeout: 30000, // allow more time for first-time model load
      })
        .then((res) => (res.ok ? res.json() : null))
        .catch(() => null);

      const [contextData, greetingData] = await Promise.all([
        contextPromise,
        greetingPromise,
      ]);

      // Build final initial message content
      const personalizedGreeting = contextData
        ? createPersonalizedGreeting(contextData.context)
        : null;

      const finalGreeting =
        (greetingData && greetingData.greeting) ||
        personalizedGreeting ||
        `Hello! I'm ${activePersona?.name || "your assistant"}. ${
          activePersona?.background || "How can I help you today?"
        }`;

      // Replace loading bubble with the real greeting
      setMessages([
        {
          id: Date.now(),
          sender: "persona",
          content: finalGreeting,
          timestamp: new Date(),
          persona: activePersona,
          context: contextData ? contextData.context : undefined,
        },
      ]);

      // Cache context if available
      if (contextData) {
        sessionStorage.setItem(cacheKey, JSON.stringify(contextData));
      }
    } catch (error) {
      console.error("Error initializing chat:", error);
    } finally {
      // Stop loading animation
      if (loadingIntervalRef.current) {
        clearInterval(loadingIntervalRef.current);
        loadingIntervalRef.current = null;
      }
      setLoadingDots(0);
      setIsLoading(false);
    }
  }, [activePersona, createPersonalizedGreeting]);

  useEffect(() => {
    if (activePersona) {
      initializeChat();
    }
  }, [activePersona, initializeChat]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (loadingIntervalRef.current) {
        clearInterval(loadingIntervalRef.current);
        loadingIntervalRef.current = null;
      }
    };
  }, []);

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      sender: "user",
      content: inputMessage.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);
    setIsTyping(true);

    try {
      const response = await fetch(API_ENDPOINTS.CHAT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage.content,
          user_id: "api_user",
          session_id: sessionId,
          persona_name: activePersona.name,
        }),
      });

      if (response.ok) {
        const responseData = await response.json();

        setTimeout(() => {
          const personaMessage = {
            id: Date.now() + 1,
            sender: "persona",
            content: responseData.response || responseData.persona_response,
            timestamp: new Date(),
            persona: activePersona,
            analysis: responseData.training_analysis,
            context: responseData.context_used,
            suggestions: responseData.training_analysis?.suggestions || [],
          };

          setMessages((prev) => [...prev, personaMessage]);
          setIsTyping(false);
        }, 1000); // Simulate typing delay
      }
    } catch (error) {
      console.error("Error sending message:", error);

      // Fallback response
      setTimeout(() => {
        const fallbackMessage = {
          id: Date.now() + 1,
          sender: "persona",
          content: "I'm sorry, I didn't catch that. Could you please repeat?",
          timestamp: new Date(),
          persona: activePersona,
        };

        setMessages((prev) => [...prev, fallbackMessage]);
        setIsTyping(false);
      }, 1000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className={`chat-interface ${isStandalone ? "standalone" : ""}`}>
      {/* Chat Header */}
      <div className="chat-header">
        <div className="persona-info">
          <div className="persona-avatar">
            <i className="fas fa-user-circle"></i>
          </div>
          <div className="persona-details">
            <h3>
              {(() => {
                const name = activePersona?.name || "Customer";
                const agePart =
                  typeof activePersona?.age === "number" &&
                  !Number.isNaN(activePersona.age)
                    ? `${activePersona.age}-year-old`
                    : "";
                const typePart = (activePersona?.type || "")
                  .toString()
                  .trim()
                  .toLowerCase();
                // Fallback if description is missing; avoid calling split on undefined
                const descWord = (activePersona?.description || "")
                  .toString()
                  .trim()
                  .split(" ")
                  .filter(Boolean)
                  .slice(-1)[0];

                const qualifier = [agePart, typePart || descWord]
                  .filter(Boolean)
                  .join(" ")
                  .trim();

                return (
                  <>
                    Chat with {name}
                    {qualifier ? ` - Your ${qualifier} client` : ""}
                  </>
                );
              })()}
            </h3>
            <p>
              Help {activePersona.name} create a safe and effective workout plan
            </p>
          </div>
        </div>
        {!isStandalone && (
          <button className="close-chat-btn" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        )}
      </div>

      {/* Chat Messages */}
      <div className="chat-messages">
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.sender}`}>
            <div className="message-content">
              <p>{message.content}</p>
              <small className="message-time">
                {formatTime(message.timestamp)}
              </small>
              {message.analysis && (
                <div className="message-analysis">
                  <small>
                    <i className="fas fa-lightbulb"></i>
                    {message.analysis.persona_reaction && (
                      <span>
                        Reaction:{" "}
                        {message.analysis.persona_reaction.reaction_type}
                      </span>
                    )}
                  </small>
                </div>
              )}
              {message.suggestions && message.suggestions.length > 0 && (
                <div className="training-suggestions">
                  <h5>
                    <i className="fas fa-graduation-cap"></i> Training Feedback
                  </h5>
                  {message.suggestions.map((suggestion, index) => (
                    <div key={index} className="suggestion-item">
                      <strong>{suggestion.category}:</strong>{" "}
                      {suggestion.suggestion}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="message persona">
            <div className="message-content typing">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <small>{activePersona.name} is typing...</small>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input */}
      <div className="chat-input-area">
        <div className="input-container">
          <textarea
            className="message-input-field"
            placeholder={`Type your ${
              activePersona?.name?.toLowerCase() === "mary"
                ? "fitness"
                : "sales"
            } question here...`}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            rows="2"
          />
          <button
            className="send-button"
            onClick={sendMessage}
            disabled={isLoading || !inputMessage.trim()}
          >
            {isLoading ? (
              <i className="fas fa-spinner fa-spin"></i>
            ) : (
              <i className="fas fa-paper-plane"></i>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
