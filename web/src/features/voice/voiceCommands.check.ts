// Run: node --experimental-strip-types web/src/features/voice/voiceCommands.check.ts
import assert from "node:assert/strict";
// @ts-expect-error TS5097: node needs the .ts extension, the app build does not allow it
import { parsePunctuation } from "./voiceCommands.ts";

assert.equal(parsePunctuation("hello period how are you comma sir new line thanks "), "hello. how are you, sir\nthanks ");
assert.equal(parsePunctuation("periodic table "), "periodic table "); // word, not the command
console.log("voiceCommands: all checks passed");
