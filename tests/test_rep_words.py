"""The rep's own words in buy mode (core/buy_mode/script_engine/rep_words.py, /api/buy/words, /api/buy/init `words`):
a top rep's or an SOP's questions said in place of the script's, the script still running the call."""
import os

import pytest

from core.buy_mode.script_engine import rep_words
from core.buy_mode.script_engine.engine import question_of
from core.buy_mode.script_engine.method import load_method
from core.infra.constants import REP_WORDS

SCRIPT_PRODUCT = "high_ticket_sales_mentorship"   # sold with the cat script


@pytest.fixture(scope="module")
def cat():
    return load_method("cat")


# --- the questions in a source ---


def test_questions_are_the_sentences_that_ask():
    lines = ["Hi Dan, thanks for making the time. What made you book the call?",
             "Got it. And how long has that been going on?", "Right.", "Why?"]
    assert rep_words.questions_in(lines) == ["What made you book the call?", "And how long has that been going on?"]


def test_an_sop_instruction_gives_the_question_it_quotes_not_the_instruction():
    lines = ['Ask: "What made you book the call today?"', "Ask: How long has this been a problem?",
             "Confirm the decision maker", "Q - Who else is involved in the decision?"]
    assert rep_words.questions_in(lines) == [
        "What made you book the call today?", "How long has this been a problem?", "Who else is involved in the decision?"]


def test_an_apostrophe_is_no_quote_and_a_compound_question_is_two():
    assert rep_words.questions_in(["What's getting in the way and how long has it been a problem?"]) == [
        "What's getting in the way?", "How long has it been a problem?"]
    assert rep_words.questions_in(["Then say “Who else signs off on this?” and wait."]) == ["Who else signs off on this?"]


def test_questions_are_cleaned_and_said_once():
    lines = ["What do you **really** want {outcome}?", "what do you REALLY want outcome ?", "Is   this\tclear to you?"]
    assert rep_words.questions_in(lines) == ["What do you really want outcome?", "Is this clear to you?"]


def test_a_long_question_is_cut_at_a_word_and_still_asks():
    long = "Can you " + "walk me through " * 30 + "it?"
    (cut,) = rep_words.questions_in([long]) or [rep_words.clean(long)]
    assert len(cut) <= REP_WORDS["max_chars"] + 1 and cut.endswith("?") and not cut.endswith(" ?")


# --- the steps a question can take ---


def test_only_steps_that_ask_and_wait_can_take_words(cat):
    ids = {s.id for s in rep_words.askable(cat)}
    assert "01" in ids and "03" in ids and "m_identify" in ids
    assert "00" not in ids                     # the frame runs straight on
    assert all(question_of(cat.steps[i].say).endswith("?") for i in ids)


def test_a_question_takes_the_step_that_asks_the_same(cat, fake_embedder):
    asked = cat.steps["03"].say
    matches = rep_words.match(cat, [asked, "Can you see my screen okay?"], fake_embedder.embed)
    assert [(m.step, m.theirs) for m in matches] == [("03", asked)]
    assert matches[0].name == "Time" and matches[0].score == 1.0


def test_each_question_takes_one_step_at_most(cat, fake_embedder):
    # Two steps ask "do you see yourself jumping in?"; one source line can take only one of them.
    matches = rep_words.match(cat, ["Do you see yourself jumping in?"], fake_embedder.embed)
    assert len(matches) == 1


def test_nothing_to_match_is_no_matches(cat, fake_embedder):
    assert rep_words.match(cat, [], fake_embedder.embed) == []


# --- the method with the words in ---


def test_the_new_question_replaces_the_questions_and_keeps_the_talk(cat):
    method = rep_words.with_words(cat, {"m_resolve": "So how could you sort the money out?",
                                        "willing": "Are you happy staying where you are?"})
    # m_resolve asks two questions after its talk: the new one says both
    assert method.steps["m_resolve"].say == (
        "Okay. So, I can see that money might be an issue from what you told me. So how could you sort the money out?")
    assert method.steps["willing"].say == "Are you happy staying where you are? Nothing wrong with that, I'm not here to judge"
    assert method.steps["willing"].listen == cat.steps["willing"].listen   # still heard the same way
    assert cat.steps["willing"].say.startswith("Are you willing")          # the loaded script is untouched


def test_a_plain_line_gets_the_new_question_too(cat):
    step = rep_words.with_words(cat, {"goal_practical": "And what would that give you?"}).steps["goal_practical"]
    assert step.say == "And what would that give you?" and step.say_plain == "And what would that give you?"


