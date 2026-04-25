"""Centralized string constants to prevent typos and enable safe refactoring."""


class MessageRole:
    """Conversation message roles."""
    USER = "user"
    ASSISTANT = "assistant"


class ObjectionType:
    """Objection classification types."""
    MONEY = "money"
    PARTNER = "partner"
    FEAR = "fear"
    LOGISTICAL = "logistical"
    THINK = "think"
    SMOKESCREEN = "smokescreen"
    UNKNOWN = "unknown"


class ObjectionCategory:
    """High-level objection categories."""
    RESOURCE = "resource"
    STAKEHOLDER = "stakeholder"
    INTERNAL = "internal"
    UNCLEAR = "unclear"
