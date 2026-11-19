"""An SOP step as the rep would say it: "Ask what they want to achieve" -> "What do you want to achieve?".

Rules only, for the common ways SOPs write a question to ask: "Ask (them) (directly) <what / how / who ...>",
"Ask (them) if / whether <...>", "Find out <what ...>". The prospect becomes "you", and the question is put in
question order ("how long it has been" -> "how long has it been", "what they want" -> "what do you want"). A step
that already says its question ("Ask: 'What made you book?'") or is not a question to ask gives None: the caller
keeps the SOP's own words.
"""

from __future__ import annotations

import re

_LEAD = re.compile(
    r"^(?:ask|find out|check|confirm|establish|understand|learn|discover)\b(?:\s+(?:them|the prospect|the client|"
    r"the customer|the lead|directly|simply|openly|clearly|again))*\s+", re.IGNORECASE)
_WH = r"(?:what|how|why|where|when|who|which|whose)"
_SUBJECT = r"(?:you|it|we|this|that|there)"
_AUX = r"(?:are|is|was|were|have|has|had|can|could|will|would|should|did|do|does|might|may)"
# A word that makes "you" its object: "what made you book", "what brought you here", "what would stop you joining".
_VERB = re.compile(r"^(?:\w+ed|made|makes|got|gets|brought|brings|led|leads|kept|keeps|took|takes|gave|gives|stops|"
                   r"drives|drove|would|could|should|will|can|did|does|do|might|may|must)$", re.IGNORECASE)
_PAST = {"found": "find", "got": "get", "came": "come", "went": "go", "heard": "hear", "saw": "see", "chose": "choose",
         "knew": "know", "thought": "think", "felt": "feel", "met": "meet", "paid": "pay", "spent": "spend",
         "bought": "buy", "began": "begin", "started": "start", "tried": "try", "decided": "decide",
         "wanted": "want", "joined": "join", "booked": "book", "reached": "reach", "looked": "look"}
# The prospect, written in the third person, said to them in the second.
_YOU = [(r"\bthey're\b", "you're"), (r"\bthey've\b", "you've"), (r"\bthey'd\b", "you'd"), (r"\bthey'll\b", "you'll"),
        (r"\bthey\b", "you"), (r"\bthem\b", "you"), (r"\btheirs\b", "yours"), (r"\btheir\b", "your"),
        (r"\bthemselves\b", "yourself"), (r"\bthe prospect\b", "you"), (r"\bthe client\b", "you"),
        (r"\bthe customer\b", "you"), (r"\byou is\b", "you are"), (r"\byou was\b", "you were"),
        (r"\byou has\b", "you have"), (r"\byou does\b", "you do"), (r"\byou wants\b", "you want"),
        (r"\byou needs\b", "you need")]


def _past_ed(word: str) -> bool:
    """"reconsidered" is a past tense; "need", "proceed" are not."""
    return word.endswith("ed") and not word.endswith("eed")


def _second_person(text: str) -> str:
    for pattern, said in _YOU:
        text = re.sub(pattern, said, text, flags=re.IGNORECASE)
    return text


def _question_order(clause: str) -> str:
    """One "what they want" clause in the order a question takes."""
    # "how long it has been a problem" -> "how long has it been a problem"
    m = re.match(rf"^({_WH}(?:\s+(?!{_SUBJECT}\b)\w+){{0,3}}?)\s+({_SUBJECT})\s+({_AUX})\b(.*)$", clause, re.IGNORECASE)
    if m:
        return f"{m.group(1)} {m.group(3)} {m.group(2)}{m.group(4)}"
    # "what specifically you need to think through" -> "what specifically do you need to think through"; never when
    # "you" is the object of a verb before it ("what made you book the call" is a question already)
    m = re.match(rf"^({_WH}(?:\s+(?!you\b)\w+){{0,3}}?)\s+you\s+(?!{_AUX}\b)(\w+)(.*)$", clause, re.IGNORECASE)
    if m and not any(_VERB.match(w) for w in m.group(1).split()[1:]):
        verb = m.group(2).lower()
        if verb in _PAST:   # "how they found us" -> "how did you find us"
            return f"{m.group(1)} did you {_PAST[verb]}{m.group(3)}"
        if _past_ed(verb):   # no safe way to its plain form ("reconsidered"): leave the step unsaid
            return ""
        return f"{m.group(1)} do you {m.group(2)}{m.group(3)}"
    # "what your biggest challenge is", "what your goals are for next year" -> "what is your ...", "what are your ..."
    m = re.match(rf"^({_WH})\s+((?:your|the|this|that|these|those)\b.+?)\s+(is|are|was|were)\b(.*)$", clause, re.IGNORECASE)
    if m:
        return f"{m.group(1)} {m.group(3)} {m.group(2)}{m.group(4)}"
    return clause


def _yes_no(clause: str) -> str:
    """"you want to go ahead" -> "do you want to go ahead"; "you're ready" -> "are you ready"."""
    clause = re.sub(r"^you're\b", "you are", clause, flags=re.IGNORECASE)
    m = re.match(rf"^({_SUBJECT})\s+({_AUX})\b(.*)$", clause, re.IGNORECASE)
    if m:
        return f"{m.group(2)} {m.group(1)}{m.group(3)}"
    m = re.match(r"^you\s+(\w+)(.*)$", clause, re.IGNORECASE)
    if not m or _past_ed(m.group(1).lower()) or m.group(1).lower() in _PAST:
        return ""   # "it all makes sense", "you decided": no safe question order, so the step is left unsaid
    return f"do you {m.group(1)}{m.group(2)}"


def as_question(step: str) -> str | None:
    """The question an SOP step tells the rep to ask, worded as the rep says it; None when it asks nothing."""
    text = re.sub(r"\s+", " ", step or "").strip().rstrip(".!;:")
    lead = _LEAD.match(text)
    if not lead or "?" in text:
        return None
    rest = _second_person(text[lead.end():])
    m = re.match(r"^(?:if|whether)\s+(.*)$", rest, re.IGNORECASE)
    if m:
        said = _yes_no(re.sub(r"\s+or not$", "", m.group(1)))
        if not said:
            return None
    elif re.match(rf"^{_WH}\b", rest, re.IGNORECASE):
        # "what's in the way and how long it has been a problem": each question clause in question order
        clauses = re.split(rf"\s+and\s+(?={_WH}\b)", rest, flags=re.IGNORECASE)
        ordered = [_question_order(c) for c in clauses]
        if not all(ordered):
            return None
        said = " and ".join(ordered)
    else:
        return None
    return said[:1].upper() + said[1:] + "?"
