"""Shared string enums."""

from enum import Enum


class Stage(str, Enum):
    """Where the sales conversation is (the script's ui_stage)."""
    INTENT = "intent"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    PITCH = "pitch"
    OUTCOME = "outcome"  # the closing stage, not the sold/walked result
