"""Concept listening: on a step that captures an answer and takes any reply, one AI call hears for the
step's concept. A miss gets one fresh probe for it, a second miss moves on; "k" never becomes an answer.
Offline: bag-of-words embedder, a fake AI that answers the listen call's three lines."""
from itertools import pairwise

import pytest

from core.loader import load_yaml
from core.script_engine.checks import CheckContext
from core.script_engine.engine import ScriptState
from core.script_engine.listen import Heard, hear, parse
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.seller import ScriptSeller

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")
SHRUGS = {"k", "kk", "idk", "dunno", "ok", "meh", "whatever", "no idea", "not sure"}


class ListenAI:
    """Answers the listen call like a careful human would: a shrug misses, anything else answers."""

    def __init__(self, probe="What's the one thing that stops you right now?", ack="none"):
        self.probe, self.ack, self.prompts = probe, ack, []

    def __call__(self, prompt, max_tokens):
        self.prompts.append(prompt)
        if "<goal>" not in prompt:
            raise RuntimeError("only the listen call is faked")
        reply = prompt.split("<reply>")[1].split("</reply>")[0].strip().lower()
        if reply in SHRUGS:
            return f"ANSWERED: no\nACK: none\nPROBE: {self.probe}"
        return f"ANSWERED: yes\nACK: {self.ack}\nPROBE: none"


def seller(bow, llm, step=None, **state):
    s = ScriptSeller(CFG, CAT, load_offer("shay_coaching"), load_common_sense(), bow, llm)
    if step:
        s.reset(ScriptState(step=step, **state))
    return s


# ---- parse + checks (listen.py) ----------------------------------------------------------------

@pytest.mark.parametrize("raw, want", [
    ("ANSWERED: yes\nACK: You barely see your daughter.\nPROBE: none", (True, "You barely see your daughter.", "")),
    ("answered: No\nack: -\nprobe: \"What stops you?\"", (False, "", "What stops you?")),
    ("ANSWERED: yes", (True, "", "")),
    ("Sure thing!\nANSWERED: no\nPROBE: Why not?", (False, "", "Why not?")),
    ("ANSWERED: yes ACK: hi PROBE: none", (True, "hi", "")),                      # all on one line
    ("ANSWERED: no\nPROBE: What stops you?\nANSWERED: yes", (False, "", "What stops you?")),  # first verdict counts
    ("ANSWERED: no\nPROBE: ANSWERED: yes", (False, "", "")),                      # a key inside a value is no probe
])
def test_parse_reads_the_three_lines_tolerantly(raw, want):
    assert parse(raw) == want


@pytest.mark.parametrize("raw", ["vague", "", "ANSWERED: maybe\nACK: x", "ACK: hi\nPROBE: why?"])
def test_parse_without_a_verdict_is_none(raw):
    assert parse(raw) is None


ACK_CTX = CheckContext(12, 0, False, "$5k", prospect_words=frozenset({"nights", "barely", "daughter"}),
                       stop_words=frozenset(CFG["stop_words"]) | frozenset(CFG["ack_words"]),
                       banned_phrases=tuple(CFG["banned_phrases"]))
PROBE_CTX = CheckContext(18, 1, False, "$5k", known_figures=frozenset(), banned_phrases=tuple(CFG["banned_phrases"]),
                         banned=frozenset(CFG["answer_banned_words"]) - frozenset({"two", "weeks"}))


def listen(raw, asked="What holds you back?"):
    return hear(lambda p, n: raw, "prompt", 90, ACK_CTX, PROBE_CTX, asked, CFG)


def test_a_probe_must_be_one_checked_question():
    assert listen("ANSWERED: no\nPROBE: What stops you?") == Heard(False, probe="What stops you?")
    assert listen("ANSWERED: no\nPROBE: Tell me what stops you.") == Heard(False)      # not a question
    assert listen("ANSWERED: no\nPROBE: What stops you? Money?") == Heard(False)       # two questions
    assert listen("ANSWERED: no\nPROBE: But what stops you?") == Heard(False)          # banned word
    assert listen("ANSWERED: no\nPROBE: Is $5k the problem?") == Heard(False)          # price too early
    assert listen("ANSWERED: no\nPROBE: Is it the 3 kids?") == Heard(False)            # a number they never said
    assert listen("ANSWERED: no\nPROBE: what holds you back?") == Heard(False)         # the same words again
    assert listen("ANSWERED: no\nPROBE: Would a guaranteed refund help?") == Heard(False)  # a promise
    assert listen("ANSWERED: no\nPROBE: Is it the three kids?") == Heard(False)        # a spelled-out number
    assert listen("ANSWERED: no\nPROBE: Why two weeks?") == Heard(False, probe="Why two weeks?")  # their words
    assert listen("ANSWERED: no\nPROBE: none") == Heard(False)


