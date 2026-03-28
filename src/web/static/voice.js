/**
 * Voice Mode Module
 * Handles audio recording (toggle mode), transcription, and playback
 *
 * Toggle mode: Click to start recording, click again to stop and send
 */

class VoiceMode {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.stream = null;
    this.audioContext = null;
    this.analyser = null;

    // Configuration
    this.voice = "male_us"; // Default voice
    this.autoPlay = true; // Auto-play bot audio responses

    // Callbacks
    this.onRecordingStart = null;
    this.onRecordingStop = null;
    this.onTranscription = null;
    this.onResponse = null;
    this.onError = null;
    this.onAudioPlay = null;
    this.onAudioEnd = null;

    // State
    this.isInitialized = false;
    this.currentAudio = null;
  }

  /**
   * Initialize voice mode (request microphone access)
   * @returns {Promise<boolean>} True if initialized successfully
   */
  async init() {
    if (this.isInitialized) return true;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Set up audio analyser for visualization (optional)
      this.audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )();
      this.analyser = this.audioContext.createAnalyser();
      const source = this.audioContext.createMediaStreamSource(this.stream);
      source.connect(this.analyser);
      this.analyser.fftSize = 256;

      // Configure MediaRecorder with best available format
      const mimeType = this._getBestMimeType();
      this.mediaRecorder = new MediaRecorder(this.stream, {
        mimeType,
        audioBitsPerSecond: 128000,
      });

      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          this.audioChunks.push(e.data);
        }
      };

      this.mediaRecorder.onstop = () => this._handleRecordingComplete();

      this.isInitialized = true;
      console.log("VoiceMode initialized with", mimeType);
      return true;
    } catch (err) {
      console.error("VoiceMode init failed:", err);
      const errorMsg = this._getErrorMessage(err);
      if (this.onError) this.onError(errorMsg);
      return false;
    }
  }

  /**
   * Get the best supported audio MIME type
   */
  _getBestMimeType() {
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return "audio/webm"; // Fallback
  }

  /**
   * Convert MediaRecorder errors to user-friendly messages
   */
  _getErrorMessage(err) {
    if (
      err.name === "NotAllowedError" ||
      err.name === "PermissionDeniedError"
    ) {
      return "Microphone access denied. Please allow microphone access in your browser settings.";
    }
    if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
      return "No microphone found. Please connect a microphone and try again.";
    }
    if (err.name === "NotReadableError" || err.name === "TrackStartError") {
      return "Microphone is in use by another application.";
    }
    return `Microphone error: ${err.message || err.name || "Unknown error"}`;
  }

  /**
   * Toggle recording (start if stopped, stop if recording)
   * @returns {boolean} New recording state
   */
  toggle() {
    if (this.isRecording) {
      this.stopRecording();
      return false;
    } else {
      return this.startRecording();
    }
  }

  /**
   * Start recording audio
   * @returns {boolean} True if recording started
   */
  startRecording() {
    if (!this.isInitialized) {
      console.warn("VoiceMode not initialized");
      return false;
    }
    if (this.isRecording) return true;

    // Stop any playing audio
    this.stopPlayback();

    // Clear previous chunks
    this.audioChunks = [];

    // Resume audio context if suspended
    if (this.audioContext.state === "suspended") {
      this.audioContext.resume();
    }

    // Start recording (collect data every 100ms)
    this.mediaRecorder.start(100);
    this.isRecording = true;

    if (this.onRecordingStart) this.onRecordingStart();
    console.log("Recording started");
    return true;
  }

  /**
   * Stop recording audio
   */
  stopRecording() {
    if (!this.mediaRecorder || !this.isRecording) return;

    this.mediaRecorder.stop();
    this.isRecording = false;

    if (this.onRecordingStop) this.onRecordingStop();
    console.log("Recording stopped");
  }

  /**
   * Handle recording completion - send to server
   */
  async _handleRecordingComplete() {
    const audioBlob = new Blob(this.audioChunks, {
      type: this.mediaRecorder.mimeType,
    });

    // Check if audio is too short (likely accidental click)
    if (audioBlob.size < 1000) {
      console.log("Audio too short, ignoring");
      return;
    }

    // Get session ID from the app
    const sessionId =
      typeof getSessionId === "function" ? getSessionId() : null;
    if (!sessionId) {
      if (this.onError)
        this.onError("No active session. Please refresh the page.");
      return;
    }

    // Build form data
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    formData.append("voice", this.voice);

    try {
      const response = await fetch("/api/voice/chat", {
        method: "POST",
        headers: { "X-Session-ID": sessionId },
        body: formData,
      });

      const data = await response.json();

      if (!data.success) {
        if (this.onError) this.onError(data.error || "Voice request failed");
        return;
      }

      // Callback with transcription (user's message)
      if (this.onTranscription) {
        this.onTranscription(data.transcription);
      }

      // Callback with full response
      if (this.onResponse) {
        this.onResponse(data);
      }

      // Auto-play audio response
      if (this.autoPlay && data.audio) {
        this.playAudio(data.audio, data.audio_type);
      }
    } catch (err) {
      console.error("Voice chat error:", err);
      if (this.onError) this.onError("Voice request failed. Please try again.");
    }
  }

  /**
   * Play base64-encoded audio
   * @param {string} base64Audio - Base64-encoded audio data
   * @param {string} mimeType - Audio MIME type
   */
  playAudio(base64Audio, mimeType = "audio/mpeg") {
    if (!base64Audio) return;

    try {
      // Decode base64 to bytes
      const audioBytes = Uint8Array.from(atob(base64Audio), (char) =>
        char.charCodeAt(0),
      );
      const audioBlob = new Blob([audioBytes], { type: mimeType });
      const audioUrl = URL.createObjectURL(audioBlob);

      // Stop any currently playing audio
      this.stopPlayback();

      // Create and play new audio
      this.currentAudio = new Audio(audioUrl);

      this.currentAudio.onplay = () => {
        if (this.onAudioPlay) this.onAudioPlay();
      };

      this.currentAudio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        this.currentAudio = null;
        if (this.onAudioEnd) this.onAudioEnd();
      };

      this.currentAudio.onerror = (e) => {
        console.error("Audio playback error:", e);
        URL.revokeObjectURL(audioUrl);
        this.currentAudio = null;
      };

      this.currentAudio.play().catch((e) => {
        console.warn("Audio autoplay blocked:", e);
        // Browser blocked autoplay - user needs to interact first
      });
    } catch (err) {
      console.error("Play audio error:", err);
    }
  }

  /**
   * Stop currently playing audio
   */
  stopPlayback() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
  }

  /**
   * Set voice for TTS
   * @param {string} voice - Voice key (male_us, female_us, male_uk, female_uk)
   */
  setVoice(voice) {
    this.voice = voice;
  }

  /**
   * Get audio analyser data for visualization
   * @returns {Uint8Array|null} Frequency data array or null
   */
  getAnalyserData() {
    if (!this.analyser) return null;
    const data = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(data);
    return data;
  }

  /**
   * Get current recording state
   */
  getState() {
    return {
      isInitialized: this.isInitialized,
      isRecording: this.isRecording,
      isPlaying: this.currentAudio && !this.currentAudio.paused,
      voice: this.voice,
    };
  }

  /**
   * Clean up resources
   */
  destroy() {
    this.stopRecording();
    this.stopPlayback();

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.isInitialized = false;
  }
}

// Singleton instance
let voiceMode = null;

/**
 * Get or create VoiceMode instance
 * @returns {VoiceMode}
 */
function getVoiceMode() {
  if (!voiceMode) {
    voiceMode = new VoiceMode();
  }
  return voiceMode;
}

/**
 * Initialize voice mode (call on page load or user interaction)
 * @returns {Promise<boolean>}
 */
async function initVoiceMode() {
  const vm = getVoiceMode();
  return await vm.init();
}

/**
 * Check if voice mode is supported by the browser
 * @returns {boolean}
 */
function isVoiceModeSupported() {
  return !!(
    navigator.mediaDevices?.getUserMedia &&
    window.MediaRecorder &&
    (window.AudioContext || window.webkitAudioContext)
  );
}
