import React from "react";
import { Link } from "react-router-dom";
import "./EnhancedTrainingDashboard.css";

const Header = ({
  leftItems = [],
  currentInterface = "enhanced",
  onSwitchInterface = () => {},
  useRouting = false,
}) => {
  return (
    <nav className="dashboard-nav">
      <div className="nav-left">
        {leftItems.map((item, idx) => (
          <React.Fragment key={idx}>
            {item.href ? (
              <Link
                to={item.href}
                className={`nav-link ${item.active ? "active" : ""}`}
              >
                {item.label}
              </Link>
            ) : (
              <button
                className={item.active ? "active" : ""}
                onClick={item.onClick}
                disabled={item.disabled}
              >
                {item.label}
              </button>
            )}
          </React.Fragment>
        ))}
      </div>
      {/* Only show interface switcher when useRouting is true */}
      {useRouting && (
        <div className="nav-right interface-switch">
          <Link
            to="/dashboard"
            className={`nav-interface-btn ${
              currentInterface === "enhanced" ||
              currentInterface === "training" ||
              currentInterface === "home"
                ? "active"
                : ""
            }`}
          >
            Training
          </Link>
          <Link
            to="/chat"
            className={`nav-interface-btn ${
              currentInterface === "chat" ? "active" : ""
            }`}
          >
            Chat
          </Link>
        </div>
      )}
    </nav>
  );
};

export default Header;
