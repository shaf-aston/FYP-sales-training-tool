"""Canonical user-facing error strings. Centralised so tone stays consistent."""

# Generic errors
GENERIC_ERROR = "Something broke on our end - give it another go."
INTERNAL_SERVER_ERROR = "Internal server error"

# Rate limiting
RATE_LIMIT_ERROR = "Too much traffic right now - hold on a second and try again."
SERVER_FULL = "Server is currently full - please check back in a moment"

# Session management
SESSION_ID_REQUIRED = "Session ID required"
SESSION_NOT_FOUND = "Session not found"
SESSION_RESTORE_FAILED = "Couldn't restore that session - you can start a new one or try again."

# Message validation
MESSAGE_REQUIRED = "Message required"
INVALID_HISTORY_FORMAT = "Invalid history format"
INVALID_HISTORY_ENTRY = "Invalid history entry"


def history_entry_too_long(max_chars: int) -> str:
    return f"History entry too long (max {max_chars} characters)"


# FSM state mutations
def invalid_stage(available_stages: list) -> str:
    return f"Invalid stage. Available: {available_stages}"


def invalid_strategy(available_strategies: set) -> str:
    return f"Invalid strategy. Available: {sorted(available_strategies)}"


STRATEGY_SWITCH_FAILED = "Failed to switch strategy"
BOT_INIT_FAILED = "Setup didn't complete - please try initializing again."
SCORE_CALCULATION_FAILED = "Failed to calculate score"

# Voice module
VOICE_ERROR = "Voice mode ran into trouble - try that again."
VOICE_TTS_ERROR = "Speech generation didn't work - try that again."

# Prospect module
PROSPECT_ERROR = "The prospect got confused - send that again."
PROSPECT_SCORING_ERROR = "Scoring didn't work - give it another go."
PROSPECT_SESSION_NOT_FOUND = "Prospect session not found"
