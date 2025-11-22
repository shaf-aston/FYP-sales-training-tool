import React from "react";
import { Link } from "react-router-dom";
import PropTypes from "prop-types";
import "./Header.css";

const Header = ({ personas = [] }) => {
  return (
    <header className="app-header">
      <div className="header-container">
        <h1>AI Sales Training Platform</h1>
        <nav className="main-nav">
          <Link to="/dashboard" className="nav-link">
            Dashboard
          </Link>
          <Link to="/training" className="nav-link">
            Training
          </Link>
          <Link to="/feedback" className="nav-link">
            Feedback
          </Link>
          <Link to="/general-chat" className="nav-link">
            General Chat
          </Link>
          <div className="nav-divider">|</div>
          {personas.map((persona) => (
            <Link
              key={persona.name}
              to={`/chat/${persona.name.toLowerCase()}`}
              className="nav-link"
            >
              Chat with {persona.displayName || persona.name}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
};

Header.propTypes = {
  personas: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      displayName: PropTypes.string,
    })
  ),
};

export default Header;