def test_an_ack_must_use_their_words():
    assert listen("ANSWERED: yes\nACK: You barely see your daughter.") == Heard(True, "You barely see your daughter.")
    assert listen("ANSWERED: yes\nACK: Great, you miss your daughter.") == Heard(True)  # not their words
    assert listen("ANSWERED: yes\nACK: none") == Heard(True)


def test_ai_down_or_off_format_is_none():
    def down(p, n):
        raise RuntimeError("down")
    assert hear(down, "p", 90, ACK_CTX, PROBE_CTX, "q", CFG) is None
    assert listen("vague") is None


# ---- one turn (seller) ------------------------------------------------------------------------

def test_a_shrug_gets_a_fresh_probe_not_the_same_line(fake_embedder):
    ai = ListenAI()
    s = seller(fake_embedder, ai, step="09")
    text, _ = s.reply("k")
    assert text == ai.probe
    assert s.state.step == "09" and s.state.asks == 1 and "belief" not in s.state.slots
    assert "<goal>Limiting belief: the story they tell themselves" in ai.prompts[0]


def test_shrugs_are_asked_again_misses_times_then_the_call_moves_on_without_an_answer(fake_embedder):
    s = seller(fake_embedder, ListenAI(), step="09")
    said = [s.reply(shrug)[0] for shrug in ["k", "idk", "k"][:CFG["misses"]]]
    assert s.state.step == "09" and len(said) == len(set(said))  # never moves on, never the same line
    text, _ = s.reply("idk")
    assert text == CAT.steps["belief_origin"].say
    assert "belief" not in s.state.slots


def test_an_answer_after_the_probe_is_kept_and_acked(fake_embedder):
    s = seller(fake_embedder, ListenAI(ack="So you're lazy."), step="09")
    s.reply("k")
    text, _ = s.reply("I'm lazy")  # means nothing in the meaning bank, so the AI's line is said
    assert text == f"So you're lazy. {CAT.steps['belief_origin'].say}"
    assert s.state.slots["belief"] == "I'm lazy"


def test_a_side_question_after_the_probe_re_asks_the_probe_wording(fake_embedder):
    ai = ListenAI()
    s = seller(fake_embedder, ai, step="09")
    s.reply("k")
    text, _ = s.reply("sorry, can you say that again")
    assert text.endswith(ai.probe)


def test_one_ai_call_per_turn_on_a_concept_step(fake_embedder):
    ai = ListenAI(ack="You barely see your daughter.")
    s = seller(fake_embedder, ai, step="04")
    s.reply("I work nights and barely see my daughter")
    assert len(ai.prompts) == 1


def test_a_shrug_past_the_misses_costs_no_ai_call(fake_embedder):
    ai = ListenAI()
    s = seller(fake_embedder, ai, step="09")
    for _ in range(CFG["misses"] + 1):
        s.reply("k")  # the last one: advance moves on whatever the AI says, so no call
    assert len(ai.prompts) == CFG["misses"]


def test_an_ai_probe_already_asked_on_the_step_is_never_asked_again(fake_embedder):
    ai = ListenAI()  # the same probe every time
    s = seller(fake_embedder, ai, step="09")
    first, _ = s.reply("k")
    second, _ = s.reply("k")
    assert first == ai.probe and second != ai.probe


def test_off_format_listen_output_means_no_second_call_this_turn(fake_embedder):
    calls = []

    def odd(p, n):
        calls.append(p)
        return "**ANSWERED:** yes"
    s = seller(fake_embedder, odd, step="04")
    text, _ = s.reply("I work nights and barely see my daughter")
    assert len(calls) == 1 and text == CAT.steps["05"].say_plain  # no ack: the plain line, nothing else


def test_the_old_wording_comes_back_when_the_ai_is_down(fake_embedder):
    def down(p, n):
        raise RuntimeError("down")
    s = seller(fake_embedder, down, step="09")
    said = [s.reply("k")[0] for _ in range(CFG["misses"])]
    lead = CAT.reask  # 09 has no probes: its own words, behind a different lead each time
    assert said[:2] == [f"{lead[0]} {CAT.steps['09'].say}", f"{lead[1]} {CAT.steps['09'].say}"]
    assert all(a != b for a, b in pairwise(said))
    text, _ = s.reply("k")
    assert text == CAT.steps["belief_origin"].say     # then the call moves on


def test_labelled_steps_still_use_examples_not_the_listen_call(fake_embedder):
    ai = ListenAI()
    s = seller(fake_embedder, ai, step="01")
    s.reply("not sure really")   # labelled vague: asked again, no AI listen call
    assert ai.prompts == [] and s.state.step == "01"


