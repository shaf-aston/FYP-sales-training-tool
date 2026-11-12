"""The sell-mode buyer's move by rules (buyer_moves.py) and a real prospect's line for it (buyer_lines.py)."""

import os
import re

import pytest

from core.infra.env import ROOT_DIR
from core.infra.loader import load_buyer_config, load_yaml
from core.infra.providers.base import LLMResponse
from core.sell_mode.buyer_lines import fill, lines_for, pick_line
from core.sell_mode.buyer_moves import MOVES, Move, next_move, topic_of
from core.sell_mode.buyer_session import BuyerSession

PERSONA = {"name": "Sam", "needs": ["cost reduction", "scaling operations"], "budget": "cost-conscious",
           "pain_points": ["losing customers to competitors", "manual processes eating time"]}
MOVES_CFG = load_buyer_config()["moves"]
WARM, MID, COLD = MOVES_CFG["open_from"], (MOVES_CFG["open_from"] + MOVES_CFG["guarded_below"]) / 2, 0.0


# --- the move ---


@pytest.mark.parametrize("line, topic", [
    ("What's your budget for something like this?", "budget"),
    ("When would you want to get started?", "time"),
    ("Who else is involved in the decision?", "decision"),
    ("What are you using at the moment?", "current"),
    ("What's the biggest challenge right now?", "current"),   # "right now" names the current set-up first
    ("What's been the hardest part?", "pain"),
    ("What are you hoping to achieve?", "need"),
    ("Nice weather today, eh?", "current"),
    ("Tell me about your business?", "general"),
])
def test_the_topic_is_what_the_seller_asked_about(line, topic):
    assert topic_of(line) == topic


@pytest.mark.parametrize("readiness, line, signals, kind", [
    (WARM, "Buy now, offer ends today!", ["pressure"], "stall"),
    (MID, "What's your budget?", [], "share"),
    (COLD, "What's your budget?", [], "guard"),
    (MID, "Tell me about your business?", [], "guard"),
    (MID, "Tell me about your business?", ["open_question", "on_topic"], "share"),
    (WARM, "Tell me about your business?", [], "share"),
    (WARM, "We help teams cut admin by half.", [], "lean_in"),
    (MID, "We help teams cut admin by half.", [], "ask"),
    (COLD, "We help teams cut admin by half.", [], "stall"),
    (COLD, "What questions do you have for me?", [], "ask"),
])
def test_rules_choose_the_move(readiness, line, signals, kind):
    move = next_move(readiness, line, signals)
    assert move.kind == kind and move.kind in MOVES


def test_a_push_gets_the_pressure_lines():
    move = next_move(WARM, "Sign today or lose the discount", ["pressure"], objection=True)
    assert (move.kind, move.topic, move.label) == ("stall", "pressure", "stall:pressure+object")


def test_every_move_has_an_instruction_for_the_ai():
    assert set(MOVES_CFG["instructions"]) == set(MOVES)


# --- the line bank ---


def test_every_line_in_the_bank_is_short_plain_and_fillable():
    bank = load_yaml("prospect_lines.yaml")["lines"]
    assert set(bank) == set(MOVES)
    for kind, cells in bank.items():
        for topic, lines in cells.items():
            assert len(lines) >= 8, (kind, topic)
            assert len(set(lines)) == len(lines), (kind, topic)
            for line in lines:
                assert len(line.split()) <= 20 and not re.search(r"\{(?!need\}|pain\}|budget\}|budget_kind\})", line), line
                assert fill(line, PERSONA, "") is not None or fill(line, {**PERSONA, "budget": "$5k"}, "") is not None, line


def test_blanks_take_the_next_thing_not_said_yet_and_start_sentences_with_a_capital():
    assert fill("{need}, mostly.", PERSONA, "") == "Cost reduction, mostly."
    assert fill("{need}, mostly.", PERSONA, "honestly cost reduction is it") == "Scaling operations, mostly."
    assert fill("Mainly {need}.", PERSONA, "cost reduction scaling operations") is None   # nothing new to say
    assert fill("Honestly? {pain}.", {"pain_points": []}, "") is None


def test_a_budget_is_said_as_a_figure_or_as_a_description():
    figure, kind = {"budget": "$50,000-$70,000"}, {"budget": "cost-conscious"}
    assert fill("I'd want to keep it around {budget}.", figure, "") == "I'd want to keep it around $50,000-$70,000."
    assert fill("I'd want to keep it around {budget}.", kind, "") is None
    assert fill("{budget_kind}. I'm not throwing money at it.", kind, "") == "Cost-conscious. I'm not throwing money at it."
    assert fill("{budget_kind}. I'm not throwing money at it.", figure, "") is None


def test_an_answer_has_no_general_lines_so_the_ai_answers_what_the_bank_cannot():
    assert lines_for(Move("share", "general")) == []
    assert lines_for(Move("guard", "budget")) == lines_for(Move("guard", "general"))


