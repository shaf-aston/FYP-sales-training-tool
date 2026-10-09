"""Shared string enums."""

from enum import StrEnum


class Stage(StrEnum):
    """Where the sales conversation is (the script's ui_stage)."""
    INTENT = "intent"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    PITCH = "pitch"
    OUTCOME = "outcome"  # the closing stage, not the sold/walked result
