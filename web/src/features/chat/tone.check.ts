// Run: node --experimental-strip-types web/src/features/chat/tone.check.ts
import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension
import { bubbles, highlighted, speakable, typingMs } from "./tone.ts";

const line = "So this isn't really about the money.¶It's about ==them==.";

// a pause starts a new bubble; empty ones never show
assert.deepEqual(bubbles(line), ["So this isn't really about the money.", "It's about ==them==."]);
assert.deepEqual(bubbles("24 months... Damn.¶"), ["24 months... Damn."]);
assert.deepEqual(bubbles("Plain line?"), ["Plain line?"]);

// the key thing gets a highlight; stress stays markdown
assert.equal(highlighted("It's about ==them==."), "It's about <mark>them</mark>.");
assert.equal(highlighted("_all_ of it"), "_all_ of it");

// the voice hears words only, with a sentence break between bubbles
assert.equal(speakable(line), "So this isn't really about the money. It's about them.");
assert.equal(speakable("It's _all_ on you¶Why?"), "It's all on you. Why?");
assert.equal(speakable("the belief_cost slot"), "the belief_cost slot.");

// typing time grows with the line, within limits
assert.equal(typingMs("ok"), 600);
assert.equal(typingMs("x".repeat(500)), 2400);
assert.ok(typingMs("x".repeat(40)) > typingMs("x".repeat(20)));

console.log("tone ok");
