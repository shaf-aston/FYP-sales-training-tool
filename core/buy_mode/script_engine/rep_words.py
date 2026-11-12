"""The rep's own words: a top rep's questions (from a real call) or an SOP's, said in place of the script's.

The script still runs the call (what each step listens for, where it goes next, the checks around the AI); only the
wording of a step's question changes. A source line takes a step only when it asks the same thing (meaning matched
with the local embedding model, one line per step, strongest pairs first), so a step's routes still fit the
question the prospect hears. Statements (the pitch, the frame) keep the script's words: they carry the offer's facts.

  questions_in(lines)                 the questions in a rep's lines or an SOP's, cleaned
  match(method, questions, embed)     which question steps a source line can take, with how close it is
  with_words(method, words)           the method with those lines said instead (validated: only question steps)

No mode imports and no AI: the caller passes `embed` (texts -> vectors), as core/sop does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from core.buy_mode.script_engine.engine import questions_of
from core.buy_mode.script_engine.method import Method, Step
from core.buy_mode.script_engine.words.fill import NAME
from core.infra.constants import REP_WORDS
from core.infra.similarity import Embed, best_pairs, similarity
from core.infra.utils import sentences

# Characters a borrowed line never carries: blanks ({name}), stress marks (**, _, ==) and markup are the script's own.
_UNSAFE = re.compile(r"[{}*_=<>\[\]\\`|#~^]")
# "Ask: What made you book the call?", "Say “...?”": the words to say, not the instruction around them.
_QUOTED = re.compile(r"(?:^|(?<=[\s:(]))[\"“‘]([^\"“”‘’]{3,}?\?)[\"”’]?")   # an apostrophe ("What's") is no quote
_INSTRUCTION = re.compile(r"^\s*(?:ask|say|question|q)\s*[:\-–]\s*", re.IGNORECASE)
# Words in front of a question that say nothing about what it asks ("So, roughly how much ...").
_FILLER = re.compile(r"^(?:(?:so|and|but|okay|ok|right|great|well|now|then|just|roughly|honestly|sure|also|"
                     r"before anything else|in that case|be honest with me|out of curiosity|tell me)\b[,.]?\s*)+",
                     re.IGNORECASE)
_KINDS = [  # what sort of answer a question asks for: a why wants reasons, a how much a figure, a yes/no a yes or no
    ("why", r"why\b|how come\b|what(?:'s| is) the reason\b"),
    ("amount", r"how (?:much|many)\b"),
    ("time", r"how long\b|when\b|how often\b"),
    ("how", r"how\b"),
    ("where", r"where\b"),
    ("who", r"who\b|whose\b"),
    ("what", r"what\b|which\b"),
    ("yes_no", r"(?:are|is|was|were|do|does|did|have|has|had|can|could|will|would|should|shall|may|might)\b"),
]


class RepWordsError(ValueError):
    """A line that cannot be said: an unknown step, a step that asks nothing, or a line that is not a question."""


@dataclass(frozen=True)
class Match:
    step: str       # step id
    name: str       # the step's name in the script (empty for steps with none)
    stage: str      # ui_stage
    script: str     # the script's question there
    theirs: str     # the source's question said instead
    score: float    # how alike the two are, 0-1


def clean(line: str) -> str:
    """One spoken line: no markup, one line, single spaces, at most `max_chars` (cut at a word)."""
    text = re.sub(r"\s+([?.!,;:])", r"\1", re.sub(r"\s+", " ", _UNSAFE.sub("", line or ""))).strip(" -–•")
    limit = REP_WORDS["max_chars"]
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "?"
    return text


def _is_question(text: str) -> bool:
    words = len(text.split())
    return text.endswith("?") and REP_WORDS["min_words"] <= words <= REP_WORDS["max_words"]


def _one_each(question: str) -> list[str]:
    """"What's in the way and how long has it been a problem?" -> one question each: a compound question matches
    neither of the script's well."""
    parts = re.split(r",?\s+and\s+(?=(?:what|how|why|where|when|who|which)\b)", question, flags=re.IGNORECASE)
    return [p[:1].upper() + p[1:].rstrip("?").strip() + "?" for p in parts] if len(parts) > 1 else [question]


def questions_in(lines: list[str]) -> list[str]:
    """The questions said or written in `lines`, each once, in order: sentences ending in "?", the quoted question in
    an instruction ("Ask: 'What made you book the call?'"), never the instruction itself."""
    found: list[str] = []
    for line in lines:
        quoted = _QUOTED.findall(line or "")
        for raw in (p for q in (quoted or sentences(_INSTRUCTION.sub("", line or ""))) for p in _one_each(q)):
            text = clean(raw)
            if _is_question(text) and text.lower() not in {f.lower() for f in found}:
                found.append(text)
    return found