@pytest.mark.parametrize("words", [
    {"00": "Shall we start?"},                        # runs on, asks nothing
    {"nope": "What is this?"},                        # no such step
    {"03": "Tell me about your week."},               # not a question
    {"03": "Why?"},                                   # too short to say which step it is
    {"03": 42},
    {str(i): "How long have you been at this?" for i in range(REP_WORDS["max_lines"] + 1)},
    ["03", "How long?"],
])
def test_words_the_script_cannot_take_are_refused(cat, words):
    with pytest.raises(rep_words.RepWordsError):
        rep_words.with_words(cat, words)


def test_markup_never_reaches_the_line(cat):
    step = rep_words.with_words(cat, {"03": "How long have you **been** {name} thinking == about this?"}).steps["03"]
    assert step.say == "How long have you been name thinking about this?"


def test_a_probe_in_their_words_is_asked_first_when_the_step_is_asked_again(cat):
    step = rep_words.with_words(cat, {"03": "How long has this been on your mind?"},
                                {"03": "When did it first start bugging you?"}).steps["03"]
    assert step.probes[0] == "When did it first start bugging you?" and step.probes[1:] == cat.steps["03"].probes


@pytest.mark.parametrize("probes", [{"01": "What do you want most?"}, {"03": "Tell me more."}, ["03"]])
def test_a_probe_needs_its_step_in_their_words_and_must_ask(cat, probes):
    with pytest.raises(rep_words.RepWordsError):
        rep_words.with_words(cat, {"03": "How long has this been on your mind?"}, probes)


def test_the_source_asking_a_step_twice_gives_its_probe(cat):
    """Two questions that only step 03 fits: the closer one takes it, the other is asked when it is asked again."""
    own = rep_words._spoken(question_of(cat.steps["03"].say))
    sources = {"How long has this been on your mind?": 0.0, "When did this first start bugging you?": 0.2}

    def embed(texts):
        return [[1.0, 0.0] if t == own else [1.0, sources[t]] if t in sources else [0.0, 1.0] for t in texts]
    found = {m.step: m for m in rep_words.match(cat, ["How long has this been on your mind?",
                                                     "When did this first start bugging you?"], embed)}
    assert list(found) == ["03"]
    assert (found["03"].theirs, found["03"].probe) == ("How long has this been on your mind?",
                                                       "When did this first start bugging you?")


def test_tone_notes_and_pauses_never_reach_the_line(cat):
    step = rep_words.with_words(cat, {"03": "(curious) How long has this ¶ been on your mind?"}).steps["03"]
    assert step.say == "How long has this been on your mind?"


def test_a_step_with_choices_takes_a_question_that_offers_them(cat):
    assert rep_words.with_words(cat, {"22": "How do you want to pay, credit or debit card?"}).steps["22"].say.startswith(
        "How do you want to pay, credit or debit card?")


def test_a_yes_no_step_takes_a_yes_no_question(cat):
    assert rep_words.with_words(cat, {"19": "Can you see yourself joining us?"}).steps["19"].go_on_is_yes


def test_a_yes_no_step_is_never_matched_to_another_kind(cat):
    same = lambda texts: [[1.0, 0.0] for _ in texts]   # every line scores 1.0 to every other
    found = rep_words.match(cat, ["What would stop you from joining us today?"], same)
    assert all(m.step not in {"17", "19"} for m in found)


@pytest.mark.parametrize("label, said", [("Maya", "Maya"), ("  your   SOP ", "your SOP"), ("{x}<b>" + "a" * 60, "xb" + "a" * 38),
                                         (42, ""), (None, "")])
def test_the_label_is_plain_and_short(label, said):
    assert rep_words.clean_label(label) == said


# --- through the API ---


def _call(rep_lines, prospect="Dan"):
    lines = []
    for i, line in enumerate(rep_lines):
        lines += [f"Sam: {line}", f"{prospect}: Answer number {i} to that one, honestly."]
    return "\n".join(lines)


def test_a_call_with_their_own_words(client):
    words = {"01": "So what are you actually after with all this?", "03": "How long has this been on your mind?"}
    opened = client.post("/api/buy/init", json={"product_type": SCRIPT_PRODUCT, "words": words}).get_json()
    # step 00 runs straight on into 01: the frame is the script's, the question the top rep's
    assert opened["message"].endswith("I don't like to assume anything. So what are you actually after with all this?")
    headers = {"X-Session-ID": opened["session_id"]}
    for reply in ("I want financial freedom", "so I can stop stressing every time I buy something",
                  "I'd finally be proud of myself", "ten thousand a month"):
        said = client.post("/api/buy/chat", json={"message": reply}, headers=headers).get_json()["message"]
    assert said == "How long has this been on your mind?"


