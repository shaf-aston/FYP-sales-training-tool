// Speech-to-text. The mic is recorded and our server turns it into text (/api/dictate: Parakeet on the server, then
// Groq), the same in every browser; the recording stops by itself a moment after the learner stops talking, so
// hands-free needs no clicks. The browser's own recognition (Web Speech) is only the fallback where recording isn't
// possible: it isn't in Firefox, cuts off at pauses, sends audio to Google, and in Brave (and a headless Chrome) it
// starts, hears nothing and never says so. Plain TypeScript, no React. Browser APIs are touched only inside methods.

import { api, errorText } from "@/lib/api/client";
import { config } from "@/lib/config";

/** Browser speech error codes in plain words. */
const MIC_ERRORS: Record<string, string> = {
  "not-allowed": "Microphone blocked. Allow it in your browser settings, or type instead.",
  "service-not-allowed": "Microphone blocked. Allow it in your browser settings, or type instead.",
  "audio-capture": "No microphone found. Plug one in, or type instead.",
  network: "Voice needs an internet connection. Type instead for now.",
};

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
  canceled: boolean;
}

interface RecognizerOptions {
  language: string;
  maxRecordingMs: number;
}

const nativeCtor = (): NativeCtor | null => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: NativeCtor; webkitSpeechRecognition?: NativeCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

const canRecordAudio = () =>
  typeof window !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia) && typeof window.MediaRecorder !== "undefined";

/** True if this browser can dictate at all (natively, or by recording audio for the server). */
export const speechSupported = () => nativeCtor() !== null || canRecordAudio();

const AUDIO_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
const pickAudioType = () => AUDIO_TYPES.find((t) => MediaRecorder.isTypeSupported?.(t)) ?? "";

export class SpeechRecognizer {
  isRecording = false;
  isTranscribing = false;

  private native: NativeRecognition | null = null;
  private mode: "native" | "server" | null = null;
  /** The native one failed with "network" (Brave): record for the server from now on. */
  private nativeBroken = false;
  private audioCtx: AudioContext | null = null;
  private vadTimer: ReturnType<typeof setInterval> | null = null;
  /** The recording ended by itself with nothing said: nothing is sent. */
  private discard = false;
  /** Speech was heard in this recording (the loudness watch); a stop before any is sent nowhere. */
  private heard = false;
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

    if (canRecordAudio()) return this.startServer();
    if (nativeCtor() && !this.nativeBroken) return this.startNative();
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
    if (this.mode === "server" && this.recorder) {
      if (this.isTranscribing) return;
      // stopped before a word was said (the reply started playing, or the learner changed their mind): send nothing
      if (!this.heard && this.vadTimer) this.discard = true;
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
    this.onStop({ canceled: true });
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
        }, config.voice.nativeRestartMs);
        return;
      }
      this.isRecording = false;
      this.mode = null;
      this.onStop({ canceled: this.stopRequested });
    };
    rec.onerror = (event) => {
      if (event.error === "no-speech") return;
      if (event.error === "network" && canRecordAudio()) {
        // Brave (and an offline Chrome) has the API but no service behind it: record for our server instead
        this.nativeBroken = true;
        this.ignoreOnEnd = true;
        this.isRecording = false;
        this.mode = null;
        try {
          rec.stop();
        } catch {
          /* already stopped */
        }
        this.startServer();
        return;
      }
      if (event.error === "audio-capture" || event.error === "not-allowed") {
        this.ignoreOnEnd = true;
        this.isRecording = false;
      }
      this.onError(MIC_ERRORS[event.error] ?? "The microphone stopped. Try again, or type instead.");
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

  private startServer(): boolean {
    this.isRecording = true;
    this.ignoreOnEnd = false;
    this.stopRequested = false;
    this.mode = "server";
    void this.recordForServer();
    this.armMaxTimer();
    return true;
  }

  private async recordForServer() {
    this.discard = false;
    this.heard = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      if (!this.isRecording) return releaseStream(stream);
      this.stream = stream;
      this.chunks = [];
      const type = pickAudioType();
      const recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
      this.recorder = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data?.size) this.chunks.push(e.data);
      };
      recorder.onstop = () => void this.finishServer(type);
      recorder.start(250);
      this.onInterim("Listening…");
      this.watchForSilence(stream);
    } catch (error) {
      this.isRecording = false;
      this.mode = null;
      this.resetRecording();
      const denied = error instanceof DOMException && error.name === "NotAllowedError";
      this.onError(denied ? MIC_ERRORS["not-allowed"] : "Voice recording is not supported in this browser");
      this.onStop({ canceled: false });
    }
  }

  /** Stops the recording a moment after the learner stops talking (or if they never start), judged by loudness
   *  against the room's own noise: no extra model, and nothing leaves the browser until the turn is done. */
  private watchForSilence(stream: MediaStream) {
    const vad = config.voice.vad;
    try {
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      this.audioCtx = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      const started = performance.now();
      let floor = Infinity;
      let heard = false;
      let quietSince = 0;
      this.vadTimer = setInterval(() => {
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += v * v;
        const level = Math.sqrt(sum / buf.length);
        const now = performance.now();
        if (now - started < vad.calibrateMs) floor = Math.min(floor, level);
        const speaking = level > Math.max(vad.minLevel, (Number.isFinite(floor) ? floor : 0) * vad.overNoise);
        if (speaking) {
          if (!heard) this.onInterim("Hearing you…");
          heard = true;
          this.heard = true;
          quietSince = 0;
        } else if (heard) {
          quietSince ||= now;
          if (now - quietSince > vad.endSilenceMs) this.autoStop(false); // they finished: send it
        } else if (now - started > vad.noSpeechMs) {
          this.autoStop(true); // nothing said: send nothing (hands-free listens again)
        }
      }, 50);
    } catch {
      /* no Web Audio: the learner taps stop, as before */
    }
  }

  /** Ends the recording by itself, not as the learner's stop: hands-free carries on listening after it. */
  private autoStop(discard: boolean) {
    this.discard = discard;
    this.stopWatching();
    this.clearMaxTimer();
    try {
      this.recorder?.stop();
    } catch {
      /* already stopped */
    }
  }

  private stopWatching() {
    if (this.vadTimer) clearInterval(this.vadTimer);
    this.vadTimer = null;
    void this.audioCtx?.close().catch(() => {});
    this.audioCtx = null;
  }

  private async finishServer(type: string) {
    this.clearMaxTimer();
    this.stopWatching();
    const blob = new Blob(this.chunks, { type: type || "audio/webm" });
    if (!blob.size || this.discard) {
      this.discard = false;
      this.isRecording = false;
      this.mode = null;
      this.resetRecording();
      this.onInterim("");
      this.onStop({ canceled: this.stopRequested });
      return;
    }
    this.isTranscribing = true;
    this.onTranscribing(true);
    this.onInterim("");
    try {
      const text = (await api.dictate(blob)).trim(); // "" when nothing could be heard: nothing to add
      if (text) this.onFinal(`${text} `);
    } catch (error) {
      this.onError(errorText(error, "Couldn't make that out. Try again, or type it."));
    } finally {
      this.isTranscribing = false;
      this.isRecording = false;
      this.mode = null;
      this.resetRecording();
      this.onTranscribing(false);
      this.onStop({ canceled: this.stopRequested });
    }
  }

  private resetRecording() {
    this.stopWatching();
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
