"use client";

// Voice state for the whole app: dictation into the message box, spoken replies and hands-free mode.
// The browser work lives in ./speech/*; this file wires it to React state and the other features.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useToast } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import { config, storageKeys } from "@/lib/config";
import { stageMeta, strategyMeta } from "@/lib/labels";
import { useStoredState } from "@/lib/useStoredState";
import { useDraft } from "@/features/chat/DraftContext";
import { useSession } from "@/features/session/SessionContext";
import { SpeechRecognizer, speechSupported, type StopState } from "./speech/recognizer";
import { Tts, ttsSupported } from "./speech/tts";
import { parseFlowCommand, parsePunctuation, type FlowCommand } from "./voiceCommands";

interface VoiceValue {
  /** Can this browser dictate? False until the browser has been checked. */
  supported: boolean;
  /** Can this browser read replies aloud? */
  ttsSupported: boolean;
  dictating: boolean;
  transcribing: boolean;
  toggleDictation: () => void;
  /** Live words being heard but not final yet. */
  interim: string;
  handsFree: boolean;
  toggleHandsFree: () => void;
  speaking: boolean;
  speak: (text: string) => void;
  stop: () => void;
  /** Stop speaking and go back to listening if hands-free is on. */
  interrupt: () => void;
  autoSend: boolean;
  setAutoSend: (on: boolean) => void;
  /** -50..50 percent change from normal speed. */
  speed: number;
  setSpeed: (n: number) => void;
}

const VoiceContext = createContext<VoiceValue | null>(null);

const parseAutoSend = (raw: string) => raw !== "false";
const parseSpeed = (raw: string) => {
  const n = parseInt(raw, 10);
  const { min, max } = config.voice.speedRange;
  return Number.isNaN(n) ? undefined : Math.min(max, Math.max(min, n));
};

