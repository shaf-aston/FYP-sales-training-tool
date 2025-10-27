import React, { useState } from "react";
import "./App.css";
import EnhancedTrainingDashboard from "./EnhancedTrainingDashboard";
import LegacyChatInterface from "./LegacyChatInterface";

function App() {
  const [currentInterface, setCurrentInterface] = useState("enhanced");

  return (
    <div className="App">
      <div className="interface-selector">
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

      {currentInterface === "enhanced" ? (
        <EnhancedTrainingDashboard />
      ) : (
        <LegacyChatInterface />
      )}
    </div>
  );
}

export default App;
