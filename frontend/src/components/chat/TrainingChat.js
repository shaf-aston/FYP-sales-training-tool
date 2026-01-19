/**Simple chat interface*/
import React, { useRef, useEffect } from "react";
import useChat from "../../hooks/useChat";
import MessageBubble from "./MessageBubble";
import MessageInput from "./MessageInput";
import ErrorMessage from "../common/ErrorMessage";

const TrainingChat = ({ scenarioType = "sales" }) => {
  const {
    messages,
    inputMessage,
    isLoading,
    phase,
    error,
    handleInputChange,
    handleSendMessage,
    clearError,
  } = useChat(scenarioType);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-interface">
      <div style={{ padding: "1rem", borderBottom: "1px solid #334155" }}>
        <h2>Phase: {phase}</h2>
      </div>

      <ErrorMessage message={error} onClear={clearError} />

      <div className="chat-messages">
        {messages &&
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
        <div ref={messagesEndRef} />
      </div>

      <MessageInput
        value={inputMessage}
        onChange={handleInputChange}
        onSubmit={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
};

export default TrainingChat;
