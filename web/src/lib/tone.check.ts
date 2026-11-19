// Run: node --experimental-strip-types web/src/lib/tone.check.ts
import assert from "node:assert/strict";
// @ts-expect-error node runs this file directly and needs the .ts extension
import { bubbles, highlighted, speakable, toneRate, typingMs, unmarked } from "./tone.ts";

const line = "So this isn't really about the money.¶It's about ==them==.";

// a pause starts a new bubble; empty ones never show
assert.deepEqual(bubbles(line), ["So this isn't really about the money.", "It's about ==them==."]);
assert.deepEqual(bubbles("24 months... Damn.¶"), ["24 months... Damn."]);
assert.deepEqual(bubbles("Plain line?"), ["Plain line?"]);

// the key thing gets a highlight; stress stays markdown
assert.equal(highlighted("It's about ==them==."), "It's about <mark>them</mark>.");
assert.equal(highlighted("_all_ of it"), "_all_ of it");

// the voice hears the stress marks, with a sentence break between bubbles; the browser's own voice the words alone
assert.equal(speakable(line), "So this isn't really about the money. It's about ==them==.");
assert.equal(speakable("It's _all_ on you¶Why?"), "It's _all_ on you. Why?");
assert.equal(speakable("the belief_cost slot"), "the belief_cost slot.");
assert.equal(unmarked(speakable(line)), "So this isn't really about the money. It's about them.");
assert.equal(unmarked("It's _yours_: (all _of_ it) — “_now_”"), "It's yours: (all of it) — “now”");
assert.equal(unmarked("the belief_cost slot"), "the belief_cost slot");

// typing time grows with the line, within limits
assert.equal(typingMs("ok"), 600);
assert.equal(typingMs("x".repeat(500)), 2400);
assert.ok(typingMs("x".repeat(40)) > typingMs("x".repeat(20)));

// loud stress, long pause, tone note: shown as bold / a new bubble / not at all, never read aloud
const marked = "(slow, deliberate) Where you are **now**... that you _don't_ want[pause] Why?";
assert.deepEqual(bubbles(marked), ["Where you are **now**... that you _don't_ want", "Why?"]);
assert.equal(speakable(marked), "Where you are **now**... that you _don't_ want. Why?");
assert.equal(unmarked(speakable(marked)), "Where you are now... that you don't want. Why?");
assert.equal(speakable("(all of it) a**b"), "(all of it) a**b."); // not a tone note, not bold
assert.ok(toneRate(marked) < 0.8 && toneRate("(playful) hi") > 1);
assert.equal(toneRate("plain"), 1);

console.log("tone ok");
