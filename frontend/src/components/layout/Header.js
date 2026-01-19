/** Application header - branding and main navigation links */
import React from "react";
import { Link, NavLink } from "react-router-dom";
import "./Header.css";

const Header = () => {
  return (
    <header className="app-header">
      <div className="header-left">
        <Link to="/" className="logo">
          KallApp
        </Link>
        <nav className="main-nav">
          <NavLink to="/core" className="nav-link">
            Core
          </NavLink>
          <NavLink to="/dashboard" className="nav-link">
            Dashboard
          </NavLink>
          <NavLink to="/learning" className="nav-link">
            Learning
          </NavLink>
          <NavLink to="/roleplays" className="nav-link">
            Practice
          </NavLink>
          <NavLink to="/analytics" className="nav-link">
            Analytics
          </NavLink>
        </nav>
      </div>
      <div className="header-right">
        <NavLink to="/progress" className="nav-link">
          My Progress
        </NavLink>
      </div>
    </header>
  );
};

export default Header;
