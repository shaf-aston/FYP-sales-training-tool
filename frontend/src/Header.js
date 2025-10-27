import React from "react";
import "./EnhancedTrainingDashboard.css";

const Header = ({
  leftItems = [],
  currentInterface = "enhanced",
  onSwitchInterface = () => {},
}) => {
  return (
    <nav className="dashboard-nav">
      <div className="nav-left">
        {leftItems.map((item, idx) => (
          <button
            key={idx}
            className={item.active ? "active" : ""}
            onClick={item.onClick}
            disabled={item.disabled}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="nav-right interface-switch">
        <button
          className={currentInterface === "enhanced" ? "active" : ""}
          onClick={() => onSwitchInterface("enhanced")}
        >
          Enhanced
        </button>
        <button
          className={currentInterface === "chat" ? "active" : ""}
          onClick={() => onSwitchInterface("chat")}
        >
          Direct Chat
        </button>
      </div>
    </nav>
  );
};

export default Header;
