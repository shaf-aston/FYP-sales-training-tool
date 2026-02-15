/**
 * Advanced Speech Recognition Module
 * Improvements: Interim results, robust error handling, dynamic language
 */

class SpeechRecognizer {
  constructor(language = "en-US") {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      this.recognition = null;
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true; // IMPROVEMENT: Enable real-time feedback
    this.recognition.lang = language;

    this.isRecording = false;
    this.ignoreOnEnd = false; // Flag to stop the restart loop on fatal errors

    // Callbacks
    this.onFinalText = null;
    this.onInterimText = null; // New callback for gray text
    this.onStop = null;
    this.onError = null;

    this.recognition.onresult = (event) => {
      let interimTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          // Send final text
          const text = event.results[i][0].transcript.trim() + " ";
          if (this.onFinalText) this.onFinalText(text);
        } else {
          // Concatenate interim text
          interimTranscript += event.results[i][0].transcript;
        }
      }

      // Send interim text (for live preview)
      if (this.onInterimText) {
        this.onInterimText(interimTranscript);
      }
    };

    this.recognition.onend = () => {
      if (this.isRecording && !this.ignoreOnEnd) {
        // IMPROVEMENT: Delay restart slightly to prevent CPU spinning if errors loop
        setTimeout(() => {
          try {
            this.recognition.start();
          } catch (e) {
            // Determine if we need to handle specific restart errors
          }
        }, 100);
      } else {
        this.isRecording = false;
        if (this.onStop) this.onStop();
      }
    };

    this.recognition.onerror = (event) => {
      // IMPROVEMENT: Handle specific errors differently
      if (event.error === "no-speech") {
        // This is normal, just ignore and let it restart in onend
        return;
      }

      if (event.error === "audio-capture" || event.error === "not-allowed") {
        // Fatal errors - do not restart
        this.ignoreOnEnd = true;
        this.isRecording = false;
      }

      console.warn("Speech recognition error", event.error);
      if (this.onError) this.onError(event.error);
    };
  }

  /**
   * Start recording
   * @param {Function} onFinal - Callback for finalized text
   * @param {Function} onInterim - Callback for live streaming text
   * @param {Function} onStop - Callback when stopped
   * @param {Function} onError - Callback for errors
   */
  start(onFinal, onInterim, onStop, onError) {
    if (!this.recognition) return false;
    if (this.isRecording) return true;

    this.onFinalText = onFinal;
    this.onInterimText = onInterim;
    this.onStop = onStop;
    this.onError = onError;

    this.isRecording = true;
    this.ignoreOnEnd = false;

    try {
      this.recognition.start();
      return true;
    } catch (e) {
      console.error(e);
      return false;
    }
  }

  stop() {
    if (this.recognition && this.isRecording) {
      this.isRecording = false;
      this.ignoreOnEnd = true; // Explicitly stop the loop
      this.recognition.stop();
    }
  }

  setLanguage(lang) {
    if (this.recognition) {
      this.recognition.lang = lang;
    }
  }
}