def test_listen_can_be_switched_off(fake_embedder):
    ai = ListenAI()
    s = ScriptSeller({**CFG, "listen": False}, CAT, load_offer("shay_coaching"), load_common_sense(), fake_embedder, ai)
    s.reset(ScriptState(step="09"))
    s.reply("k")
    assert ai.prompts == []


def test_the_turn_log_says_it_missed(fake_embedder):
    s = seller(fake_embedder, ListenAI(), step="09")
    s.reply("whatever")
    assert s.last_turn["heard_as"] == "misses" and s.last_turn["step_to"] == "09"


# ---- the owner's live chat, replayed -----------------------------------------------------------

OWNER_CHAT = [
    "more money", "more money", "more money", "Less stress", "5 k month", "1 year",
    "Oh it feels quite important.", "because idont mske 5k month", "idk", "idk", "k", "kk", "k", "k",
    "k", "k", "k", "k", "k", "k", "k", "k", "k", "k",
]


def test_the_owners_chat_never_repeats_a_line_and_never_saves_a_shrug(fake_embedder):
    s = seller(fake_embedder, ListenAI())
    said = [s.opening()[0]] + [s.reply(line)[0] for line in OWNER_CHAT]
    while s.state.step != "14" and len(said) < 80:  # they keep shrugging: each open step asked `misses` more times
        said.append(s.reply("k")[0])
    assert s.state.step == "14", said  # the price is still reached: shrugs never trap the call
    assert all(a != b for a, b in pairwise(said)), said
    assert not SHRUGS & {v.lower() for v in s.state.slots.values()}, s.state.slots


# ---- a dead reply is never an answer (owner: "if not clear, don't move on") --------------------

def _down(p, n):
    raise RuntimeError("down")


def test_a_shrug_beyond_the_filler_words_is_asked_again_not_saved(fake_embedder):
    s = seller(fake_embedder, _down, step="02", slots={"outcome": "I want financial freedom"})
    text, _ = s.reply("no clue")  # live: "dunno man" at 02 was saved as their number
    assert s.state.step == "02" and "number" not in s.state.slots
    assert text == CAT.steps["02"].probes[0]


def test_unclear_words_get_asked_what_they_mean(fake_embedder):
    s = seller(fake_embedder, _down, step="04")
    text, _ = s.reply("stuff I guess")
    assert text == "What do you mean by stuff?" and "why" not in s.state.slots
    text, _ = s.reply("stuff I guess")  # asked once: next time other words
    assert text == CAT.steps["04"].probes[0]


def test_a_question_is_never_heard_as_a_shrug(fake_embedder):
    s = seller(fake_embedder, _down, step="04")
    s.reply("no clue, what do you mean?")
    assert s.last_turn["heard_as"] != "says_nothing"


def test_a_frustrated_whatever_is_still_frustration_not_a_shrug(fake_embedder):
    s = seller(fake_embedder, _down, step="08")
    s.reply("meh, whatever")
    assert s.last_turn["heard_as"] == "sense:frustrated"


def test_every_open_question_takes_misses_shrugs_before_moving_on(fake_embedder):
    for step in ("belief_origin", "11"):  # open questions that once moved on at the first "k"
        s = seller(fake_embedder, _down, step=step)
        for _ in range(CFG["misses"]):
            s.reply("k")
            assert s.state.step == step
        s.reply("k")
        assert s.state.step != step


def test_a_shrug_on_a_step_with_labels_and_a_catch_all_is_not_saved(fake_embedder):
    # live: "dunno man" at "how long have you been thinking about this?" was kept as the years and moved on
    s = seller(fake_embedder, _down, step="03")
    s.reply("dunno man")
    assert s.state.step == "03" and "years" not in s.state.slots


def test_a_greeting_is_never_asked_what_it_means(fake_embedder):
    # live: "hey" got "What do you mean by hey?"; only words about the question are asked about
    s = seller(fake_embedder, _down, step="01")
    text, _ = s.reply("hey")
    assert "mean by" not in text


def test_rewinding_past_a_brb_forgets_they_stepped_away(fake_embedder):
    # bug: "waiting" lived outside the saved state, so an edited turn replayed as if they had said "brb"
    s = seller(fake_embedder, _down, step="04")
    before = s.snapshot()
    s.reply("brb")
    assert s.state.waiting
    s.restore(before)
    assert not s.state.waiting
    s.reply("ok")
    assert s.last_turn["heard_as"] == "says_nothing"


def test_a_shrug_after_an_early_answer_is_still_asked_about_this_turn(fake_embedder):
    # bug: the "answered a later step" flag outlived its turn; now it lives in that turn's verdict only
    s = seller(fake_embedder, _down, step="01")
    s.reply("I want to make 5k a month")  # answers a later step early
    assert s.state.slots
    s.reset(ScriptState(step="04", slots=s.state.slots))
    text, _ = s.reply("stuff I guess")
    assert text == "What do you mean by stuff?"
