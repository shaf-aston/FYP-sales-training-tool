"""All magic numbers and limits live here"""

# stage display
UNDETERMINED_STAGE = "----"  # shown when intent strategy hasn't resolved yet

# response validation (Layer 3)
MIN_RESPONSE_CHARS = 40
MAX_RESPONSE_CHARS = 1500

# conversation context
RECENT_HISTORY_WINDOW = 10
PERSONA_CHECKPOINT_TURNS = 6
MAX_USER_KEYWORDS = 6

# session & performance
MAX_PROSPECT_SESSIONS = 100
# A learner-chosen objection to practise, and a persona name, as typed in prospect setup.
MAX_CHOSEN_OBJECTION_CHARS = 200
MAX_PERSONA_NAME_CHARS = 40
PROSPECT_IDLE_MINUTES = 30
# Note: SESSION_IDLE_MINUTES and MAX_SESSIONS are defined in web/security.py (SSoT)

# input validation
MAX_FIELD_LENGTH = 5000
TERSE_INPUT_THRESHOLD = 3
# Note: MAX_MESSAGE_LENGTH is defined in web/security.py (SSoT)

# strategy detection - any more than 3 turns can be frustrating for the user
MIN_TURNS_BEFORE_ADVANCE = 3

# LLM provider. Lower = steadier wording across chats; rules already pick what to say.
DEFAULT_TEMPERATURE = 0.4
# The AI buyer gets a little more variety so personas don't all sound alike.
BUYER_TEMPERATURE = 0.6
# Replies run 12-80 tokens; Groq charges the requested cap against the free per-minute budget.
DEFAULT_MAX_TOKENS = 150

