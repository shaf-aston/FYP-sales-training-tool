// Voice mode state
let handsFreeMode = false;
let currentTtsAudio = null;
let ttsPlaybackSpeed = parseInt(
  localStorage.getItem("ttsPlaybackSpeed") || "0",
); // Range: -50 to +50 percent, default 0 is normal speed
let shouldAutoSendAfterSilence =
  localStorage.getItem("autoSendDictation") !== "false";
const VOICE_SILENCE_DELAY_MS = 500; // Wait for 0.5 seconds of silence before auto-send
const TTS_RESUME_WATCHDOG_MS = 15000;
let voiceSilenceTimer = null;
let ttsResumeWatchdogTimer = null;
let ttsPlaybackGeneration = 0;
let ttsPlaybackPending = false;
let _handsFreeRestartAttempts = 0;

// Voice settings helpers.
function toggleAutoSend() {
  const checkbox = document.getElementById("autoSendDictationToggle");
  shouldAutoSendAfterSilence = checkbox.checked;
  localStorage.setItem("autoSendDictation", shouldAutoSendAfterSilence);
  showToast(
    `Auto-send after pause ${shouldAutoSendAfterSilence ? "ON" : "OFF"}`,
  );
}

function updateTtsSpeed(speedValueInput) {
  ttsPlaybackSpeed = parseInt(speedValueInput);
  const speedValue = document.getElementById("ttsSpeedValue");
  const speedPercent = document.getElementById("ttsSpeedPercent");

  // Update label text based on speed
  if (ttsPlaybackSpeed < 0) {
    speedValue.textContent = `Slower (${ttsPlaybackSpeed}%)`;
  } else if (ttsPlaybackSpeed > 0) {
    speedValue.textContent = `Faster (+${ttsPlaybackSpeed}%)`;
  } else {
    speedValue.textContent = "Normal";
  }

  speedPercent.textContent = `${ttsPlaybackSpeed > 0 ? "+" : ""}${ttsPlaybackSpeed}%`;
  localStorage.setItem("ttsPlaybackSpeed", ttsPlaybackSpeed);
}

// Restore the saved TTS speed into the slider and label.
function initTtsSpeedControl() {
  const slider = document.getElementById("ttsSpeedSlider");
  if (slider) {
    slider.value = ttsPlaybackSpeed;
    updateTtsSpeed(ttsPlaybackSpeed);
  }
}


// Text-to-speech helpers
const tts = {
  speak: (t) => playAssistantTts(t).then(() => true),
  stop: () => stopTtsPlayback(),
  isSpeaking: () =>
    ttsPlaybackPending ||
    Boolean(currentTtsAudio) ||
    ("speechSynthesis" in window && speechSynthesis.speaking),
};

function clearVoiceSilenceTimer() {
  if (!voiceSilenceTimer) return;
  clearTimeout(voiceSilenceTimer);
  voiceSilenceTimer = null;
}

function scheduleVoiceAutoSend(inputEl) {
  if (!shouldAutoSendAfterSilence) return;

  clearVoiceSilenceTimer();
  voiceSilenceTimer = setTimeout(() => {
    voiceSilenceTimer = null;
    if (inputEl.value.trim()) sendMessage();
  }, VOICE_SILENCE_DELAY_MS);
}

function _setDictationPreview(text) {
  const el = document.getElementById("dictationPreview");
  if (!el) return;
  if (text && text.trim()) {
    el.textContent = text;
    el.style.display = "";
  } else {
    el.textContent = "";
    el.style.display = "none";
  }
}

function _showTTSBanner(on) {
  const el = document.getElementById("ttsSpeakingBanner");
  if (el) el.style.display = on ? "" : "none";
}

function parsePunctuation(text) {
  return text
    .replace(/ period /g, ". ")
    .replace(/ comma /g, ", ")
    .replace(/ new line /g, "\n");
}

// Speech module
let speechRecognizer;

