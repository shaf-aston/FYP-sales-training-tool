/**
 * Speech Recognition Module
 * Single Responsibility: Convert speech to text
 */

class SpeechRecognizer {
  constructor() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      this.recognition = null;
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true; // Keep listening until manually stopped
    this.recognition.interimResults = false;
    this.recognition.lang = "en-US";
    this.isRecording = false;
    this.onTextCallback = null;
    this.onStopCallback = null;

    this.recognition.onresult = (e) => {
      // Process only NEW results to avoid duplication
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const text = e.results[i][0].transcript + " ";
          if (this.onTextCallback) this.onTextCallback(text);
        }
      }
    };

    this.recognition.onend = () => {
      // Auto-restart if still supposed to be recording
      if (this.isRecording) {
        this.recognition.start();
      } else if (this.onStopCallback) {
        this.onStopCallback(); // Only call when actually stopping
      }
    };

    this.recognition.onerror = (e) => {
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.error("Speech error:", e.error);
      }
      this.isRecording = false;
      if (this.onStopCallback) this.onStopCallback();
    };
  }

  start(onText, onStop) {
    if (!this.recognition) {
      alert("Speech not supported. Use Chrome or Edge.");
      return false;
    }
    if (this.isRecording) return false;

    this.onTextCallback = onText;
    this.onStopCallback = onStop;
    this.recognition.start();
    this.isRecording = true;
    return true;
  }

  stop() {
    if (this.recognition && this.isRecording) {
      this.isRecording = false; // Set flag BEFORE stopping to prevent auto-restart
      this.recognition.stop();
    }
  }

  isAvailable() {
    return this.recognition !== null;
  }

  getState() {
    return this.isRecording;
  }
}
