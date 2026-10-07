import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension; tsconfig does not allow it
import { grade, isDue, parseSchedule } from "./drillSchedule.ts";

const DAY = 86_400_000;
const intervals = [0, 1, 3, 7, 21];
const now = 1_000_000_000;

// new drill is due
assert.equal(isDue({}, "a", now), true);

// Yes raises level and pushes due date
let s = grade({}, "a", true, now, intervals);
assert.deepEqual(s.a, { level: 1, due: now + 1 * DAY });
assert.equal(isDue(s, "a", now), false);
assert.equal(isDue(s, "a", now + DAY), true);

// Not quite resets to 0 (due immediately)
s = grade(s, "a", true, now, intervals);
assert.equal(s.a.level, 2);
s = grade(s, "a", false, now, intervals);
assert.deepEqual(s.a, { level: 0, due: now });

// level capped at max
for (let i = 0; i < 10; i++) s = grade(s, "a", true, now, intervals);
assert.equal(s.a.level, intervals.length - 1);
assert.equal(s.a.due, now + 21 * DAY);

// duplicate id: grading the same id twice keeps one entry; other ids untouched
const base = grade({}, "b", true, now, intervals);
const twice = grade(grade(base, "a", true, now, intervals), "a", true, now, intervals);
assert.deepEqual(Object.keys(twice).sort(), ["a", "b"]);
assert.equal(twice.a.level, 2);
assert.equal(grade(base, "a", true, now, intervals).b, base.b);

// grading does not mutate the input
const frozen = Object.freeze({ z: { level: 1, due: 5 } });
grade(frozen, "z", true, now, intervals);
assert.equal(frozen.z.level, 1);

// corrupt saved data is dropped, not thrown
assert.deepEqual(parseSchedule("{not json"), {});
assert.deepEqual(parseSchedule('{"a":{"level":"x"},"b":{"level":1,"due":2}}'), { b: { level: 1, due: 2 } });

console.log("drillSchedule: all checks passed");
