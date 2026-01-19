/** Error banner - displays dismissible error messages */
import React from "react";

const ErrorMessage = ({ message, onClear }) => {
  if (!message) return null;

  return (
    <div className="error-message-banner">
      <span>{message}</span>
      <button type="button" onClick={onClear} className="btn-close">
        ×
      </button>
    </div>
  );
};

export default ErrorMessage;
