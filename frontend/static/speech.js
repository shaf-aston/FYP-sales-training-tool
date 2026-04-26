/**
 * Speech Recognition helper.
 *
 * Native browser recognition is used when available. When it is not, the
 * class falls back to a MediaRecorder + Puter transcription flow.
 */

class SpeechRecognizer {
  constructor(language = "en-US") {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    this.language = language;
    this.usePuterFallback = !SpeechRecognition;
    this.recognition = null;
    this.mediaRecorder = null;
    this.mediaStream = null;
    this.recordingChunks = [];
    this.isRecording = false;
    this.isTranscribing = false;
    this.ignoreOnEnd = false;
    this.maxRecordingMs = 60000;
    this.maxRecordingTimer = null;
    this._stopRequested = false;

    // Callbacks
    this.onFinalText = null;
    this.onInterimText = null;
    this.onStop = null;
    this.onError = null;

    if (this.usePuterFallback) {
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = language;

    this.recognition.onresult = (event) => {
      let interimTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          const text = event.results[i][0].transcript.trim() + " ";
          if (this.onFinalText) this.onFinalText(text);
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (this.onInterimText) {
        this.onInterimText(interimTranscript);
      }
    };

    this.recognition.onend = () => {
      if (this.isRecording && !this.ignoreOnEnd) {
        setTimeout(() => {
          try {
            this.recognition.start();
          } catch (e) {
            // Ignore restart errors and let the UI recover naturally.
          }
        }, 100);
        return;
      }

      this.isRecording = false;
      if (this.onStop) this.onStop({ mode: "native", transcribing: false });
    };

    this.recognition.onerror = (event) => {
      if (event.error === "no-speech") {
        return;
      }

      if (event.error === "audio-capture" || event.error === "not-allowed") {
        this.ignoreOnEnd = true;
        this.isRecording = false;
      }

      console.warn("Speech recognition error", event.error);
      if (this.onError) this.onError(event.error);
    };
  }

  async _loadPuterSdk() {
    if (typeof puter !== "undefined" && puter.ai) {
      return;
    }

    if (window.__puterSdkLoadPromise) {
      return window.__puterSdkLoadPromise;
    }

    window.__puterSdkLoadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://js.puter.com/v2/";
      script.async = true;
      script.dataset.sdk = "puter";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Puter SDK"));
      document.head.appendChild(script);
    }).catch((err) => {
      window.__puterSdkLoadPromise = null;
      throw err;
    });

    return window.__puterSdkLoadPromise;
  }

  async _transcribeWithPuter(blob) {
    await this._loadPuterSdk();

    if (typeof puter === "undefined" || !puter.ai) {
      throw new Error("Puter SDK loaded but puter.ai is unavailable");
    }

    const result = await puter.ai.speech2txt(blob, {
      model: "gpt-4o-mini-transcribe",
    });

    if (typeof result === "string") {
      return result;
    }

    if (result && typeof result.text === "string") {
      return result.text;
    }

    throw new Error("Unexpected transcription result from Puter");
  }

  _clearMaxRecordingTimer() {
    if (this.maxRecordingTimer) {
      clearTimeout(this.maxRecordingTimer);
      this.maxRecordingTimer = null;
    }
  }

  _cleanupStream() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
  }

  _resetFallbackState() {
    this.mediaRecorder = null;
    this.recordingChunks = [];
    this.isTranscribing = false;
    this._clearMaxRecordingTimer();
    this._cleanupStream();
  }

  /**
   * Start recording
   * @param {Function} onFinal - Callback for finalized text
   * @param {Function} onInterim - Callback for live streaming text
   * @param {Function} onStop - Callback when stopped
   * @param {Function} onError - Callback for errors
   */
  start(onFinal, onInterim, onStop, onError) {
    if (this.isRecording || this.isTranscribing) return true;

    this.onFinalText = onFinal;
    this.onInterimText = onInterim;
    this.onStop = onStop;
    this.onError = onError;

    this.isRecording = true;
    this.ignoreOnEnd = false;
    this._stopRequested = false;

    if (!this.usePuterFallback) {
      try {
        this.recognition.start();
        return true;
      } catch (e) {
        this.isRecording = false;
        console.error(e);
        return false;
      }
    }

    if (
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      this.isRecording = false;
      if (this.onError) {
        this.onError("Voice recording is not supported in this browser");
      }
      return false;
    }

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        if (!this.isRecording || this._stopRequested) {
          stream.getTracks().forEach((track) => track.stop());
          this.isRecording = false;
          return;
        }

        this.mediaStream = stream;
        this.recordingChunks = [];

        const recorder = new MediaRecorder(stream);
        this.mediaRecorder = recorder;

        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            this.recordingChunks.push(event.data);
          }
        };

        recorder.onerror = (event) => {
          console.warn("MediaRecorder error", event);
          this._resetFallbackState();
          this.isRecording = false;
          if (this.onError) {
            this.onError(event?.error?.message || "Recording failed");
          }
        };

        recorder.onstop = async () => {
          this.isRecording = false;
          this.isTranscribing = true;

          if (this.onStop) {
            this.onStop({ mode: "puter", transcribing: true });
          }

          try {
            const blob = new Blob(this.recordingChunks, {
              type: recorder.mimeType || "audio/webm",
            });
            const text = await this._transcribeWithPuter(blob);
            if (text && this.onFinalText) {
              this.onFinalText(`${String(text).trim()} `);
            }
          } catch (err) {
            console.warn("Puter transcription failed", err);
            if (this.onError) {
              this.onError(err?.message || "Transcription failed");
            }
          } finally {
            this._resetFallbackState();
          }
        };

        try {
          recorder.start();
        } catch (err) {
          this._resetFallbackState();
          this.isRecording = false;
          if (this.onError) {
            this.onError(err?.message || "Could not start recording");
          }
          return;
        }

        this.maxRecordingTimer = setTimeout(() => {
          if (this.isRecording) {
            this.stop();
          }
        }, this.maxRecordingMs);
      })
      .catch((err) => {
        this.isRecording = false;
        if (this.onError) {
          this.onError(err?.message || "Microphone access failed");
        }
      });

    return true;
  }

  stop() {
    if (!this.isRecording) return;

    this.isRecording = false;
    this.ignoreOnEnd = true;
    this._stopRequested = true;
    this._clearMaxRecordingTimer();

    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {
        console.warn("Speech recognition stop failed", e);
      }
      return;
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      try {
        this.mediaRecorder.stop();
      } catch (e) {
        console.warn("MediaRecorder stop failed", e);
      }
      return;
    }

    this._resetFallbackState();
    if (this.onStop) {
      this.onStop({ mode: "puter", transcribing: false, canceled: true });
    }
  }

  setLanguage(lang) {
    this.language = lang;
    if (this.recognition) {
      this.recognition.lang = lang;
    }
  }
}
