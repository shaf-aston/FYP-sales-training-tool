/** Chat inteface - individual chat messages */
import React from "react";
import DOMPurify from "dompurify";

const MessageBubble = ({ message }) => {
  const { type, content, feedback, data, coaching } = message;

  const sanitizedContent = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: ["b", "i", "em", "strong", "br"],
    ALLOWED_ATTR: [],
  });

  return (
    <div className={`message message-${type}`}>
      <div
        className="message-content"
        dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      />
      {coaching && (
        <div className="coaching-feedback">
          <span className="coaching-icon">💡</span> {coaching}
        </div>
      )}
    </div>
  );
};

export default MessageBubble;
