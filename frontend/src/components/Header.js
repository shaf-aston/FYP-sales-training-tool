import React from "react";
import { Link } from "react-router-dom";
import "./Header.css";

const Header = () => {
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
          <Link to="/chat/mary" className="nav-link">
            Chat with Mary
          </Link>
          <Link to="/chat/jake" className="nav-link">
            Chat with Jake
          </Link>
          <Link to="/chat/sarah" className="nav-link">
            Chat with Sarah
          </Link>
          <Link to="/chat/david" className="nav-link">
            Chat with David
          </Link>
        </nav>
      </div>
    </header>
  );
};

export default Header;