def test_the_label_comes_back_with_the_call_and_on_restore(client):
    words = {"03": "How long has this been on your mind?"}
    opened = client.post("/api/buy/init", json={"product_type": SCRIPT_PRODUCT, "words": words, "label": "Maya"}).get_json()
    assert opened["words_label"] == "Maya"
    again = client.post("/api/buy/init", json={"session_id": opened["session_id"], "label": "someone else"}).get_json()
    assert again["session_id"] == opened["session_id"] and again["words"] == words and again["words_label"] == "Maya"
    plain = client.post("/api/buy/init", json={"product_type": SCRIPT_PRODUCT, "label": "Maya"}).get_json()
    assert plain["words"] == {} and plain["words_label"] == ""


def test_a_forgotten_call_starts_again_with_the_words_sent(client):
    words = {"03": "How long has this been on your mind?"}
    res = client.post("/api/buy/init", json={"session_id": "gone0001", "product_type": SCRIPT_PRODUCT,
                                             "words": words, "label": "Maya"}).get_json()
    assert res["session_id"] != "gone0001"
    assert (res["product_type"], res["words"], res["words_label"]) == (SCRIPT_PRODUCT, words, "Maya")


@pytest.mark.parametrize("product", [["x"], {"a": 1}, 7])
def test_words_with_an_odd_product_use_the_default(client, product):
    res = client.post("/api/buy/words", json={"product_type": product, "stages": [{"title": "a", "steps": ["Ask what they want"]}]})
    assert res.status_code == 200 and res.get_json()["product_type"]


def test_words_that_dont_fit_are_refused_before_the_call_starts(client):
    response = client.post("/api/buy/init", json={"product_type": SCRIPT_PRODUCT, "words": {"00": "Ready to start?"}})
    assert response.status_code == 400 and response.get_json()["code"] == "REP_WORDS_INVALID"


def test_a_real_calls_rep_questions_are_matched(client, cat):
    asked = cat.steps["03"].say
    text = _call(["Hi Dan, thanks for coming on.", asked, "Can you hear me okay?"])
    body = client.post("/api/buy/words", json={"product_type": SCRIPT_PRODUCT, "call": {"text": text}}).get_json()
    assert body["rep"] == "Sam" and body["questions"] == 2 and body["steps"] == len(rep_words.askable(cat))
    assert [(m["step"], m["theirs"]) for m in body["matches"]] == [("03", asked)]


def test_an_sops_questions_are_matched(client, cat):
    stages = [{"title": "Discovery", "steps": [f'Ask: "{cat.steps["03"].say}"', "Confirm the budget"]}]
    body = client.post("/api/buy/words", json={"product_type": SCRIPT_PRODUCT, "stages": stages}).get_json()
    assert body["rep"] is None and [m["step"] for m in body["matches"]] == ["03"]


def test_words_need_a_call_or_an_sop(client):
    response = client.post("/api/buy/words", json={"product_type": SCRIPT_PRODUCT})
    assert response.status_code == 400 and response.get_json()["code"] == "REP_WORDS_SOURCE"


def test_an_unreadable_call_says_why(client):
    response = client.post("/api/buy/words", json={"call": {"text": "just some notes, nobody speaking"}})
    assert response.status_code == 400 and response.get_json()["code"] == "CALL_UNREADABLE"


# --- the threshold, measured with the real model (opt-in: downloads it) ---

