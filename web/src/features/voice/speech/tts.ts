// Text-to-speech. The server's voice first (engine set in config/limits.yaml), the browser's own voice
// when the server has none. A reply is fetched a sentence at a time and the first plays as soon as it arrives,
// while the next is made: the wait is one sentence, not the whole reply. Plain TypeScript, no React.

import { api } from "@/lib/api/client";
import type { Speaker } from "@/lib/api/types";
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

/** The server's voice needs only audio playback; the browser's own voice is the fallback where there is one. */
export const ttsSupported = () => typeof window !== "undefined" && (typeof Audio !== "undefined" || "speechSynthesis" in window);

/** The reply as the pieces it is fetched in: sentences, a scrap too short to say alone joined to the next one. */
export function sentences(text: string): string[] {
  const parts = text.split(/(?<=[.!?…])\s+/).map((p) => p.trim()).filter(Boolean);
  const out: string[] = [];
  for (const p of parts) {
    if (out.length && out[out.length - 1].length < 4) out[out.length - 1] += ` ${p}`;
    else out.push(p);
  }
  return out;
}

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

  async speak(text: string, speed: number, speaker?: Speaker) {
    if (!text.trim()) return;
    this.stop();
    const mine = this.generation;
    this.pending = true;

    const handle = await this.createHandle(text, speed, speaker);
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
      this.opts.onError("Could not play the voice");
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

  private async createHandle(text: string, speed: number, speaker?: Speaker): Promise<Handle | null> {
    return (await this.serverHandle(text, speed, speaker)) ?? this.nativeHandle(text, speed);
  }

  /** The server's voice, sentence by sentence: each piece plays as soon as it is here, the next is fetched while it
   *  plays. A piece the server can't say ends the reply there (the words are on screen). */
  private async serverHandle(text: string, speed: number, speaker?: Speaker): Promise<Handle | null> {
    const parts = sentences(text);
    const fetches: Promise<Blob | null>[] = [api.speech(parts[0], speaker)];
    const fetchPart = (i: number) => (fetches[i] ??= i < parts.length ? api.speech(parts[i], speaker) : Promise.resolve(null));
    const first = await fetches[0];
    if (!first) return null;
    fetchPart(1); // the next one is being made while the first plays

    let audio: HTMLAudioElement | null = null;
    let url = "";
    let stopped = false;
    const handle: Handle = {
      pause: () => {
        stopped = true;
        audio?.pause();
        if (url) URL.revokeObjectURL(url);
      },
      play: async () => {
        for (let i = 0; i < parts.length && !stopped; i++) {
          const blob = i === 0 ? first : await fetchPart(i);
          if (!blob || stopped) break;
          fetchPart(i + 1);
          url = URL.createObjectURL(blob);
          audio = new Audio(url);
          audio.playbackRate = nativeRate(speed);
          const playing = audio;
          const ended = await new Promise<boolean>((resolve) => {
            playing.addEventListener("ended", () => resolve(true), { once: true });
            playing.addEventListener("error", () => resolve(false), { once: true });
            playing.play().catch(() => resolve(false));
          });
          URL.revokeObjectURL(url);
          url = "";
          if (!ended) {
            if (!stopped) handle.onerror();
            return;
          }
        }
        if (!stopped) handle.onended();
      },
      onended: () => {},
      onerror: () => {},
    };
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
