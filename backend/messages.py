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

# Prospect module
PROSPECT_ERROR = "The prospect got confused - send that again."
PROSPECT_SCORING_ERROR = "Scoring didn't work - give it another go."
PROSPECT_SESSION_NOT_FOUND = "Prospect session not found"
PROSPECT_UNAVAILABLE = "The AI service isn't responding right now - nothing you did. Try again shortly."
PROSPECT_REVIEW_ERROR = "Couldn't rebuild the session review - try again."
