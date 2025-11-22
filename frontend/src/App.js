import React, { useState, useEffect } from "react";
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
import DeveloperDashboard from "./components/DeveloperDashboard";
import Header from "./components/Header";
import API_ENDPOINTS from "./config/apiConfig";

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
  const [personas, setPersonas] = useState([]);

  useEffect(() => {
    const fetchPersonas = async () => {
      try {
        const response = await fetch(API_ENDPOINTS.GET_PERSONAS);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setPersonas(data);
      } catch (error) {
        console.error("Failed to fetch personas:", error);
        setPersonas([]); // Set empty array on error
      }
    };

    fetchPersonas();
  }, []);

  return (
    <Router>
      <Header personas={personas} />
      <div className="App">
        <DeveloperDashboard />
        <Routes>
          <Route path="/" element={<DashboardPage />} />

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
