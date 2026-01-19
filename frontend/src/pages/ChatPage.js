/**Simple chat page*/
import React from "react";
import { useParams } from "react-router-dom";
import TrainingChat from "../components/chat/TrainingChat";
import "./Pages.css";

const ChatPage = () => {
  const { scenario } = useParams();

  return (
    <div className="chat-page">
      <TrainingChat scenarioType={scenario || "sales"} />
    </div>
  );
};

export default ChatPage;
