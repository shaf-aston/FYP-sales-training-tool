"""Tone marks (tone.py): drawn by the screen, never read by the AI. The web twin is tone.check.ts."""
from core.script_engine.meanings import parse_meanings
from core.script_engine.tone import join, plain, stresses


def test_plain_drops_the_marks():
    assert plain("So it's about ==them==.¶Taking over _all_ the bills…") == "So it's about them. Taking over all the bills…"
    assert plain("It's _yours_: (all _of_ it) — “_now_”") == "It's yours: (all of it) — “now”"
    assert plain("it is _all_-in") == "it is all-in" and stresses("it is _all_-in") == 1
    assert plain("the belief_cost slot") == "the belief_cost slot"  # an underscore inside a word is no stress


def test_stresses_counts_both_marks():
    assert stresses("It's _all_ on ==you==") == 2
    assert stresses("belief_cost and ==you==") == 1


def test_join_puts_each_part_in_its_own_bubble():
    assert join("I'm sorry.", " Why? ") == "I'm sorry.¶Why?"
    assert join("", "Why?") == "Why?"
    assert join("Damn.¶", "What?") == "Damn.¶What?"  # never an empty bubble


def test_the_ai_reads_the_question_without_marks(fake_embedder, cat_seller):
    prompts = []

    def ai(prompt, n):
        prompts.append(prompt)
        raise RuntimeError("down")

    s = cat_seller(fake_embedder, ai, step="04", meanings=parse_meanings({"min_score": 1.0, "meanings": {}}))
    s.reply("because it eats me up")
    assert prompts and all("¶" not in p and "==" not in p for p in prompts)