LABELLED = {   # a rep's question -> the step it asks; tuned on the first half, checked on the second
    "cat": {
        "01": "So what is it you actually want to get out of making money online?",
        "02": "Roughly how much would you need coming in every month?",
        "03": "How long has this been on your mind?",
        "05": "Why do you think you haven't got there yet?",
        "09": "What do you believe about yourself that's been holding you back?",
        "belief_origin": "Where do you reckon that belief started?",
        "belief_cost": "If nothing changes with that belief, what's it going to cost you over the next few years?",
        "11": "What makes you different from everyone else who says this?",
        "18": "Does all of that make sense so far?",
        "19": "Can you see yourself joining us?",
        "22": "How do you want to pay for it, credit or debit card?",
        "m_identify": "What's the biggest thing stopping you right now?",
        "m_partner_proceed": "If your partner isn't on board, would you still go for it?",
        "goal_identity": "How would that change you as a person?",
        "12": "So what are you going to do differently starting today?",
        "m_think_what": "What exactly do you need to think about, is it the money or your partner?",
        "m_card": "Have you thought about using a credit card and paying it off with the extra profit?",
        "willing": "Are you happy to keep settling for average?",
    },
    "impact_formula": {
        "intent": "What did you want to get help with first?",
        "problem": "What's been the hardest part to figure out?",
        "duration": "How long has that been going on for you?",
        "why_now": "What's changed recently that made you look at this now?",
        "inaction": "What happens if nothing changes and you carry on as you are?",
        "feeling": "How would that make you feel?",
        "check": "Does that make sense?",
        "close": "How do you feel, do you see yourself getting started?",
        "payment": "How would you like to pay, credit or debit?",
        "commit": "Why now, why make the change at all?",
        "change": "If you could change one thing about it, what would it be?",
    },
}
OFF_SCRIPT = [
    "Can you hear me okay?", "Did you get the email I sent over?", "Where are you based at the moment?",
    "Is now still a good time to talk?", "Have you got a pen handy?", "Can you see my screen?",
    "What's the weather like over there?", "Shall I send you the recording afterwards?",
    "Do you have any questions about the contract terms?", "How did you hear about us?", "What do you do for work?",
    "Are you married?", "Have you checked out our YouTube channel?", "Is it okay if I record this call?",
    "Which time zone are you in?", "Did the link work for you?", "How old are you, if you don't mind me asking?",
    "Are you on mobile or laptop?", "Do you have kids?", "What's your favourite book?",
    "Can I call you back in five minutes?",
]


@pytest.mark.skipif(os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)")
@pytest.mark.parametrize("script", sorted(LABELLED))
def test_the_threshold_swaps_nothing_wrong_and_most_of_what_fits(script):
    from core.infra.embedder import make_embedder
    from core.buy_mode.script_engine.seller import engine_config
    from core.infra.env import ROOT_DIR

    gold = LABELLED[script]   # the real model, built here: every other test runs on the offline stand-in
    embed = make_embedder(engine_config(), ROOT_DIR).embed
    matches = rep_words.match(load_method(script), list(gold.values()) + OFF_SCRIPT, embed)
    right = sum(gold.get(m.step) == m.theirs for m in matches)
    assert right == len(matches), [(m.step, m.theirs) for m in matches if gold.get(m.step) != m.theirs]
    assert right / len(gold) >= 0.8


SAMPLE_MATCHES = {   # the samples behind "Try a sample" in the Rep's words tool: what each script takes from them
    ("call", "cat"): {"01", "02", "03", "05", "09", "belief_origin", "18", "22"},
    ("call", "impact_formula"): {"intent", "problem", "duration", "feeling", "check", "payment"},
    ("sop", "cat"): {"01", "02", "03", "09", "belief_origin", "19", "22"},
    ("sop", "impact_formula"): {"intent", "problem", "close", "payment"},
}


@pytest.mark.skipif(os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)")
@pytest.mark.parametrize("source, script", sorted(SAMPLE_MATCHES))
def test_the_samples_give_the_right_questions(source, script):
    from core.infra.embedder import make_embedder
    from core.buy_mode.script_engine.seller import engine_config
    from core.calls.reader import read_call
    from core.infra.env import ROOT_DIR
    from core.infra.loader import CONFIG_DIR, load_yaml
    from core.sop.document import read_document
    from core.sop.outline import build_outline
    from core.sop.spoken import as_question

    if source == "call":
        reading = read_call((CONFIG_DIR / "rep_words_sample_call.txt").read_text("utf-8"))
        lines = [h["content"] for h in reading.history() if h["role"] == "user"]
    else:
        blocks = read_document((CONFIG_DIR / "rep_words_sample_sop.md").read_bytes(), "sample.md")
        lines = [as_question(s) or s for st in build_outline(blocks, load_yaml("sop.yaml")["untitled_stage"]) for s in st.steps]
    matches = rep_words.match(load_method(script), rep_words.questions_in(lines), make_embedder(engine_config(), ROOT_DIR).embed)
    assert {m.step for m in matches} == SAMPLE_MATCHES[(source, script)]


@pytest.mark.parametrize("source, start", [("call", "Discovery call"), ("sop", "# Discovery call SOP"), ("other", "Discovery call")])
def test_the_samples_are_served(client, source, start):
    body = client.get(f"/api/buy/words/sample?source={source}").get_json()
    assert body["text"].startswith(start) and body["filename"]


def test_the_sample_call_reads_with_its_rep(client):
    text = client.get("/api/buy/words/sample?source=call").get_json()["text"]
    body = client.post("/api/buy/words", json={"product_type": SCRIPT_PRODUCT, "call": {"text": text}}).get_json()
    assert body["rep"] == "Maya Okafor" and body["questions"] >= 10
