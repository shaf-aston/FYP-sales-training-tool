// Text-to-speech. The server's voice first (engine set in config/limits.yaml), the browser's own voice
// when the server has none. Plain TypeScript, no React.

import { api } from "@/lib/api/client";
import { config } from "@/lib/config";

interface Handle {
  pause(): void;
  play(): Promise<void>;
  onended: () => void;
  onerror: () => void;
}

interface TtsOptions {
  language: string;
  watchdogMs: number;
  /** Fires when audible playback starts (true) or ends (false). */
  onSpeaking: (on: boolean) => void;
  /** Fires when playback ended by itself (or the watchdog), so the mic can resume. Not fired by stop(). */
  onFinish: () => void;
  onError: (message: string) => void;
}

export const ttsSupported = () => typeof window !== "undefined" && "speechSynthesis" in window;

const nativeRate = (speed: number) => Math.min(config.voice.rateClamp.max, Math.max(config.voice.rateClamp.min, 1 + speed / 100));

export class Tts {
  private generation = 0;
  private pending = false;
  private handle: Handle | null = null;
  private watchdog: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly opts: TtsOptions) {}

  /** True from the moment speak() is called until playback ends. */
  get busy() {
    return this.pending || this.handle !== null;
  }

  async speak(text: string, speed: number) {
    if (!text.trim()) return;
    this.stop();
    const mine = this.generation;
    this.pending = true;

    const handle = await this.createHandle(text, speed);
    if (mine !== this.generation) {
      handle?.pause(); // a newer speak() or stop() overtook this one
      return;
    }
    this.pending = false;
    this.handle = handle;
    if (!handle) {
      this.opts.onError("Voice playback is unavailable");
      this.opts.onFinish();
      return;
    }

    this.opts.onSpeaking(true);
    const finish = () => {
      if (mine !== this.generation) return;
      this.stop();
      this.opts.onFinish();
    };
    // If "ended" never arrives (hidden tab, audio error) force the mic back after a while.
    this.watchdog = setTimeout(finish, this.opts.watchdogMs);
    handle.onended = finish;
    handle.onerror = finish;
    try {
      await handle.play();
    } catch {
      this.opts.onError("Could not play the assistant voice");
      finish();
    }
  }

  /** Cancels current and in-flight playback. Does not resume the mic. */
  stop() {
    this.generation += 1;
    this.pending = false;
    if (this.watchdog) clearTimeout(this.watchdog);
    this.watchdog = null;
    const had = this.handle;
    this.handle = null;
    if (had) {
      had.onended = () => {};
      had.onerror = () => {};
      had.pause();
      this.opts.onSpeaking(false);
    }
  }

  private async createHandle(text: string, speed: number): Promise<Handle | null> {
    return (await this.serverHandle(text, speed)) ?? this.nativeHandle(text, speed);
  }

  private async serverHandle(text: string, speed: number): Promise<Handle | null> {
    const blob = await api.speech(text);
    if (!blob) return null;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = nativeRate(speed);
    const handle: Handle = {
      pause: () => audio.pause(),
      play: async () => audio.play(),
      onended: () => {},
      onerror: () => {},
    };
    const done = (then: () => void) => () => { URL.revokeObjectURL(url); then(); };
    audio.addEventListener("ended", done(() => handle.onended()), { once: true });
    audio.addEventListener("error", done(() => handle.onerror()), { once: true });
    return handle;
  }

  private nativeHandle(text: string, speed: number): Handle | null {
    if (!ttsSupported() || typeof SpeechSynthesisUtterance === "undefined") return null;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = this.opts.language;
    utterance.rate = nativeRate(speed);
    const handle: Handle = {
      pause: () => speechSynthesis.cancel(),
      play: async () => {
        speechSynthesis.cancel();
        speechSynthesis.speak(utterance);
      },
      onended: () => {},
      onerror: () => {},
    };
    utterance.onend = () => handle.onended();
    utterance.onerror = () => handle.onerror();
    return handle;
  }
}
