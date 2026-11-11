"""A buyer the learner describes (e.g. built from one of their real calls), checked before it reaches the prompt.

The same keys as a persona in buyer.yaml, plus `objections` ({type, text}) that the buyer raises in order
instead of the difficulty profile's bank. Text is length-capped; lists are capped and stripped of blanks.
The persona is marked `custom: True`, so it opens with buyer.yaml `custom_opening_lines`.
"""

from __future__ import annotations

from core.infra.constants import MAX_CUSTOM_BUYER_ITEMS, MAX_CUSTOM_BUYER_TEXT_CHARS

TEXT_FIELDS = ("name", "background", "personality", "budget")
LIST_FIELDS = ("needs", "pain_points")
OBJECTION_TYPES = ("price", "skepticism", "timing", "partner", "fear")


class InvalidCustomBuyer(ValueError):
    """The described buyer is the wrong shape; the message names the field."""


def _text(value, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value.strip()) > MAX_CUSTOM_BUYER_TEXT_CHARS:
        raise InvalidCustomBuyer(f"{field}: text up to {MAX_CUSTOM_BUYER_TEXT_CHARS} characters")
    return value.strip()


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
    texts = {field: _text(data.get(field), field) for field in TEXT_FIELDS}
    if not texts["name"]:
        raise InvalidCustomBuyer("name: required")
    # A blank field is left out, so the prompt's own default (e.g. a "mid-range" budget) applies.
    persona = {field: value for field, value in texts.items() if value} | {"custom": True}
    for field in LIST_FIELDS:
        persona[field] = [t for t in (_text(v, field) for v in _items(data.get(field), field)) if t]
    bank = []
    for item in _items(data.get("objections"), "objections"):
        kind = item.get("type") if isinstance(item, dict) else None
        if kind not in OBJECTION_TYPES:
            raise InvalidCustomBuyer(f"objections: type is one of {', '.join(OBJECTION_TYPES)}")
        text = _text(item.get("text"), "objections")
        if text:
            bank.append({"type": kind, "text": text})
    return persona, bank
