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

# voice mode
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
MAX_TTS_TEXT_LENGTH = 5000

# session & performance
MAX_METRICS_LINES = 5000
METRICS_KEEP_AFTER_ROTATION = 2500
MAX_ANALYTICS_LINES = 10000
ANALYTICS_KEEP_AFTER_ROTATION = 5000
MAX_PROSPECT_SESSIONS = 100
PROSPECT_IDLE_MINUTES = 30
# Note: SESSION_IDLE_MINUTES and MAX_SESSIONS are defined in web/security.py (SSoT)

# input validation
MAX_FIELD_LENGTH = 5000
TERSE_INPUT_THRESHOLD = 3
# Note: MAX_MESSAGE_LENGTH is defined in web/security.py (SSoT)

# strategy detection - any more than 3 turns can be frustrating for the user
MIN_TURNS_BEFORE_ADVANCE = 3

# LLM provider
DEFAULT_TEMPERATURE = 0.8
DEFAULT_MAX_TOKENS = 200

