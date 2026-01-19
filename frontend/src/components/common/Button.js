/** Reusable button component with customizable styles and states */
import React from "react";

const Button = ({
  onClick,
  children,
  className = "btn-primary",
  disabled = false,
  type = "button",
}) => {
  return (
    <button
      type={type}
      onClick={onClick}
      className={className}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

export default Button;