function toggleMic() {
  const micBtn = document.getElementById("micBtn");
  const input = document.getElementById("messageInput");

  if (!speechRecognizer) {
    showToast("Speech not supported in this browser", "error");
    return;
  }

  if (speechRecognizer.isTranscribing) {
    showToast("Transcribing, please wait", "info");
    return;
  }

  if (speechRecognizer.isRecording) {
    speechRecognizer.stop();
    return;
  }

  micBtn.classList.add("recording");
  micBtn.innerHTML = "Stop";

  speechRecognizer.start(
    (text) => {
      if (currentTtsAudio) return; // echo guard: ignore while bot is speaking
      const parsed = parsePunctuation(text);
      input.value = (input.value || "") + parsed;
      autoResizeTextarea(input);
      _setDictationPreview("");

      scheduleVoiceAutoSend(input);
    },
    (text) => {
      if (currentTtsAudio) return;
      _setDictationPreview(text);
    },
    (state) => {
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "Mic";
      if (state?.canceled) {
        _setDictationPreview("");
        input.focus();
        return;
      }
      _setDictationPreview("");
      // On stop: let the pause-timer fire naturally; only flush if user typed.
      input.focus();
    },
    (err) => {
      console.warn("Mic Error:", err);
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "Mic";
      _setDictationPreview("");
      showToast(String(err || "Microphone error"), "error");
    },
  );
}

function resumeVoiceInputAfterTts() {
  window.__speechPausedForTTS = false;
  if (handsFreeMode) {
    startHandsFreeRecognition();
    return;
  }

  const input = document.getElementById("messageInput");
  if (input) input.focus();
}

function stopTtsPlayback({ resumeVoiceInput = false } = {}) {
  ttsPlaybackGeneration += 1;
  ttsPlaybackPending = false;

  if (ttsResumeWatchdogTimer) {
    clearTimeout(ttsResumeWatchdogTimer);
    ttsResumeWatchdogTimer = null;
  }

  if (currentTtsAudio) {
    currentTtsAudio.onended = null;
    currentTtsAudio.onerror = null;
    try {
      currentTtsAudio.pause();
    } catch (e) {}

    if (currentTtsAudio._blobUrl) {
      URL.revokeObjectURL(currentTtsAudio._blobUrl);
    }
    currentTtsAudio = null;
  }

  document.querySelectorAll(".tts-btn.speaking").forEach((btn) => {
    btn.classList.remove("speaking");
  });

  const interruptBtn = document.getElementById("interruptBtn");
  if (interruptBtn) interruptBtn.style.display = "none";
  _showTTSBanner(false);

  if (resumeVoiceInput) {
    resumeVoiceInputAfterTts();
  }
}

function _nativeSpeechRate() {
  const rate = 1 + ttsPlaybackSpeed / 100;
  return Math.min(10, Math.max(0.1, rate));
}

function _hasPuterTts() {
  return Boolean(window.puter?.ai?.txt2speech);
}

async function createPuterTtsHandle(text) {
  if (!_hasPuterTts()) {
    return null;
  }

  try {
    const audio = await window.puter.ai.txt2speech(text, {
      language: "en-US",
      engine: "neural",
    });

    if (!audio || typeof audio.play !== "function") {
      return null;
    }

    let onended = null;
    let onerror = null;
    const finish = () => {
      if (onended) onended();
    };
    const fail = () => {
      if (onerror) onerror();
    };

    if (typeof audio.addEventListener === "function") {
      audio.addEventListener("ended", finish, { once: true });
      audio.addEventListener("error", fail, { once: true });
    } else {
      audio.onended = finish;
      audio.onerror = fail;
    }

    return {
      kind: "puter",
      pause() {
        try {
          audio.pause();
        } catch (e) {}
      },
      play() {
        return Promise.resolve(audio.play());
      },
      set onended(fn) {
        onended = fn;
      },
      set onerror(fn) {
        onerror = fn;
      },
    };
  } catch (error) {
    console.warn("Puter TTS failed:", error);
    return null;
  }
}

