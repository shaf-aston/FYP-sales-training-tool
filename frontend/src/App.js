import React, { useState } from "react";
import "./App.css";
import EnhancedTrainingDashboard from "./EnhancedTrainingDashboard";
import BootstrapEnhancedDashboard from "./BootstrapEnhancedDashboard";
import LegacyChatInterface from "./LegacyChatInterface";

function App() {
  const [currentInterface, setCurrentInterface] = useState("bootstrap");

  return (
    <div className="App">
      <div className="interface-selector">
        <button
          className={currentInterface === "bootstrap" ? "active" : ""}
          onClick={() => setCurrentInterface("bootstrap")}
        >
          Bootstrap Dashboard
        </button>
        <button
          className={currentInterface === "enhanced" ? "active" : ""}
          onClick={() => setCurrentInterface("enhanced")}
        >
          Enhanced Training Dashboard
        </button>
        <button
          className={currentInterface === "legacy" ? "active" : ""}
          onClick={() => setCurrentInterface("legacy")}
        >
          Legacy Chat Interface
        </button>
      </div>

      {currentInterface === "bootstrap" ? (
        <BootstrapEnhancedDashboard />
      ) : currentInterface === "enhanced" ? (
        <EnhancedTrainingDashboard />
      ) : (
        <LegacyChatInterface />
      )}
    </div>
  );
}

export default App;
