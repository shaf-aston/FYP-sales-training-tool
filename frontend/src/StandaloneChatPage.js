import React from "react";
import ChatInterface from "./ChatInterface";
import Header from "./Header";
import "./ChatInterface.css";
import "./EnhancedTrainingDashboard.css";

const StandaloneChatPage = ({ onSwitchInterface = () => {} }) => {
  return (
    <div className="standalone-chat-page">
      <Header
        leftItems={[]}
        currentInterface={"chat"}
        onSwitchInterface={onSwitchInterface}
      />
      <ChatInterface isStandalone={true} />
    </div>
  );
};

export default StandaloneChatPage;
