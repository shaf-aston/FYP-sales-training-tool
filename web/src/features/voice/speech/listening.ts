// When is the learner talking? Loudness against the room's own noise, frame by frame (50 ms). Plain TypeScript, no
// browser APIs, so it can be checked on its own (listening.check.ts).
//
// The room's noise is the quietest frame so far, not only the first moments: a learner who starts talking the
// instant they tap the mic would otherwise have their voice taken as the noise, never be heard, and lose the turn.
// It is also capped, so even a voice-only start keeps the bar within reach of ordinary speech.

export interface Vad {
  overNoise: number;
  minLevel: number;
  maxFloor: number;
  endSilenceMs: number;
  noSpeechMs: number;
}

export type Heard = "listening" | "speaking" | "finished" | "nothing";

export class Listening {
  private floor = Infinity;
  private heard = false;
  private quietSince = 0;
  private readonly vad: Vad;
  private readonly started: number;

  constructor(vad: Vad, started: number) {
    this.vad = vad;
    this.started = started;
  }

  /** One frame's loudness (RMS) at time `now` (ms): what that means for the recording. */
  frame(level: number, now: number): Heard {
    this.floor = Math.min(this.floor, level, this.vad.maxFloor);   // the quietest frame yet, never above the cap
    const speaking = level > Math.max(this.vad.minLevel, this.floor * this.vad.overNoise);
    if (speaking) {
      this.heard = true;
      this.quietSince = 0;
      return "speaking";
    }
    if (this.heard) {
      this.quietSince ||= now;
      return now - this.quietSince > this.vad.endSilenceMs ? "finished" : "listening";
    }
    return now - this.started > this.vad.noSpeechMs ? "nothing" : "listening";
  }
}
