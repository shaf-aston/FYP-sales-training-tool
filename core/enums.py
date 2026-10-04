"""Every string enum the app shares: roles, stages, strategies, objection types."""

from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Strategy(str, Enum):
    """Which stage sequence the seller bot follows (config key: strategy / flow_type)."""
    CONSULTATIVE = "consultative"
    TRANSACTIONAL = "transactional"
    INTENT = "intent"  # strategy not chosen yet; bot is still probing


class Stage(str, Enum):
    """Where the sales conversation is."""
    INTENT = "intent"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    PITCH = "pitch"
    NEGOTIATION = "negotiation"
    OBJECTION = "objection"
    OUTCOME = "outcome"  # the closing stage, not the sold/walked result


class ObjectionType(str, Enum):
    MONEY = "money"
    PARTNER = "partner"
    FEAR = "fear"
    LOGISTICAL = "logistical"
    THINK = "think"
    SMOKESCREEN = "smokescreen"
    UNKNOWN = "unknown"
