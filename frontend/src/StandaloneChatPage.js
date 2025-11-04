import React from "react";
import { useNavigate } from "react-router-dom";
import ChatInterface from "./ChatInterface";
import Header from "./Header";
import "./ChatInterface.css";
import "./EnhancedTrainingDashboard.css";

const StandaloneChatPage = ({
  onSwitchInterface = () => {},
  selectedPersona = null,
  isGeneralChat = false,
}) => {
  const navigate = useNavigate();

  const handleTabChange = (view) => {
    if (view === "dashboard") {
      navigate("/dashboard");
    } else if (view === "training") {
      if (selectedPersona) {
        navigate(`/training/${selectedPersona.toLowerCase()}`);
      } else {
        navigate("/training");
      }
    } else if (view === "feedback") {
      navigate("/feedback");
    } else if (view === "general-chat") {
      navigate("/general-chat");
    }
  };

  return (
    <div className="enhanced-training-dashboard">
      <Header
        leftItems={[
          {
            label: "Dashboard",
            active: false,
            onClick: () => handleTabChange("dashboard"),
          },
          {
            label: "Training",
            active: false,
            onClick: () => handleTabChange("training"),
          },
          {
            label: "Feedback",
            active: false,
            onClick: () => handleTabChange("feedback"),
          },
          {
            label: "General Chat",
            active: isGeneralChat,
            onClick: () => handleTabChange("general-chat"),
          },
        ]}
        currentInterface={"chat"}
        onSwitchInterface={onSwitchInterface}
      />

      <main className="dashboard-content">
        <ChatInterface
          isStandalone={true}
          selectedPersona={selectedPersona}
          isGeneralChat={isGeneralChat}
        />
      </main>
    </div>
  );
};

export default StandaloneChatPage;
