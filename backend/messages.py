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


EDIT_NOT_ALLOWED = "Only your own messages in this chat can be edited."
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
CUSTOM_BUYER_INVALID = "That buyer can't be used: {detail}"

# Accounts and teams (/api/account, /api/team)
LOGIN_REQUIRED = "Log in to use this."
BAD_LOGIN = "That email and password don't match an account."
LOGIN_LOCKED = "Too many wrong passwords for this email. Wait 15 minutes and try again."
PASSWORD_WRONG = "That password isn't right."
ACCOUNT_FIELD_ERRORS = {
    ("email", "invalid"): "Enter a valid email address.",
    ("email", "taken"): "There's already an account with that email. Log in instead.",
    ("name", "invalid"): "Enter your name (up to 60 characters).",
    ("password", "too_short"): "Use at least 8 characters for your password.",
    ("password", "too_long"): "Use at most 256 characters for your password.",
}
SKILL_ENTRIES_INVALID = "Those scores couldn't be saved: send up to {max} entries in the skill log format."
PROSPECTS_FULL = "You've saved {max} prospects. Delete one to save another."
PROSPECT_NOT_FOUND = "That saved prospect doesn't exist."
TEAM_ERRORS = {
    "name_invalid": "Give the team a name (up to 60 characters).",
    "already_in_team": "You're already in a team. Leave it first.",
    "unknown_code": "No team has that invite code. Check it with your manager.",
    "not_in_team": "You're not in a team.",
    "not_manager": "Only the team's manager can do that.",
    "not_a_member": "That person isn't in your team.",
}

# Uploaded calls (/api/calls)
CALL_TEXT_REQUIRED = "Paste a call transcript or choose a file."
CALL_UNREADABLE_TEXT = "Couldn't find who said what. Use a transcript with speaker names, like \"Jane: Hi there\" on each line, or a Zoom, Teams or Fathom export."
CALL_TOO_LONG_TEXT = "That transcript is too long. Keep it under {max_chars:,} characters."
CALL_TOO_SHORT_TEXT = "That's too short to learn from. Use a call with a few back-and-forth turns between two people."
CALL_UNKNOWN_SPEAKER_TEXT = "Nobody called {name} speaks in this call."
CALL_ONE_SPEAKER_TEXT = "Everyone in this transcript is labelled \"{name}\". Name the speakers (or export it with names) so we can tell you from the prospect."
REQUEST_TOO_LARGE = "That's too big to send. Keep files under 1 MB."

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
FEEDBACK_EMPTY = "Rating or comment required"
RATING_OUT_OF_RANGE = "Rating must be 1-5"
RATING_NOT_NUMBER = "Rating must be a number 1-5"

# Buy mode
MISSING_INDEX = "Missing message index"
INVALID_INDEX = "Invalid index format"
INVALID_STEP = "That step does not exist"
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
