import React, { useState } from "react";
import "./App.css";
import EnhancedTrainingDashboard from "./EnhancedTrainingDashboard";
import StandaloneChatPage from "./StandaloneChatPage";

function App() {
  const [currentInterface, setCurrentInterface] = useState("enhanced");

  return (
    <div className="App">
      {currentInterface === "enhanced" ? (
        <EnhancedTrainingDashboard onSwitchInterface={setCurrentInterface} />
      ) : currentInterface === "chat" ? (
        <StandaloneChatPage onSwitchInterface={setCurrentInterface} />
      ) : null}
    </div>
  );
}

export default App;
