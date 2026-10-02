// Speech-to-text. Native Web Speech first (live interim text); Puter speech2txt via MediaRecorder as fallback.
// Plain TypeScript, no React. Browser APIs are touched only inside methods, never at import time.

import { loadPuter } from "./puter";

interface NativeResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface NativeEvent {
  resultIndex: number;
  results: ArrayLike<NativeResult>;
}
interface NativeRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: NativeEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  start(): void;
  stop(): void;
}
type NativeCtor = new () => NativeRecognition;

export interface StopState {
  mode: "native" | "puter";
  canceled: boolean;
}

export interface RecognizerOptions {
  language: string;
  maxRecordingMs: number;
  /** How long to wait for Puter's script before giving up. */
  puterLoadMs: number;
}

const nativeCtor = (): NativeCtor | null => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: NativeCtor; webkitSpeechRecognition?: NativeCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

const canRecordAudio = () =>
  typeof window !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia) && typeof window.MediaRecorder !== "undefined";

/** True if this browser can dictate at all (natively, or by recording audio for Puter). */
export const speechSupported = () => nativeCtor() !== null || canRecordAudio();
export const nativeSpeechSupported = () => nativeCtor() !== null;

const AUDIO_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
const pickAudioType = () => AUDIO_TYPES.find((t) => MediaRecorder.isTypeSupported?.(t)) ?? "";

const NATIVE_RESTART_MS = 100;
const PUTER_MODEL = "gpt-4o-mini-transcribe";

export class SpeechRecognizer {
  isRecording = false;
  isTranscribing = false;

  private native: NativeRecognition | null = null;
  private mode: "native" | "puter" | null = null;
  private ignoreOnEnd = false;
  private stopRequested = false;
  private maxTimer: ReturnType<typeof setTimeout> | null = null;
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private onFinal: (text: string) => void = () => {};
  private onInterim: (text: string) => void = () => {};
  private onStop: (state: StopState) => void = () => {};
  private onError: (message: string) => void = () => {};
  private onTranscribing: (on: boolean) => void = () => {};

  constructor(private readonly opts: RecognizerOptions) {}

  /** Returns false if recording could not begin (an error is also reported through onError). */
  start(
    onFinal: (text: string) => void,
    onInterim: (text: string) => void,
    onStop: (state: StopState) => void,
    onError: (message: string) => void,
    onTranscribing: (on: boolean) => void = () => {},
  ): boolean {
    if (this.isRecording || this.isTranscribing) return true;
    Object.assign(this, { onFinal, onInterim, onStop, onError, onTranscribing });

    if (nativeCtor()) return this.startNative();
    if (canRecordAudio()) return this.startPuter();
    onError("Voice recording is not supported in this browser");
    return false;
  }

  stop() {
    if (!this.isRecording && !this.isTranscribing) return;
    this.stopRequested = true;
    this.clearMaxTimer();

    if (this.mode === "native" && this.native) {
      this.isRecording = false;
      this.ignoreOnEnd = true;
      try {
        this.native.stop();
      } catch {
        /* already stopped */
      }
      return;
    }
    if (this.mode === "puter" && this.recorder) {
      if (this.isTranscribing) return;
      try {
        this.recorder.stop();
      } catch {
        /* already stopped */
      }
      return;
    }
    this.isRecording = false;
    this.isTranscribing = false;
    this.mode = null;
    this.onStop({ mode: "native", canceled: true });
  }

  private armMaxTimer() {
    this.maxTimer = setTimeout(() => {
      if (this.isRecording) this.stop();
    }, this.opts.maxRecordingMs);
  }

  private clearMaxTimer() {
    if (this.maxTimer) clearTimeout(this.maxTimer);
    this.maxTimer = null;
  }

  private ensureNative(): NativeRecognition | null {
    if (this.native) return this.native;
    const Ctor = nativeCtor();
    if (!Ctor) return null;
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = this.opts.language;

    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) this.onFinal(`${r[0].transcript.trim()} `);
        else interim += r[0].transcript;
      }
      this.onInterim(interim);
    };
    rec.onend = () => {
      if (this.isRecording && !this.ignoreOnEnd) {
        // The browser ends sessions on its own after a pause; keep listening.
        setTimeout(() => {
          try {
            rec.start();
          } catch {
            /* the UI recovers when the user stops */
          }
        }, NATIVE_RESTART_MS);
        return;
      }
      this.isRecording = false;
      this.mode = null;
      this.onStop({ mode: "native", canceled: this.stopRequested });
    };
    rec.onerror = (event) => {
      if (event.error === "no-speech") return;
      if (event.error === "audio-capture" || event.error === "not-allowed") {
        this.ignoreOnEnd = true;
        this.isRecording = false;
      }
      this.onError(event.error);
    };
    this.native = rec;
    return rec;
  }

  private startNative(): boolean {
    const rec = this.ensureNative();
    if (!rec) return false;
    this.isRecording = true;
    this.ignoreOnEnd = false;
    this.stopRequested = false;
    this.mode = "native";
    try {
      rec.start();
    } catch {
      this.isRecording = false;
      this.mode = null;
      this.onError("Could not start the microphone");
      return false;
    }
    this.armMaxTimer();
    return true;
  }

  private startPuter(): boolean {
    this.isRecording = true;
    this.ignoreOnEnd = false;
    this.stopRequested = false;
    this.mode = "puter";
    void this.recordForPuter();
    this.armMaxTimer();
    return true;
  }

  private async recordForPuter() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!this.isRecording) return releaseStream(stream);
      this.stream = stream;
      this.chunks = [];
      const type = pickAudioType();
      const recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
      this.recorder = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data?.size) this.chunks.push(e.data);
      };
      recorder.onstop = () => void this.finishPuter(type);
      recorder.start();
      this.onInterim("Recording...");
    } catch (error) {
      this.isRecording = false;
      this.mode = null;
      this.resetPuter();
      this.onError(error instanceof Error ? error.message : "Voice recording is not supported in this browser");
      this.onStop({ mode: "puter", canceled: false });
    }
  }

  private async finishPuter(type: string) {
    this.clearMaxTimer();
    this.isTranscribing = true;
    this.onTranscribing(true);
    try {
      const blob = new Blob(this.chunks, { type: type || "audio/webm" });
      if (!blob.size) throw new Error("No audio captured for transcription");
      const ai = await loadPuter(this.opts.puterLoadMs);
      const result = await ai.speech2txt({ file: blob, model: PUTER_MODEL });
      const text = String(typeof result === "string" ? result : (result?.text ?? "")).trim();
      if (text) this.onFinal(`${text} `);
    } catch (error) {
      this.onError(error instanceof Error ? error.message : "Speech transcription failed");
    } finally {
      this.isTranscribing = false;
      this.isRecording = false;
      this.mode = null;
      this.resetPuter();
      this.onTranscribing(false);
      this.onStop({ mode: "puter", canceled: this.stopRequested });
    }
  }

  private resetPuter() {
    this.recorder = null;
    this.chunks = [];
    releaseStream(this.stream);
    this.stream = null;
  }
}

function releaseStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((t) => {
    try {
      t.stop();
    } catch {
      /* ignore */
    }
  });
}
