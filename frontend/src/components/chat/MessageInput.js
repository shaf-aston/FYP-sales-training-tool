/**Simple message input*/
import React from "react";

const MessageInput = ({ value, onChange, onSubmit, isLoading }) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (value.trim()) {
      onSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="chat-input-form">
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder="Type your message..."
        disabled={isLoading}
        className="chat-input"
      />
      <button type="submit" disabled={isLoading} className="btn-send">
        {isLoading ? "..." : "Send"}
      </button>
    </form>
  );
};

export default MessageInput;
