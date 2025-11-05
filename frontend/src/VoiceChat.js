import React, { useState, useRef, useEffect } from "react";
import "./VoiceChat.css";

const VoiceChat = ({ onVoiceMessage, isListening: externalListening }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState("");
  const [voiceStatus, setVoiceStatus] = useState({
    whisper: false,
    elevenlabs: false,
  });

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const streamRef = useRef(null);

  // Check voice service status on mount
  const checkVoiceStatus = async () => {
    try {
      // Backend route is mounted as /api/voice-status (not /api/voice/status)
      const response = await fetch("/api/voice-status");
      const status = await response.json();
      setVoiceStatus({
        whisper: status.whisper_available,
        elevenlabs: status.elevenlabs_available,
      });
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

      // Check if speech-to-text is available
      if (!voiceStatus.whisper) {
        setError("Speech-to-text service not available");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;

      // Setup audio analysis for visual feedback
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);

      // Start audio level monitoring
      monitorAudioLevel();

      // Setup MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm",
      });

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = processRecording;

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("Error starting recording:", error);
      setError("Failed to access microphone");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setAudioLevel(0);

      // Stop all tracks
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }

      // Close audio context
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    }
  };

  const processRecording = async () => {
    setIsProcessing(true);

    try {
      // Create blob from recorded chunks
      const audioBlob = new Blob(audioChunksRef.current, {
        type: "audio/webm",
      });

      // Create form data for upload
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("user_id", "default");

      // Send to voice chat endpoint
      // Backend voice chat endpoint is /api/voice-chat
      const response = await fetch("/api/voice-chat", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      // Play AI response audio if available
      if (result.ai_audio && voiceStatus.elevenlabs) {
        playAudioResponse(result.ai_audio);
      }

      // Send message to parent component
      if (onVoiceMessage) {
        onVoiceMessage({
          userText: result.user_text,
          aiResponse: result.ai_response,
          hasAudio: !!result.ai_audio,
        });
      }
    } catch (error) {
      console.error("Error processing recording:", error);
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
        { type: "audio/mpeg" }
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

  return (
    <div className="voice-chat">
      <div className="voice-controls">
        <button
          className={`record-button ${isRecording ? "recording" : ""} ${
            isProcessing ? "processing" : ""
          }`}
          onClick={toggleRecording}
          disabled={isProcessing || !voiceStatus.whisper}
        >
          <div className="record-icon">
            {isProcessing ? (
              <div className="spinner"></div>
            ) : isRecording ? (
              <div className="stop-icon"></div>
            ) : (
              <div className="mic-icon">🎤</div>
            )}
          </div>

          {isRecording && (
            <div className="audio-level" style={{ opacity: audioLevel }}></div>
          )}
        </button>

        <div className="voice-status">
          <div
            className={`status-indicator ${
              voiceStatus.whisper ? "available" : "unavailable"
            }`}
          >
            STT: {voiceStatus.whisper ? "✅" : "❌"}
          </div>
          <div
            className={`status-indicator ${
              voiceStatus.elevenlabs ? "available" : "unavailable"
            }`}
          >
            TTS: {voiceStatus.elevenlabs ? "✅" : "❌"}
          </div>
        </div>
      </div>

      <div className="voice-instructions">
        {isProcessing ? (
          <p>Processing your message...</p>
        ) : isRecording ? (
          <p>Listening... Click to stop recording</p>
        ) : voiceStatus.whisper ? (
          <p>Click the microphone to start voice conversation</p>
        ) : (
          <p>Voice features not available - check configuration</p>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default VoiceChat;