def test_a_line_is_never_said_twice_in_a_call(fake_embedder):
    history, said = [], []
    for turn in range(12):
        line = pick_line(Move("stall", "general"), "We help teams cut admin.", PERSONA, history, fake_embedder.embed, f"s|{turn}")
        if line is None:
            break
        said.append(line)
        history.append({"role": "assistant", "content": line})
    assert len(said) == len(set(said)) == len(lines_for(Move("stall", "general")))


def test_the_same_seed_picks_the_same_line(fake_embedder):
    pick = lambda seed: pick_line(Move("ask", "general"), "We run a 12-week programme.", PERSONA, [], fake_embedder.embed, seed)
    assert pick("abc|3") == pick("abc|3")
    assert len({pick(f"s{n}|1") for n in range(20)}) > 1   # but sessions differ


def test_an_answer_far_from_the_question_is_left_to_the_ai():
    far = lambda texts: [[1.0, 0.0] if i == 0 else [0.0, 1.0] for i, _ in enumerate(texts)]
    assert pick_line(Move("share", "budget"), "What's your budget?", PERSONA, [], far, "s|1") is None


# --- in a session ---

SELLER = [
    "Hi Sam, thanks for making the time. What made you take this call?",
    "What's been the hardest part of running things lately?",
    "That sounds draining. How long has that been going on?",
    "What are you using at the moment to handle it?",
    "If you could fix one thing first, what would you want to achieve?",
    "We help small service businesses automate the admin that eats their week.",
    "What would that free you up to do?",
    "What sort of budget have you set aside for fixing this?",
    "Who else would be involved in deciding?",
    "When would you ideally want to get started?",
    "Most owners see the first results within a month.",
    "What questions do you have for me?",
]


def _play(session_id, stub_buyer, monkeypatch, bank=True, min_score=0.0):
    """A scripted call. The offline embedder's scores mean nothing, so the meaning bar is off unless a test sets it."""
    monkeypatch.setattr("core.sell_mode.buyer_session.LINE_BANK", bank)
    if min_score is not None:
        monkeypatch.setattr("core.sell_mode.buyer_lines.MIN_SCORE", min_score)
    stub_buyer.reply = "That's a fair question, let me think."
    buyer = BuyerSession(difficulty="medium", persona=dict(PERSONA), session_id=session_id)
    buyer.get_opening_message()
    replies, sources = [], []
    for line in SELLER:
        if buyer.state.ended:
            break
        replies.append(buyer.process_turn(line).content)
        sources.append(buyer.last_source)
    return replies, sources


def test_most_replies_come_from_the_bank(stub_buyer, monkeypatch):
    sources = [s for n in range(10) for s in _play(f"bank-{n}", stub_buyer, monkeypatch)[1]]
    assert sources.count("bank") / len(sources) >= 0.7, sources


def test_the_same_session_replays_the_same_way(stub_buyer, monkeypatch):
    assert _play("replay-1", stub_buyer, monkeypatch) == _play("replay-1", stub_buyer, monkeypatch)


def test_bank_off_the_ai_words_every_move(stub_buyer, monkeypatch):
    assert set(_play("ai-only", stub_buyer, monkeypatch, bank=False)[1]) == {"ai"}


def test_the_ai_is_told_the_move(stub_buyer, monkeypatch):
    monkeypatch.setattr("core.sell_mode.buyer_session.LINE_BANK", False)
    prompts = []
    stub_buyer.chat = lambda messages, **kw: prompts.append(messages[0]["content"]) or LLMResponse(content="Okay.")
    buyer = BuyerSession(difficulty="medium", persona=dict(PERSONA), session_id="told")
    buyer.process_turn("Buy now, the offer ends today!")
    assert prompts[-1].endswith("THIS TURN: " + MOVES_CFG["instructions"]["stall"])


def test_replies_sound_like_a_prospect(stub_buyer, monkeypatch):
    """Rough bands until real calls give the reference numbers (docs/PLAN.md 2.2): short replies, at most one
    question a turn, objections on some turns but not most."""
    replies = [r for n in range(10) for r in _play(f"real-{n}", stub_buyer, monkeypatch)[0]]
    words = sorted(len(r.split()) for r in replies)
    assert 4 <= words[len(words) // 2] <= 25
    assert max(r.count("?") for r in replies) <= 2
    raised = sum(BuyerSession(difficulty="medium", session_id=f"real-{n}").pacer.raised_by(len(SELLER)) for n in range(10))
    assert 0 < raised <= len(replies) // 2


@pytest.mark.skipif(os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)")
def test_with_the_real_model_most_replies_come_from_the_bank(stub_buyer, monkeypatch):
    from core.infra.embedder import make_embedder

    real = make_embedder(load_yaml("script/engine.yaml"), ROOT_DIR)
    monkeypatch.setattr("core.infra.embedder.shared_embedder", lambda: real)
    sources = [s for n in range(5) for s in _play(f"real-model-{n}", stub_buyer, monkeypatch, min_score=None)[1]]
    assert sources.count("bank") / len(sources) >= 0.7, sources
