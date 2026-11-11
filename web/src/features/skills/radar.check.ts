// Run: node --experimental-strip-types web/src/features/skills/radar.check.ts
import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension
import { axisPoint, labelLines, labelPlace, polygon, sentenceCase } from "./radar.ts";

// first axis points up, full value reaches the edge
assert.deepEqual(axisPoint(0, 4, 100, 100, 50), { x: 50, y: 0 });
// clockwise: second of four points right
assert.deepEqual(axisPoint(1, 4, 100, 100, 50), { x: 100, y: 50 });
// half value is half way; values are clamped to 0..max
assert.deepEqual(axisPoint(2, 4, 50, 100, 50), { x: 50, y: 75 });
assert.deepEqual(axisPoint(3, 4, 250, 100, 50), { x: 0, y: 50 });
assert.deepEqual(axisPoint(0, 4, -5, 100, 50), { x: 50, y: 50 });

// polygon: one point per value, missing values at the centre
assert.equal(polygon([100, undefined, 100, 100], 100, 50), "50,0 50,50 50,100 0,50");

// labels: top is centred, right side starts, left side ends
assert.equal(labelPlace(0, 4, 50, 10).anchor, "middle");
assert.equal(labelPlace(1, 4, 50, 10).anchor, "start");
assert.equal(labelPlace(3, 4, 50, 10).anchor, "end");

// labels: sentence case, two lines from two words on
assert.equal(sentenceCase("needs discovery"), "Needs discovery");
assert.deepEqual(labelLines("flow"), ["Flow"]);
assert.deepEqual(labelLines("conversation flow"), ["Conversation", "flow"]);
assert.deepEqual(labelLines("one two three"), ["One two", "three"]);

console.log("radar ok");
