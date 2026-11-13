"""One rule for "does this line say X?" (core/infra/phrases.py), used by the buyer, the turn rating, the review and
the score."""

from core.infra.phrases import says, says_any, says_word
from core.infra.loader import load_buyer_config
from core.sell_mode.sell_evaluator import _criteria_scores


def test_a_phrase_matches_at_the_start_of_a_word_only():
    assert says("frustrat", "I'm so frustrated with it")
    assert says("how", "How long has it been?") and not says("how", "Let me show you")
    assert not says("fit", "That will benefit you")                  # inside a word: never
    assert says("plan", "our planet-friendly range")                  # a word's start: by design ("frustrat")
    assert says("what's stopped", "What’s stopped you?")            # curly apostrophe
    assert not says("s", "it's fine")                                 # never a letter after an apostrophe


def test_a_symbol_matches_anywhere():
    assert says("$", "It's $4,000.") and says_any(["£", "price"], "about £300")


def test_a_whole_word_allows_a_contraction_but_not_a_longer_word():
    assert says_word(["what"], "what's the hardest part?") and not says_word(["what"], "whatever works")


def test_the_score_no_longer_counts_words_inside_other_words():
    """'Can I show you?' asked nothing open, and 'benefit' is not 'fit': both used to count."""
    evaluation = load_buyer_config()["evaluation"]

    def score(line, criterion):
        history = [{"role": "assistant", "content": "Hi."}, {"role": "user", "content": line},
                   {"role": "assistant", "content": "Okay."}]
        return _criteria_scores(history, evaluation)[criterion]["score"]

    assert score("Can I show you something?", "needs_discovery") < score("How would that help you?", "needs_discovery")
    assert score("It will benefit you.", "solution_presentation") < score("That would fit what you said.", "solution_presentation")
