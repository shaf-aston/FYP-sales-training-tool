// Run: node --experimental-strip-types web/src/features/session/history.check.ts
import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension
import { fromHistory, nextIndex, parseSettings } from "./history.ts";
import type { ChatMsg } from "../../lib/api/types.ts";

const turns = (n: number): ChatMsg[] => Array.from({ length: n }, (_, i) => ({ role: i % 2 ? "user" : "assistant", content: `m${i}` }));

// Short history keeps 0-based indices.
assert.deepEqual(fromHistory(turns(3), 100).map((m) => m.historyIndex), [0, 1, 2]);

// Long history (over the cap) keeps the TRUE server index, not 0.
const long = fromHistory(turns(120), 100);
assert.equal(long.length, 100);
assert.equal(long[0].historyIndex, 20);
assert.equal(long[0].content, "m20");

// Exactly at the cap: nothing skipped.
assert.equal(fromHistory(turns(100), 100)[0].historyIndex, 0);

// Edit branch offset: history sliced from 5 starts at 5.
assert.equal(fromHistory(turns(8).slice(5), 100, 5)[0].historyIndex, 5);

// nextIndex follows the last live message, ignoring dividers and greyed history.
const msgs = fromHistory(turns(120), 100);
assert.equal(nextIndex(msgs), 120);
assert.equal(nextIndex([]), 0);
const edited = [...msgs.map((m) => (m.historyIndex >= 110 ? { ...m, historical: true } : m)), { id: "d", role: "divider" as const, content: "", historyIndex: -1 }];
assert.equal(nextIndex(edited), 110);

// Duplicate content is two separate messages with distinct ids and indices.
const dup = fromHistory([{ role: "user", content: "same" }, { role: "user", content: "same" }], 100);
assert.notEqual(dup[0].id, dup[1].id);
assert.deepEqual(dup.map((m) => m.historyIndex), [0, 1]);

// Settings: bad JSON -> undefined; unknown display -> inline; missing hints -> true.
assert.equal(parseSettings("{oops"), undefined);
assert.deepEqual(parseSettings('{"evalDisplay":"popup"}'), { showHints: true, evalDisplay: "inline" });
assert.deepEqual(parseSettings('{"showHints":false,"evalDisplay":"panel"}'), { showHints: false, evalDisplay: "panel" });
assert.deepEqual(parseSettings("null"), { showHints: true, evalDisplay: "inline" });

console.log("history: all checks passed");