export function VoiceProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const draft = useDraft();
  const session = useSession();
  const [autoSend, setAutoSend] = useStoredState(storageKeys.autoSendDictation, true, parseAutoSend);
  const [speed, setSpeed] = useStoredState(storageKeys.ttsSpeed, 0, parseSpeed);
  const [supported, setSupported] = useState(false);
  const [ttsOk, setTtsOk] = useState(false);
  const [dictating, setDictating] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [interim, setInterim] = useState("");
  const [handsFree, setHandsFree] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  // Latest values for callbacks that outlive a render (recognizer and speech events).
  const live = useRef({ draft, session, autoSend, speed, toast });
  useEffect(() => {
    live.current = { draft, session, autoSend, speed, toast };
  });
  const handsFreeNow = useRef(false); // set synchronously on toggle, before React re-renders

  const recognizer = useRef<SpeechRecognizer | null>(null);
  const tts = useRef<Tts | null>(null);
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const restartAttempt = useRef(0);
  const pausedForTts = useRef(false);
  const startListening = useRef<() => boolean>(() => false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser capability is only known after hydration
    setSupported(speechSupported());
    setTtsOk(ttsSupported());
  }, []);

  const clearTimers = useCallback(() => {
    if (silenceTimer.current) clearTimeout(silenceTimer.current);
    if (restartTimer.current) clearTimeout(restartTimer.current);
    silenceTimer.current = null;
    restartTimer.current = null;
  }, []);

  const scheduleAutoSend = useCallback(() => {
    // Hands-free promises "speak, auto-send, auto-play", so it sends even if the setting is off.
    if (!live.current.autoSend && !handsFreeNow.current) return;
    if (silenceTimer.current) clearTimeout(silenceTimer.current);
    silenceTimer.current = setTimeout(() => {
      silenceTimer.current = null;
      void live.current.draft.submit();
    }, config.voice.silenceDelayMs);
  }, []);

  const runFlowCommand = useCallback(async (cmd: FlowCommand) => {
    const { session: s, toast: say } = live.current;
    if (!s.sessionId) return;
    try {
      if (cmd.type === "stage") {
        s.applyBotState(await api.setStage(s.sessionId, cmd.value));
        say(`Voice: moved to ${stageMeta(cmd.value).label}`, "info");
      } else {
        s.applyBotState(await api.setStrategy(s.sessionId, cmd.value));
        say(`Voice: approach set to ${strategyMeta(cmd.value).label}`, "info");
      }
    } catch (e) {
      if (!s.handleExpired(e)) say(`Voice command error: ${e instanceof ApiError ? e.message : "please try again"}`, "error");
    }
  }, []);

  const onFinal = useCallback(
    (text: string) => {
      if (tts.current?.busy) return; // echo guard: that is the coach talking, not the user
      const { session: s, draft: d } = live.current;
      setInterim("");
      const cmd = handsFreeNow.current && s.flowControls && s.mode === "seller" ? parseFlowCommand(text) : null;
      if (cmd) {
        if (silenceTimer.current) clearTimeout(silenceTimer.current);
        void runFlowCommand(cmd);
        return;
      }
      d.append(parsePunctuation(text));
      scheduleAutoSend();
    },
    [runFlowCommand, scheduleAutoSend],
  );

  const onInterim = useCallback((text: string) => {
    if (!tts.current?.busy) setInterim(text);
  }, []);

  const onStop = useCallback((state: StopState) => {
    setDictating(false);
    setTranscribing(false);
    setInterim("");
    live.current.draft.inputRef.current?.focus();
    // Hands-free keeps listening: restart with growing delays so a broken mic doesn't spin.
    if (!handsFreeNow.current || pausedForTts.current || state.canceled) return;
    const { base, max, attempts } = config.voice.restartBackoffMs;
    const attempt = restartAttempt.current;
    restartTimer.current = setTimeout(() => {
      restartTimer.current = null;
      if (!handsFreeNow.current || pausedForTts.current) return;
      restartAttempt.current = startListening.current() ? 0 : Math.min(attempt + 1, attempts);
    }, Math.min(base * 2 ** attempt, max));
  }, []);

  const onError = useCallback((message: string) => {
    setDictating(false);
    setInterim("");
    live.current.toast(message || "Microphone error", "error");
  }, []);

  const begin = useCallback(() => {
    recognizer.current ??= new SpeechRecognizer({
      language: config.voice.language,
      maxRecordingMs: config.voice.maxRecordingMs,
      puterLoadMs: config.voice.puterLoadMs,
    });
    const r = recognizer.current;
    if (r.isRecording || r.isTranscribing) return true;
    setDictating(true);
    const started = r.start(onFinal, onInterim, onStop, onError, setTranscribing);
    if (!started) setDictating(false);
    return started;
  }, [onFinal, onInterim, onStop, onError]);

  useEffect(() => {
    startListening.current = begin;
  }, [begin]);

  /** After the coach finishes (or is interrupted): bring the mic back, or give focus to the box. */
  const resumeAfterSpeech = useCallback(() => {
    pausedForTts.current = false;
    if (handsFreeNow.current) begin();
    else live.current.draft.inputRef.current?.focus();
  }, [begin]);

  const speak = useCallback(
    (text: string) => {
      const r = recognizer.current;
      if (r?.isRecording) {
        pausedForTts.current = true; // mic off while the coach talks, so it can't hear itself
        r.stop();
      }
      tts.current ??= new Tts({
        language: config.voice.language,
        watchdogMs: config.voice.ttsWatchdogMs,
        puterLoadMs: config.voice.puterLoadMs,
        onSpeaking: setSpeaking,
        onFinish: () => resumeAfterSpeech(),
        onError: (m) => live.current.toast(m, "error"),
      });
      void tts.current.speak(text, live.current.speed);
    },
    [resumeAfterSpeech],
  );

  const stop = useCallback(() => tts.current?.stop(), []);

  const interrupt = useCallback(() => {
    tts.current?.stop();
    resumeAfterSpeech();
  }, [resumeAfterSpeech]);

  const toggleDictation = useCallback(() => {
    if (!speechSupported()) return live.current.toast("Speech not supported in this browser", "error");
    const r = recognizer.current;
    if (r?.isTranscribing) return live.current.toast("Transcribing, please wait", "info");
    if (r?.isRecording) return r.stop();
    begin();
  }, [begin]);

  const toggleHandsFree = useCallback(() => {
    const on = !handsFreeNow.current;
    if (on && !speechSupported()) return live.current.toast("Speech not supported in this browser", "error");
    handsFreeNow.current = on;
    setHandsFree(on);
    tts.current?.stop();
    restartAttempt.current = 0;
    clearTimers();
    live.current.toast(
      on ? "Conversational Mode ON - speak, auto-send, auto-play response" : "Conversational Mode OFF - dictation only",
      "info",
    );
    if (on) begin();
    else {
      pausedForTts.current = false;
      recognizer.current?.stop();
      setInterim("");
    }
  }, [begin, clearTimers]);

  // Hands-free: read each NEW coach message aloud (never the history already on screen).
  const spokenId = useRef<string | undefined>(undefined);
  useEffect(() => {
    const last = [...session.messages].reverse().find((m) => m.role === "assistant" && !m.historical);
    if (!handsFree) {
      spokenId.current = last?.id;
      return;
    }
    if (last && last.id !== spokenId.current) {
      spokenId.current = last.id;
      speak(last.content);
    }
  }, [session.messages, handsFree, speak]);

  useEffect(
    () => () => {
      clearTimers();
      recognizer.current?.stop();
      tts.current?.stop();
    },
    [clearTimers],
  );

  const value = useMemo<VoiceValue>(
    () => ({
      supported,
      ttsSupported: ttsOk,
      dictating,
      transcribing,
      toggleDictation,
      interim,
      handsFree,
      toggleHandsFree,
      speaking,
      speak,
      stop,
      interrupt,
      autoSend,
      setAutoSend,
      speed,
      setSpeed,
    }),
    [supported, ttsOk, dictating, transcribing, toggleDictation, interim, handsFree, toggleHandsFree, speaking, speak, stop, interrupt, autoSend, setAutoSend, speed, setSpeed],
  );

  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>;
}

export function useVoice() {
  const ctx = useContext(VoiceContext);
  if (!ctx) throw new Error("useVoice must be used inside <VoiceProvider>");
  return ctx;
}
