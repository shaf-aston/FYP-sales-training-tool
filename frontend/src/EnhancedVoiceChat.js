import React, { useState, useRef, useEffect } from "react";
import "./EnhancedVoiceChat.css";

const EnhancedVoiceChat = ({
  onVoiceMessage,
  isListening: externalListening,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState("");
  const [showAdvancedAnalysis, setShowAdvancedAnalysis] = useState(false);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [voiceStatus, setVoiceStatus] = useState({
    stt: { available: false, advanced_analysis_available: false },
    tts: { available: false },
    advanced_features: {},
  });

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const streamRef = useRef(null);

  // Check voice service status on mount
  const checkVoiceStatus = async () => {
    try {
      const response = await fetch("/api/voice-status");
      const status = await response.json();
      setVoiceStatus(status);
    } catch (error) {
      console.error("Failed to check voice status:", error);
    }
  };

  // Check voice service status on mount
  useEffect(() => {
    checkVoiceStatus();
  }, []);

  const startRecording = async () => {
    try {
      setError("");
      setAnalysisResults(null);

      // Check if speech-to-text is available
      if (!voiceStatus.stt?.available) {
        setError("Speech-to-text service not available");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;

      // Set up audio context for level monitoring
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);

      // Set up MediaRecorder
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: "audio/webm",
      });

      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = handleRecordingComplete;

      mediaRecorderRef.current.start();
      setIsRecording(true);

      // Start monitoring audio levels
      monitorAudioLevel();
    } catch (error) {
      console.error("Error starting recording:", error);
      setError(
        "Failed to start recording. Please check microphone permissions."
      );
    }
  };

  const stopRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
    }

    setIsRecording(false);
    setAudioLevel(0);
  };

  const handleRecordingComplete = async () => {
    try {
      setIsProcessing(true);

      const audioBlob = new Blob(audioChunksRef.current, {
        type: "audio/webm",
      });
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("enable_advanced_analysis", showAdvancedAnalysis);

      let response;

      if (showAdvancedAnalysis) {
        // Use advanced analysis endpoint
        response = await fetch("/api/advanced-audio-analysis", {
          method: "POST",
          body: formData,
        });
      } else {
        // Use regular voice chat endpoint
        const voiceChatFormData = new FormData();
        voiceChatFormData.append("audio", audioBlob, "recording.webm");
        voiceChatFormData.append("user_id", "default");
        voiceChatFormData.append("persona_name", "Mary");

        response = await fetch("/api/voice-chat", {
          method: "POST",
          body: voiceChatFormData,
        });
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();

      if (showAdvancedAnalysis) {
        // Handle advanced analysis results
        setAnalysisResults(result);
        if (onVoiceMessage) {
          onVoiceMessage({
            userText: result.transcription?.text || "",
            aiResponse: "Advanced analysis completed.",
            analysisResults: result,
          });
        }
      } else {
        // Handle regular voice chat results
        if (result.ai_audio_base64) {
          playAudioResponse(result.ai_audio_base64);
        }

        if (onVoiceMessage) {
          onVoiceMessage({
            userText: result.user_text,
            aiResponse: result.ai_response,
            confidence: result.confidence,
            questionCount: result.question_count || 0,
            analysis: result.analysis,
          });
        }
      }
    } catch (error) {
      console.error("Error processing voice message:", error);
      setError("Failed to process voice message");
    } finally {
      setIsProcessing(false);
    }
  };

  const playAudioResponse = (base64Audio) => {
    try {
      // Convert base64 to audio and play
      const audioBlob = new Blob(
        [Uint8Array.from(atob(base64Audio), (c) => c.charCodeAt(0))],
        { type: "audio/wav" }
      );

      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
      };

      audio.play().catch((error) => {
        console.error("Error playing audio:", error);
      });
    } catch (error) {
      console.error("Error processing audio response:", error);
    }
  };

  const monitorAudioLevel = () => {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

    const updateLevel = () => {
      if (!isRecording) return;

      analyserRef.current.getByteFrequencyData(dataArray);
      const average =
        dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
      setAudioLevel(Math.min(average / 128, 1));

      requestAnimationFrame(updateLevel);
    };

    updateLevel();
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const renderAnalysisResults = () => {
    if (!analysisResults) return null;

    const { analysis_summary, qa_analysis, advanced_analysis } =
      analysisResults;

    return (
      <div className="analysis-results">
        <h3>🎯 Advanced Audio Analysis Results</h3>

        {/* Performance Score */}
        <div className="performance-score">
          <h4>Overall Performance Score</h4>
          <div className="score-display">
            <div
              className="score-bar"
              style={{
                width: `${
                  (analysis_summary?.overall_performance_score || 0) * 100
                }%`,
              }}
            />
            <span className="score-text">
              {(
                (analysis_summary?.overall_performance_score || 0) * 100
              ).toFixed(1)}
              %
            </span>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-value">
              {analysis_summary?.speakers_identified || 0}
            </div>
            <div className="metric-label">Speakers Identified</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              {analysis_summary?.questions_asked || 0}
            </div>
            <div className="metric-label">Questions Asked</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              {analysis_summary?.training_techniques_detected || 0}
            </div>
            <div className="metric-label">Techniques Detected</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              {analysis_summary?.conversation_sections || 0}
            </div>
            <div className="metric-label">Conversation Sections</div>
          </div>
        </div>

        {/* Top Recommendations */}
        {analysis_summary?.top_recommendations?.length > 0 && (
          <div className="recommendations">
            <h4>💡 Top Recommendations</h4>
            <ul>
              {analysis_summary.top_recommendations.map((rec, index) => (
                <li key={index}>{rec}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Question Analysis */}
        {qa_analysis && (
          <div className="qa-analysis">
            <h4>❓ Question Analysis</h4>
            <p>
              <strong>Clean Text:</strong> {qa_analysis.clean_text}
            </p>
            <p>
              <strong>Questions Found:</strong> {qa_analysis.question_count}
            </p>
            {qa_analysis.sentences?.length > 0 && (
              <div className="sentences-breakdown">
                <h5>Sentence Breakdown:</h5>
                {qa_analysis.sentences.map((sentence, index) => (
                  <div
                    key={index}
                    className={`sentence ${
                      sentence.is_question ? "question" : "statement"
                    }`}
                  >
                    <span className="sentence-type">{sentence.type}</span>
                    <span className="sentence-text">{sentence.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Training Techniques */}
        {advanced_analysis?.training_annotations?.length > 0 && (
          <div className="training-techniques">
            <h4>🎯 Training Techniques Detected</h4>
            {advanced_analysis.training_annotations
              .slice(0, 5)
              .map((annotation, index) => (
                <div key={index} className="technique-card">
                  <div className="technique-header">
                    <span className="technique-name">
                      {annotation.technique?.value || "Unknown"}
                    </span>
                    <span className="effectiveness-score">
                      {(annotation.effectiveness_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="technique-description">
                    {annotation.description}
                  </p>
                  {annotation.improvement_suggestions?.length > 0 && (
                    <div className="suggestions">
                      <strong>Suggestions:</strong>
                      <ul>
                        {annotation.improvement_suggestions
                          .slice(0, 2)
                          .map((suggestion, i) => (
                            <li key={i}>{suggestion}</li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="enhanced-voice-chat">
      <div className="voice-controls">
        <div className="recording-section">
          <button
            className={`record-button ${isRecording ? "recording" : ""} ${
              isProcessing ? "processing" : ""
            }`}
            onClick={toggleRecording}
            disabled={isProcessing || !voiceStatus.stt?.available}
          >
            {isProcessing ? (
              <div className="processing-spinner" />
            ) : isRecording ? (
              "🛑"
            ) : (
              "🎤"
            )}
          </button>

          {isRecording && (
            <div className="audio-level-indicator">
              <div
                className="audio-level-bar"
                style={{ height: `${audioLevel * 100}%` }}
              />
            </div>
          )}
        </div>

        <div className="voice-options">
          <label className="analysis-toggle">
            <input
              type="checkbox"
              checked={showAdvancedAnalysis}
              onChange={(e) => setShowAdvancedAnalysis(e.target.checked)}
              disabled={!voiceStatus.stt?.advanced_analysis_available}
            />
            <span>Advanced Analysis Mode</span>
          </label>
        </div>
      </div>

      {/* Status Display */}
      <div className="voice-status">
        <div
          className={`status-indicator ${
            voiceStatus.stt?.available ? "active" : "inactive"
          }`}
        >
          STT: {voiceStatus.stt?.available ? "Ready" : "Unavailable"}
        </div>
        <div
          className={`status-indicator ${
            voiceStatus.tts?.available ? "active" : "inactive"
          }`}
        >
          TTS: {voiceStatus.tts?.available ? "Ready" : "Unavailable"}
        </div>
        {voiceStatus.advanced_features?.speaker_diarization && (
          <div className="status-indicator active">
            Advanced Analysis: Ready
          </div>
        )}
      </div>

      {error && <div className="error-message">⚠️ {error}</div>}

      {isProcessing && (
        <div className="processing-message">
          {showAdvancedAnalysis
            ? "🔍 Running advanced analysis..."
            : "🎤 Processing voice..."}
        </div>
      )}

      {/* Analysis Results */}
      {analysisResults && renderAnalysisResults()}
    </div>
  );
};

export default EnhancedVoiceChat;
