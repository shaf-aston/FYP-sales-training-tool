// Run: node --experimental-strip-types web/src/features/skills/skillLog.check.ts
import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension
import { averages, change, parseLog, record, trend, weakest } from "./skillLog.ts";

const ids = ["needs_discovery", "rapport_building", "objection_handling"];
const entry = (sessionId: string, at: number, a: number, b: number, c: number) => ({
  sessionId,
  at,
  overall: Math.round((a + b + c) / 3),
  scores: { needs_discovery: a, rapport_building: b, objection_handling: c },
});

// bad storage never throws and drops what is not an entry
assert.deepEqual(parseLog(null), []);
assert.deepEqual(parseLog("not json"), []);
assert.deepEqual(parseLog('{"a":1}'), []);
assert.deepEqual(parseLog(JSON.stringify([entry("s1", 1, 50, 60, 70), { sessionId: "x" }, null])), [entry("s1", 1, 50, 60, 70)]);
assert.deepEqual(parseLog(JSON.stringify([{ ...entry("s1", 1, 50, 60, 70), scores: { a: "high" } }])), []);

// record: same session replaces, cap keeps the newest
let log = record([], entry("s1", 1, 40, 60, 70), 3);
log = record(log, entry("s1", 2, 45, 60, 70), 3);
assert.equal(log.length, 1);
assert.equal(log[0].scores.needs_discovery, 45);
log = record(log, entry("s2", 3, 55, 62, 60), 3);
log = record(log, entry("s3", 4, 65, 64, 50), 3);
log = record(log, entry("s4", 5, 75, 66, 40), 3);
assert.deepEqual(log.map((e) => e.sessionId), ["s2", "s3", "s4"]);
// re-scoring keeps the session's place and first time
const rescored = record(log, entry("s3", 99, 1, 1, 1), 3);
assert.deepEqual(rescored.map((e) => [e.sessionId, e.at]), [["s2", 3], ["s3", 4], ["s4", 5]]);
assert.equal(rescored[1].scores.needs_discovery, 1);
// scores outside 0-100 are not trusted from storage
assert.deepEqual(parseLog(JSON.stringify([{ ...entry("s1", 1, 50, 60, 70), scores: { a: 1e6 } }])), []);

// averages over a window, trend in order
assert.deepEqual(averages(log, ids, 2), { needs_discovery: 70, rapport_building: 65, objection_handling: 45 });
assert.deepEqual(trend(log, "needs_discovery"), [55, 65, 75]);
assert.deepEqual(averages([], ids, 5), {});

// change: latest vs the average before it
assert.equal(change(log, "needs_discovery", 2), 15);   // 75 - avg(55, 65)
assert.equal(change(log, "objection_handling", 5), -15);
assert.equal(change([entry("s1", 1, 50, 50, 50)], "needs_discovery", 3), null);

// weakest: furthest below its target; none below -> null; ties -> first
const targets = { needs_discovery: 70, rapport_building: 70, objection_handling: 70 };
assert.equal(weakest({ needs_discovery: 75, rapport_building: 66, objection_handling: 40 }, ids, targets), "objection_handling");
assert.equal(weakest({ needs_discovery: 80, rapport_building: 90, objection_handling: 70 }, ids, targets), null);
assert.equal(weakest({ needs_discovery: 60, rapport_building: 60, objection_handling: 90 }, ids, targets), "needs_discovery");

console.log("skillLog ok");
