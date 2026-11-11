"""A buyer the learner describes (e.g. built from one of their real calls), checked before it reaches the prompt.

The same keys as a persona in buyer.yaml, plus `objections` ({type, text}) that the buyer raises in order
instead of the difficulty profile's bank. Text is length-capped; lists are capped and stripped of blanks.
The persona is marked `custom: True`, so it opens with buyer.yaml `custom_opening_lines`.

`replay` is where the conversation starts instead of an opening line: a transcript (e.g. a real call up to the
turn the learner wants to redo) that ends with the buyer speaking.
"""

from __future__ import annotations

import re

from core.infra.constants import (
    MAX_CUSTOM_BUYER_ITEMS,
    MAX_CUSTOM_BUYER_TEXT_CHARS,
    MAX_FIELD_LENGTH,
    MAX_PERSONA_NAME_CHARS,
    MAX_TURN_NUMBER,
)
from core.infra.loader import load_buyer_config

TEXT_FIELDS = ("name", "background", "personality", "budget")
LIST_FIELDS = ("needs", "pain_points")
# Line breaks and control characters become one space: a field is one line in the buyer's prompt and can never
# start a section of its own ("Bob\n\nRULES: ...").
_UNPRINTABLE = re.compile(r"[\s\x00-\x1f\x7f\u2028\u2029]+")


def concern_types() -> list[str]:
    """The buyer's objection types (buyer.yaml real_objections.type_map values): the only ones a buyer raises."""
    return sorted(set(load_buyer_config()["real_objections"]["type_map"].values()))


class InvalidCustomBuyer(ValueError):
    """The described buyer is the wrong shape; the message names the field."""


def _text(value, field: str, limit: int = MAX_CUSTOM_BUYER_TEXT_CHARS) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidCustomBuyer(f"{field}: text up to {limit} characters")
    text = _UNPRINTABLE.sub(" ", value).strip()
    if len(text) > limit:
        raise InvalidCustomBuyer(f"{field}: text up to {limit} characters")
    return text


def _items(value, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_CUSTOM_BUYER_ITEMS:
        raise InvalidCustomBuyer(f"{field}: a list of up to {MAX_CUSTOM_BUYER_ITEMS}")
    return value


def parse_custom_buyer(data) -> tuple[dict, list[dict]]:
    """(persona, objection bank) from the request's `custom_buyer`. Raises InvalidCustomBuyer."""
    if not isinstance(data, dict):
        raise InvalidCustomBuyer("custom_buyer: an object")
    texts = {field: _text(data.get(field), field, MAX_PERSONA_NAME_CHARS if field == "name" else MAX_CUSTOM_BUYER_TEXT_CHARS)
             for field in TEXT_FIELDS}
    if not texts["name"]:
        raise InvalidCustomBuyer("name: required")
    # A blank field is left out, so the prompt's own default (e.g. a "mid-range" budget) applies.
    persona = {field: value for field, value in texts.items() if value} | {"custom": True}
    for field in LIST_FIELDS:
        persona[field] = [t for t in (_text(v, field) for v in _items(data.get(field), field)) if t]
    bank, kinds = [], concern_types()
    for item in _items(data.get("objections"), "objections"):
        kind = item.get("type") if isinstance(item, dict) else None
        if kind not in kinds:
            raise InvalidCustomBuyer(f"objections: type is one of {', '.join(kinds)}")
        text = _text(item.get("text"), "objections")
        if text:
            bank.append({"type": kind, "text": text})
    return persona, bank


def parse_replay(data) -> list[dict]:
    """The transcript to continue from: {role: user|assistant, content}, ending with the buyer.
    Raises InvalidCustomBuyer."""
    if not isinstance(data, list) or not data or len(data) > 2 * MAX_TURN_NUMBER:
        raise InvalidCustomBuyer(f"replay: a list of up to {2 * MAX_TURN_NUMBER} lines")
    history = []
    for entry in data:
        role = entry.get("role") if isinstance(entry, dict) else None
        content = entry.get("content") if isinstance(entry, dict) else None
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip() \
                or len(content) > MAX_FIELD_LENGTH:
            raise InvalidCustomBuyer(f"replay: each line is a user or assistant line up to {MAX_FIELD_LENGTH} characters")
        history.append({"role": role, "content": content.strip()})
    if history[-1]["role"] != "assistant":
        raise InvalidCustomBuyer("replay: must end with the buyer's line")
    return history