function createNativeTtsHandle(text) {
  if (!("speechSynthesis" in window) || !window.SpeechSynthesisUtterance) {
    return null;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = _nativeSpeechRate();

  let onended = null;
  let onerror = null;

  utterance.onend = () => {
    if (onended) onended();
  };
  utterance.onerror = () => {
    if (onerror) onerror();
  };

  return {
    kind: "native",
    pause() {
      speechSynthesis.cancel();
    },
    play() {
      try {
        speechSynthesis.cancel();
        speechSynthesis.speak(utterance);
        return Promise.resolve();
      } catch (err) {
        return Promise.reject(err);
      }
    },
    set onended(fn) {
      onended = fn;
    },
    set onerror(fn) {
      onerror = fn;
    },
  };
}

async function createAssistantTtsHandle(text) {
  if (ttsPlaybackSpeed === 0) {
    const puterHandle = await createPuterTtsHandle(text);
    if (puterHandle) {
      return puterHandle;
    }
  }

  const nativeHandle = createNativeTtsHandle(text);
  if (nativeHandle) {
    return nativeHandle;
  }

  if (ttsPlaybackSpeed !== 0) {
    const puterHandle = await createPuterTtsHandle(text);
    if (puterHandle) {
      return puterHandle;
    }
  }

  return null;
}

async function playAssistantTts(text, { onStart } = {}) {
  if (!text) return;
  stopTtsPlayback();
  const playbackGeneration = ttsPlaybackGeneration;
  ttsPlaybackPending = true;

  try {
    if (speechRecognizer && speechRecognizer.isRecording) {
      stopHandsFreeRecognition();
      window.__speechPausedForTTS = true;
    }
  } catch (e) {}

  const handle = await createAssistantTtsHandle(text);
  if (playbackGeneration !== ttsPlaybackGeneration) {
    ttsPlaybackPending = false;
    try {
      handle?.pause?.();
    } catch (e) {}
    return;
  }

  ttsPlaybackPending = false;
  currentTtsAudio = handle;
  if (!currentTtsAudio) {
    console.warn("Failed to generate TTS audio.");
    showToast("Voice playback is unavailable", "error");
    resumeVoiceInputAfterTts();
    return;
  }

  if (onStart) {
    try {
      onStart(currentTtsAudio);
    } catch (e) {}
  }

  const interruptBtn = document.getElementById("interruptBtn");
  if (interruptBtn) interruptBtn.style.display = "inline-block";
  _showTTSBanner(true);

  const finishPlayback = () => {
    stopTtsPlayback();
    resumeVoiceInputAfterTts();
  };

  // Watchdog: if onended never fires (browser tab hidden, audio error), force-resume.
  if (ttsResumeWatchdogTimer) clearTimeout(ttsResumeWatchdogTimer);
  ttsResumeWatchdogTimer = setTimeout(() => {
    ttsResumeWatchdogTimer = null;
    if (currentTtsAudio) {
      console.warn("TTS watchdog: forcing resume");
      finishPlayback();
    }
  }, TTS_RESUME_WATCHDOG_MS);

  currentTtsAudio.onended = finishPlayback;
  currentTtsAudio.onerror = finishPlayback;

  try {
    await currentTtsAudio.play();
  } catch (error) {
    console.warn("TTS playback failed:", error);
    showToast("Could not play the assistant voice", "error");
    finishPlayback();
  }
}

// Helpers for hands-free speech-to-text control
function startHandsFreeRecognition() {
  if (!speechRecognizer?.recognition) {
    showToast(
      "Hands-free mode needs native speech recognition. Use the mic button instead.",
      "info",
    );
    return false;
  }
  if (speechRecognizer.isRecording) return true;

  const inputEl = document.getElementById("messageInput");
  if (!inputEl) return false;
  const micBtn = document.getElementById("micBtn");
  if (micBtn) {
    micBtn.classList.add("recording");
    micBtn.innerHTML = "Stop";
  }

  try {
    speechRecognizer.start(
      (text) => {
        try {
          if (currentTtsAudio) return; // echo guard: bot is speaking
          const voiceCommand = parseFlowVoiceCommand(text);
          if (voiceCommand) {
            clearVoiceSilenceTimer();
            executeFlowVoiceCommand(voiceCommand);
            autoResizeTextarea(inputEl);
            _setDictationPreview("");
            return;
          }

          const parsed = parsePunctuation(text);
          inputEl.value = (inputEl.value || "") + parsed;
          autoResizeTextarea(inputEl);
          _setDictationPreview("");

          scheduleVoiceAutoSend(inputEl);
        } catch (e) {
          console.warn("dictation final handler error:", e);
        }
      },
      (interim) => {
        try {
          if (currentTtsAudio) return;
          _setDictationPreview(interim);
        } catch (e) {
          console.warn("dictation interim handler error:", e);
        }
      },
      () => {
        // Update the mic button state
        const mic = document.getElementById("micBtn");
        if (mic) {
          mic.classList.remove("recording");
          mic.innerHTML = "Mic";
        }
        // gentle restart if still in hands-free mode
        if (
          handsFreeMode &&
          speechRecognizer &&
          !speechRecognizer.isRecording
        ) {
          const attempt = _handsFreeRestartAttempts;
          const delay = Math.min(200 * Math.pow(2, attempt), 5000);
          setTimeout(() => {
            try {
              if (!handsFreeMode) return;
              if (!speechRecognizer.isRecording) {
                const started = startHandsFreeRecognition();
                if (started) {
                  _handsFreeRestartAttempts = 0;
                } else {
                  _handsFreeRestartAttempts = Math.min(attempt + 1, 5);
                }
              }
            } catch (e) {
              console.warn("hands-free restart error:", e);
            }
          }, delay);
        }
      },
      (err) => {
        console.warn("Speech error:", err);
      },
    );
    return true;
  } catch (e) {
    console.warn("startHandsFreeRecognition error:", e);
    if (micBtn) {
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "Mic";
    }
    return false;
  }
}

function stopHandsFreeRecognition() {
  try {
    if (speechRecognizer && speechRecognizer.isRecording)
      speechRecognizer.stop();
  } catch (e) {
    console.warn("stopHandsFreeRecognition error:", e);
  }
  const mic = document.getElementById("micBtn");
  if (mic) {
    mic.classList.remove("recording");
    mic.innerHTML = "Mic";
  }
  _setDictationPreview("");
}

function interruptAssistant() {
  // Stop any TTS and resume listening if appropriate
  try {
    stopTtsPlayback({ resumeVoiceInput: true });
  } catch (e) {
    console.warn("interruptAssistant error:", e);
  }
}

function toggleVoiceMode() {
  handsFreeMode = !handsFreeMode;
  const btn = document.getElementById("voiceModeBtn");
  const indicator = document.getElementById("voiceModeIndicator");
  const inputArea = document.querySelector(".input-area");
  if (btn) btn.classList.toggle("active", handsFreeMode);
  if (indicator) indicator.textContent = handsFreeMode ? "Voice" : "Text";
  if (inputArea) inputArea.classList.toggle("hands-free-active", handsFreeMode);
  stopTtsPlayback();
  if (!handsFreeMode) {
    clearVoiceSilenceTimer();
    _handsFreeRestartAttempts = 0;
  }

  showToast(
    handsFreeMode
      ? "Conversational Mode ON - speak, auto-send, auto-play response"
      : "Conversational Mode OFF - dictation only",
    "info",
  );

  // Start/stop continuous recording when toggling hands-free
  try {
    if (handsFreeMode) {
      if (!speechRecognizer || !speechRecognizer.recognition) {
        showToast("Speech not supported in this browser", "error");
        // Restore the toggle state
        handsFreeMode = false;
        if (btn) btn.classList.toggle("active", false);
        if (indicator) indicator.textContent = "Text";
        if (inputArea) inputArea.classList.toggle("hands-free-active", false);
        return;
      }

      // Start centralized hands-free recognition
      startHandsFreeRecognition();
    } else {
      // Turn hands-free OFF -> stop recording via helper
      stopHandsFreeRecognition();
    }
  } catch (e) {
    console.warn("toggleVoiceMode error:", e);
  }
}

