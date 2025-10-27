import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import "./ChatInterface.css";

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

  // Default to Mary if no persona selected
  const activePersona = useMemo(
    () =>
      selectedPersona || {
        name: "Mary",
        age: 65,
        description:
          "65-year-old recently retired teacher interested in safe fitness options",
        background:
          "Recently retired teacher who walked regularly but hasn't done structured exercise in years. Cautious but motivated to start a safe fitness routine.",
      },
    [selectedPersona]
  );

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

  const initializeChat = useCallback(async () => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    setSessionId(`session_${Date.now()}_${activePersona.name}`);

    try {
      setIsLoading(true);

      const cacheKey = `persona_context_${activePersona.name}`;
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) {
        const contextData = JSON.parse(cached);
        const personalizedGreeting = createPersonalizedGreeting(
          contextData.context
        );
        setMessages([
          {
            id: Date.now(),
            sender: "persona",
            content: personalizedGreeting,
            timestamp: new Date(),
            persona: activePersona,
            context: contextData.context,
          },
        ]);
      } else {
        // Instant lightweight greeting while network fetch happens
        setMessages([
          {
            id: Date.now(),
            sender: "persona",
            content: `Hello! I'm ${activePersona.name}. ${activePersona.background}`,
            timestamp: new Date(),
            persona: activePersona,
          },
        ]);
      }

      // Refresh from network in background
      const response = await fetchWithTimeout(
        `/api/v2/personas/${activePersona.name}/context`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          timeout: 6000,
        }
      );
      if (response.ok) {
        const contextData = await response.json();
        sessionStorage.setItem(cacheKey, JSON.stringify(contextData));
        const personalizedGreeting = createPersonalizedGreeting(
          contextData.context
        );
        // Replace first message if it's a generic one
        setMessages((prev) => {
          if (prev.length === 1 && prev[0].sender === "persona") {
            return [
              {
                id: Date.now(),
                sender: "persona",
                content: personalizedGreeting,
                timestamp: new Date(),
                persona: activePersona,
                context: contextData.context,
              },
            ];
          }
          return prev;
        });
      }
    } catch (error) {
      console.error("Error initializing chat:", error);
    } finally {
      setIsLoading(false);
    }
  }, [activePersona]);

  useEffect(() => {
    if (activePersona) {
      initializeChat();
    }
  }, [activePersona, initializeChat]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const createPersonalizedGreeting = (context) => {
    const persona = context.persona_info;

    const greetings = {
      Mary: `Hello! I'm Mary. I'm ${persona.age} and recently retired from teaching. I'm interested in starting a fitness routine, but I want to make sure it's safe and appropriate for someone my age. I've heard good things about personal training - could you help me understand what that would involve?`,
      Jake: `Hi there. I'm Jake, and I'll be direct - I'm extremely busy running my company and I'm skeptical about fitness programs. I work 60+ hours a week and I need to see real, measurable results if I'm going to invest time and money in this. What can you show me?`,
      Sarah: `Hey! I'm Sarah, and I'm really interested in getting fit, but I need to be honest - I'm on a pretty tight budget as a recent graduate. I'm still paying off student loans, so I need to make sure I'm getting the best value for my money. What are my options?`,
      David: `Hi! I'm David, father of two teenagers. I'm interested in fitness, but my main concern is how this fits with my family life. I work full-time and want to set a good example for my kids. Do you have solutions that work for busy parents?`,
    };

    return (
      greetings[persona.name] ||
      `Hello! I'm ${persona.name}. ${persona.background}`
    );
  };

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
      const response = await fetch(
        `/api/v2/personas/${activePersona.name}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            persona_name: activePersona.name,
            user_message: userMessage.content,
            session_id: sessionId,
          }),
        }
      );

      if (response.ok) {
        const responseData = await response.json();

        setTimeout(() => {
          const personaMessage = {
            id: Date.now() + 1,
            sender: "persona",
            content: responseData.persona_response,
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
              Chat with {activePersona.name} - Your {activePersona.age}-year-old{" "}
              {activePersona.description.split(" ").slice(-1)[0]} Client
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
              activePersona.name.toLowerCase() === "mary" ? "fitness" : "sales"
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
