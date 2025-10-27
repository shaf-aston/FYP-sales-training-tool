import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

const API_BASE =
  process.env.NODE_ENV === "production" ? "" : "http://localhost:8000";

function LegacyChatInterface() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [initialGreeting, setInitialGreeting] = useState("");
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Fetch initial greeting
    const fetchGreeting = async () => {
      try {
        const response = await axios.get(`${API_BASE}/api/greeting`);
        const greeting = response.data.greeting;
        setInitialGreeting(greeting);
        setMessages([
          {
            id: 1,
            text: greeting,
            sender: "mary",
            timestamp: new Date(),
          },
        ]);
      } catch (error) {
        console.error("Error fetching greeting:", error);
        setMessages([
          {
            id: 1,
            text: "Hi! I'm Mary. I'm having trouble connecting right now, but I'd love to chat about fitness!",
            sender: "mary",
            timestamp: new Date(),
          },
        ]);
      }
    };

    fetchGreeting();
  }, []);

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      id: messages.length + 1,
      text: inputValue,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, {
        message: inputValue,
      });

      const maryMessage = {
        id: messages.length + 2,
        text: response.data.response,
        sender: "mary",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, maryMessage]);
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage = {
        id: messages.length + 2,
        text: "I'm having trouble responding right now. Please try again in a moment.",
        sender: "mary",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
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

  return (
    <div className="legacy-chat-interface">
      <header className="App-header">
        <h1>Chat with Mary - Your 65-year-old Fitness Client</h1>
        <p>Help Mary create a safe and effective workout plan</p>
      </header>

      <main className="chat-container">
        <div className="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${
                message.sender === "user" ? "user-message" : "mary-message"
              }`}
            >
              <div className="message-content">{message.text}</div>
              <div className="message-time">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message mary-message">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your fitness question here..."
              className="chat-input"
              rows={1}
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={!inputValue.trim() || isLoading}
              className="send-button"
            >
              Send
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default LegacyChatInterface;
