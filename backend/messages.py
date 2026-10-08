"""Canonical user-facing error strings. Centralised so tone stays consistent."""

# Generic errors
GENERIC_ERROR = "Something broke on our end - give it another go."
INTERNAL_SERVER_ERROR = "Internal server error"

# Rate limiting
RATE_LIMIT_ERROR = "Too much traffic right now - hold on a second and try again."
SERVER_FULL = "Server is currently full - please check back in a moment"

# Session management
SESSION_NOT_FOUND = "Session not found"

# Message validation
MESSAGE_REQUIRED = "Message required"


BOT_INIT_FAILED = "Setup didn't complete - please try initializing again."

# Sell mode (the AI buyer)
SELL_ERROR = "The buyer got confused - send that again."
SELL_SCORING_ERROR = "Scoring didn't work - give it another go."
SELL_SESSION_NOT_FOUND = "Sell session not found"
SELL_UNAVAILABLE = "The AI service isn't responding right now - nothing you did. Try again shortly."
SELL_FULL = "Sell mode is at capacity - check back in a moment."
SELL_SETUP_FAILED = "Couldn't set up the buyer -- try once more"
INVALID_DIFFICULTY = "Invalid difficulty. Choose: {choices}"
UNKNOWN_PERSONA = "Unknown persona '{name}' for product '{product}'"
SELL_REVIEW_ERROR = "Couldn't rebuild the session review - try again."
