/**Simple chat hook for messaging*/
import { useState, useEffect, useRef } from "react";
import trainingService from "../services/trainingService";

const generateUUID = () =>
  crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`;

const useChat = (scenarioType) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [phase, setPhase] = useState("intent");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const hasInitialized = useRef(false);

  // Initialize session
  useEffect(() => {
    if (!scenarioType || hasInitialized.current) return;
    hasInitialized.current = true;

    const initSession = async () => {
      try {
        setIsLoading(true);
        const response = await trainingService.startSession(scenarioType);
        setSessionId(response.session_id);
        setMessages([
          {
            id: generateUUID(),
            type: "system",
            content: "Session started. What would you like to discuss?",
          },
        ]);
      } catch (err) {
        setError("Failed to start session");
      } finally {
        setIsLoading(false);
      }
    };

    initSession();
  }, [scenarioType]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !sessionId || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage("");

    setMessages((prev) => [
      ...prev,
      { id: generateUUID(), type: "user", content: userMessage },
    ]);

    try {
      setIsLoading(true);
      const response = await trainingService.sendQuestion(
        sessionId,
        userMessage,
      );

      setMessages((prev) => [
        ...prev,
        {
          id: generateUUID(),
          type: "assistant",
          content: response.response,
        },
      ]);

      setPhase(response.phase);
    } catch (err) {
      setError("Failed to send message");
    } finally {
      setIsLoading(false);
    }
  };

  return {
    messages,
    inputMessage,
    sessionId,
    phase,
    isLoading,
    error,
    handleInputChange: (e) => setInputMessage(e.target.value),
    handleSendMessage,
    clearError: () => setError(null),
  };
};

export default useChat;
