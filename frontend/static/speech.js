/**
 * Speech helpers.
 *
 * STT keeps the native browser recognizer first because it preserves live
 * interim dictation. Puter speech2txt is the fallback when the browser API is
 * not available.
 */

const STT_FALLBACK_ORDER = ["native", "puter"];

// Prefer the browser recognizer when live interim text is available.
function _hasNativeSpeechRecognition() {
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

// Fall back to Puter speech-to-text when native recognition is missing.
function _hasPuterSpeechRecognition() {
  return Boolean(
    window.puter?.ai?.speech2txt &&
      navigator.mediaDevices?.getUserMedia &&
      window.MediaRecorder,
  );
}

// Pick the first recording format the browser can actually produce.
function _pickAudioMimeType() {
  if (!window.MediaRecorder || typeof window.MediaRecorder.isTypeSupported !== "function") {
    return "";
  }

  const preferredTypes = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];

  for (const type of preferredTypes) {
    if (window.MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }

  return "";
}

// Stop every live audio track so the microphone is released cleanly.
function _disposeAudioStream(stream) {
  if (!stream || typeof stream.getTracks !== "function") return;
  stream.getTracks().forEach((track) => {
    try {
      track.stop();
    } catch (e) {
      // Ignore cleanup errors.
    }
  });
}

class SpeechRecognizer {
  constructor(language = "en-US") {
    this.language = language;
    this.isRecording = false;
    this.isTranscribing = false;
    this.ignoreOnEnd = false;
    this.maxRecordingMs = 60000;
    this.maxRecordingTimer = null;
    this._stopRequested = false;
    this._activeMode = null;
    this._nativeRecognition = null;
    this._puterRecognitionShim = null;
    this._puterStream = null;
    this._puterRecorder = null;
    this._puterChunks = [];
    this._puterMimeType = "";

    // Callbacks
    this.onFinalText = null;
    this.onInterimText = null;
    this.onStop = null;
    this.onError = null;

    if (this._supportsNativeRecognition()) {
      this._ensureNativeRecognition();
    } else if (this._supportsPuterRecognition()) {
      this._ensurePuterRecognitionShim();
    }
  }

  get isSupported() {
    return Boolean(this.recognition);
  }

  get recognition() {
    if (this._activeMode === "native" && this._nativeRecognition) {
      return this._nativeRecognition;
    }
    if (this._activeMode === "puter" && this._puterRecognitionShim) {
      return this._puterRecognitionShim;
    }

    if (this._supportsNativeRecognition()) {
      return this._ensureNativeRecognition();
    }
    if (this._supportsPuterRecognition()) {
      return this._ensurePuterRecognitionShim();
    }
    return null;
  }

  _supportsNativeRecognition() {
    return _hasNativeSpeechRecognition();
  }

  _supportsPuterRecognition() {
    return _hasPuterSpeechRecognition();
  }

  _clearMaxRecordingTimer() {
    if (this.maxRecordingTimer) {
      clearTimeout(this.maxRecordingTimer);
      this.maxRecordingTimer = null;
    }
  }

  _ensureNativeRecognition() {
    if (!this._supportsNativeRecognition()) {
      return null;
    }

    if (this._nativeRecognition) {
      this._nativeRecognition.lang = this.language;
      return this._nativeRecognition;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = this.language;

    recognition.onresult = (event) => {
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

    recognition.onend = () => {
      if (this.isRecording && !this.ignoreOnEnd) {
        setTimeout(() => {
          try {
            recognition.start();
          } catch (e) {
            // Ignore restart errors and let the UI recover naturally.
          }
        }, 100);
        return;
      }

      this.isRecording = false;
      this._activeMode = null;
      if (this.onStop) this.onStop({ mode: "native", transcribing: false });
    };

    recognition.onerror = (event) => {
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

    this._nativeRecognition = recognition;
    return recognition;
  }

  _ensurePuterRecognitionShim() {
    if (!this._supportsPuterRecognition()) {
      return null;
    }

    if (!this._puterRecognitionShim) {
      this._puterRecognitionShim = { provider: "puter" };
    }
    return this._puterRecognitionShim;
  }

  _resetPuterState() {
    this._puterRecorder = null;
    this._puterChunks = [];
    this._puterMimeType = "";
    _disposeAudioStream(this._puterStream);
    this._puterStream = null;
  }

  async _transcribeWithPuter() {
    if (!this._supportsPuterRecognition()) {
      throw new Error("Puter speech transcription is unavailable");
    }

    const puter = window.puter?.ai;
    const blob = new Blob(this._puterChunks, {
      type: this._puterMimeType || "audio/webm",
    });
    if (!blob.size) {
      throw new Error("No audio captured for transcription");
    }

    const result = await puter.speech2txt({
      file: blob,
      model: "gpt-4o-mini-transcribe",
    });
    const transcript = String(result?.text || result || "").trim();
    if (transcript && this.onFinalText) {
      this.onFinalText(`${transcript} `);
    }
  }

  _startNativeRecording() {
    const recognition = this._ensureNativeRecognition();
    if (!recognition) {
      return false;
    }

    this.isRecording = true;
    this.isTranscribing = false;
    this.ignoreOnEnd = false;
    this._stopRequested = false;
    this._activeMode = "native";

    try {
      recognition.start();
    } catch (e) {
      this.isRecording = false;
      this._activeMode = null;
      console.error(e);
      return false;
    }

    this.maxRecordingTimer = setTimeout(() => {
      if (this.isRecording) {
        this.stop();
      }
    }, this.maxRecordingMs);

    return true;
  }

  _startPuterRecording() {
    if (!this._supportsPuterRecognition()) {
      return false;
    }

    this._ensurePuterRecognitionShim();
    this.isRecording = true;
    this.isTranscribing = false;
    this.ignoreOnEnd = false;
    this._stopRequested = false;
    this._activeMode = "puter";

    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (!this.isRecording) {
          _disposeAudioStream(stream);
          return;
        }

        this._puterStream = stream;
        this._puterChunks = [];
        this._puterMimeType = _pickAudioMimeType();

        const options = this._puterMimeType ? { mimeType: this._puterMimeType } : {};
        this._puterRecorder = new MediaRecorder(stream, options);
        this._puterRecorder.ondataavailable = (event) => {
          if (event.data && event.data.size) {
            this._puterChunks.push(event.data);
          }
        };
        this._puterRecorder.onstop = async () => {
          this._clearMaxRecordingTimer();
          this.isTranscribing = true;
          try {
            await this._transcribeWithPuter();
          } catch (error) {
            console.warn("Puter speech transcription failed", error);
            if (this.onError) this.onError(error?.message || "Speech transcription failed");
          } finally {
            this.isTranscribing = false;
            this.isRecording = false;
            this._activeMode = null;
            this._resetPuterState();
            if (this.onStop) {
              this.onStop({
                mode: "puter",
                transcribing: false,
                canceled: this._stopRequested,
              });
            }
          }
        };

        this._puterRecorder.start();
        if (this.onInterimText) {
          this.onInterimText("Recording...");
        }
      } catch (error) {
        console.warn("Puter speech recording failed", error);
        this.isRecording = false;
        this._activeMode = null;
        this._resetPuterState();
        if (this.onError) {
          this.onError(error?.message || "Voice recording is not supported in this browser");
        }
      }
    })();

    this.maxRecordingTimer = setTimeout(() => {
      if (this.isRecording) {
        this.stop();
      }
    }, this.maxRecordingMs);

    return true;
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

    for (const mode of STT_FALLBACK_ORDER) {
      if (mode === "native" && this._supportsNativeRecognition()) {
        return this._startNativeRecording();
      }
      if (mode === "puter" && this._supportsPuterRecognition()) {
        return this._startPuterRecording();
      }
    }

    this.isRecording = false;
    if (this.onError) {
      this.onError("Voice recording is not supported in this browser");
    }
    return false;
  }

  stop() {
    if (!this.isRecording && !this.isTranscribing) return;

    this._stopRequested = true;
    this._clearMaxRecordingTimer();

    if (this._activeMode === "native" && this._nativeRecognition) {
      this.isRecording = false;
      this.ignoreOnEnd = true;
      try {
        this._nativeRecognition.stop();
      } catch (e) {
        console.warn("Speech recognition stop failed", e);
      }
      return;
    }

    if (this._activeMode === "puter" && this._puterRecorder) {
      if (this.isTranscribing) {
        return;
      }
      try {
        this._puterRecorder.stop();
      } catch (e) {
        console.warn("Puter speech recorder stop failed", e);
      }
      return;
    }

    this.isRecording = false;
    this.isTranscribing = false;
    this._activeMode = null;
    if (this.onStop) {
      this.onStop({ mode: "native", transcribing: false, canceled: true });
    }
  }

  setLanguage(lang) {
    this.language = lang;
    if (this._nativeRecognition) {
      this._nativeRecognition.lang = lang;
    }
  }
}
