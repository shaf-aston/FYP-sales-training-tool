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


SELLER_INIT_FAILED = "Setup didn't complete - please try initializing again."

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

# Request checks
SESSION_ID_REQUIRED = "Session ID required"
INVALID_SESSION_ID = "Invalid session ID format"
MESSAGE_TOO_LONG = "Message too long (max {max_length} characters)"
INVALID_PAYLOAD = "Invalid payload"
NO_DATA = "No data provided"
UNKNOWN_FIELD = "Unknown field: {key}"
UNKNOWN_FIELDS = "Unknown fields: {keys}"
FIELD_NOT_TEXT = "Field '{key}' must be a string"
FIELD_TOO_LONG = "Field '{key}' exceeds {max_length} characters"
UNSUPPORTED_PROVIDER = "Unsupported provider"
FORBIDDEN = "Forbidden"
FEEDBACK_EMPTY = "Rating or comment required"
RATING_OUT_OF_RANGE = "Rating must be 1-5"
RATING_NOT_NUMBER = "Rating must be a number 1-5"

# Buy mode
MISSING_INDEX = "Missing message index"
INVALID_INDEX = "Invalid index format"
REWIND_FAILED = "Rewind failed"
EDIT_FAILED = "Couldn't apply that edit -- try again in a sec"
QUESTION_REQUIRED = "Question required"
QUESTION_TOO_LONG = "Question too long"
COACH_FAILED = "Failed to generate answer"
FIELD_REQUIRED = "{label} required"
LABEL_TOO_LONG = "{label} too long"

# Sell mode
OPTIONAL_TEXT_INVALID = "{field} must be text up to {limit} characters"
SESSION_ENDED = "Session has ended. Get evaluation or reset."
NO_TURNS_YET = "Say a few things to the buyer first - the quiz uses your own turns."
TURN_NOT_IN_SESSION = "That turn is not part of this session."
TURN_REQUIRED = "A turn number is required."