def _spoken(line: str) -> str:
    """A script line as it is heard, for matching: blanks become plain words ("{outcome|with $|...}" -> "with that")."""
    def fill(m: re.Match) -> str:
        return (m.group(2) or "").replace("$", "that") if m.group(2) is not None else "that"
    return re.sub(r"\s+", " ", NAME.sub(fill, line)).strip()


def _asks(say: str) -> tuple[int, int] | None:
    """Where a line's questions are: from the first question to the end of the last (the talk between them goes with
    them), or None when it asks nothing."""
    asks = [q for q in questions_of(say) if q.endswith("?")]
    if not asks:
        return None
    start = say.index(asks[0])
    return start, say.index(asks[-1], start) + len(asks[-1])


def kind(question: str) -> str:
    """What sort of answer a question asks for ("why", "amount", "yes_no", ...), or "" when its start doesn't say."""
    text = _FILLER.sub("", question.strip())
    return next((name for name, pattern in _KINDS if re.match(pattern, text, re.IGNORECASE)), "")


def _same_kind(a: str, b: str) -> bool:
    ka, kb = kind(a), kind(b)
    return not ka or not kb or ka == kb


def askable(method: Method) -> list[Step]:
    """The steps whose question a source line may say, in script order: they ask something and wait for the answer."""
    return [s for s in method.steps.values() if s.say and not s.run_on and _asks(s.say)]


def _swap(line: str, question: str) -> str:
    """The line with its questions said as `question`; the talk before and after stays ("Okay. So ... <question>")."""
    start, end = _asks(line)
    return line[:start] + question + line[end:]


def match(method: Method, questions: list[str], embed: Embed) -> list[Match]:
    """For each question step, the source question that asks the same thing, if one is close enough; in script order.
    Each source question takes one step at most. Below `sure_score` the two must ask for the same sort of answer
    ("How would that make you feel?" is no "Why do you feel it would?"). The call's own path is matched first, then
    the objection talks (whose closes repeat the main one) with the questions left."""
    steps = askable(method)
    if not steps or not questions:
        return []
    scripted = [_spoken(s.say[slice(*_asks(s.say))]) for s in steps]
    scores = similarity(scripted, questions, embed)
    sure = REP_WORDS["sure_score"]
    for i, row in enumerate(scores):   # a pair that fails the guard can never be made
        for j, v in enumerate(row):
            if v < sure and not _same_kind(scripted[i], questions[j]):
                row[j] = -1.0
    talks = set(method.talks)
    pairs: dict[int, int] = {}
    for in_talks in (False, True):
        rows = [i for i, s in enumerate(steps) if (s.id in talks) == in_talks]
        free = [j for j in range(len(questions)) if j not in pairs.values()]
        found = best_pairs([[scores[i][j] for j in free] for i in rows], REP_WORDS["min_score"])
        pairs.update({rows[r]: free[c] for r, c in found.items()})
    return [Match(s.id, s.name, s.ui_stage, scripted[i], questions[pairs[i]], round(scores[i][pairs[i]], 3))
            for i, s in enumerate(steps) if i in pairs]


def with_words(method: Method, words: dict[str, str]) -> Method:
    """The method with `words` ({step id: question}) said in place of those steps' questions; the talk around a
    question ("Okay. So ...") stays. Raises RepWordsError for a step that cannot take one or a line that is not a
    question."""
    if not isinstance(words, dict) or len(words) > REP_WORDS["max_lines"]:
        raise RepWordsError("too_many")
    open_steps = {s.id for s in askable(method)}
    steps = dict(method.steps)
    for step_id, line in words.items():
        if step_id not in open_steps:
            raise RepWordsError(f"step {step_id!r} asks nothing")
        text = clean(line) if isinstance(line, str) else ""
        if not _is_question(text):
            raise RepWordsError(f"step {step_id!r}: not a question")
        step = steps[step_id]
        # The plain line (the same talk without their words said back) gets the same question.
        plain = _swap(step.say_plain, text) if step.say_plain and _asks(step.say_plain) else ""
        steps[step_id] = replace(step, say=_swap(step.say, text), say_plain=plain, plain_if=step.plain_if if plain else "")
    return replace(method, steps=steps)
