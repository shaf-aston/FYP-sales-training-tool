// Run: node --experimental-strip-types web/src/features/voice/speech/listening.check.ts
import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension
import { Listening } from "./listening.ts";

const VAD = { overNoise: 3, minLevel: 0.012, maxFloor: 0.02, endSilenceMs: 900, noSpeechMs: 8000 };
const run = (levels: number[]) => {
  const l = new Listening(VAD, 0);
  return levels.map((lv, i) => l.frame(lv, i * 50));
};

// a quiet room, then talk, then quiet: heard, then finished after the silence
const quiet = run([0.004, 0.004, 0.005, 0.004, 0.004, 0.004, 0.08, 0.1, 0.09, ...Array(20).fill(0.004)]);
assert.ok(quiet.includes("speaking"));
assert.equal(quiet.at(-1), "finished");

// talking from the very first frame (the bug: the voice became the "noise" and was never heard)
const instant = run([0.09, 0.1, 0.08, 0.11, 0.09, 0.1, 0.03, 0.09, 0.1]);
assert.ok(instant.filter((h) => h === "speaking").length >= 6, `instant start must be heard: ${instant}`);

// nothing said at all: given up after noSpeechMs
const silent = run(Array(170).fill(0.004));
assert.equal(silent.at(-1), "nothing");

// a noisy room does not count as talking
const hum = run(Array(40).fill(0.015));
assert.ok(!hum.includes("speaking"));
console.log("listening: all checks passed");
