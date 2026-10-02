// Run: node --experimental-strip-types web/src/features/voice/voiceCommands.check.ts
import assert from "node:assert/strict";
// @ts-expect-error TS5097: node needs the .ts extension, the app build does not allow it
import { parseFlowCommand, parsePunctuation } from "./voiceCommands.ts";

assert.deepEqual(parseFlowCommand("Jump to pitch"), { type: "stage", value: "pitch" });
assert.deepEqual(parseFlowCommand("go to the stage objection"), { type: "stage", value: "objection" });
assert.deepEqual(parseFlowCommand("switch to pitch"), { type: "stage", value: "pitch" });
assert.deepEqual(parseFlowCommand("switch strategy to consultative"), { type: "strategy", value: "consultative" });
assert.deepEqual(parseFlowCommand("set strategy transactional"), { type: "strategy", value: "transactional" });
assert.equal(parseFlowCommand("I would like to buy the blue one"), null); // plain sentence
assert.equal(parseFlowCommand("jump to banana"), null); // unknown stage
assert.equal(parseFlowCommand("   "), null);
assert.equal(parseFlowCommand(""), null);

assert.equal(parsePunctuation("hello period how are you comma sir new line thanks "), "hello. how are you, sir\nthanks ");
assert.equal(parsePunctuation("periodic table "), "periodic table "); // word, not the command
console.log("voiceCommands: all checks passed");
