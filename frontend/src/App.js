import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useParams,
} from "react-router-dom";
import "./App.css";
import EnhancedTrainingDashboard from "./EnhancedTrainingDashboard";
import StandaloneChatPage from "./StandaloneChatPage";

// Page components for different views
const DashboardPage = () => {
  return <EnhancedTrainingDashboard viewMode="dashboard" />;
};

const TrainingPage = () => {
  return <EnhancedTrainingDashboard viewMode="training" />;
};

const FeedbackPage = () => {
  return <EnhancedTrainingDashboard viewMode="feedback" />;
};

const GeneralChatPage = () => {
  return <StandaloneChatPage isGeneralChat={true} />;
};

const ChatWithPersona = () => {
  const { persona } = useParams();
  return <StandaloneChatPage selectedPersona={persona} />;
};

const TrainWithPersona = () => {
  const { persona } = useParams();
  return (
    <EnhancedTrainingDashboard selectedPersona={persona} viewMode="training" />
  );
};

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          {/* Main dashboard route */}
          <Route path="/" element={<DashboardPage />} />

          {/* Dedicated routes for main sections */}
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/training" element={<TrainingPage />} />
          <Route path="/feedback" element={<FeedbackPage />} />
          <Route path="/general-chat" element={<GeneralChatPage />} />

          {/* Persona-specific routes */}
          <Route path="/chat/:persona" element={<ChatWithPersona />} />
          <Route path="/training/:persona" element={<TrainWithPersona />} />

          {/* Redirect unknown routes to dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
