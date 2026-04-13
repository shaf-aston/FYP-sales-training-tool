"""All magic numbers and limits live here"""

# conversation context
RECENT_HISTORY_WINDOW = 10
PERSONA_CHECKPOINT_TURNS = 6
MAX_USER_KEYWORDS = 6

# web search
MIN_SECONDS_BETWEEN_SEARCHES = 30
SEARCH_CACHE_TTL_SECONDS = 1800  # 30 min
MAX_SEARCH_RESULTS = 3

# voice mode
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
MAX_TTS_TEXT_LENGTH = 5000

# session & performance
MAX_METRICS_LINES = 5000
METRICS_KEEP_AFTER_ROTATION = 2500
MAX_ANALYTICS_LINES = 10000
ANALYTICS_KEEP_AFTER_ROTATION = 5000
SESSION_IDLE_MINUTES = 360  # 6 hours
MAX_SESSIONS = 200
MAX_PROSPECT_SESSIONS = 100
PROSPECT_IDLE_MINUTES = 30

# input validation
MAX_MESSAGE_LENGTH = 2000
MAX_FIELD_LENGTH = 5000
TERSE_INPUT_THRESHOLD = 3

# strategy detection
MIN_TURNS_BEFORE_STRATEGY_FALLBACK = 3

# LLM provider
DEFAULT_TEMPERATURE = 0.8
DEFAULT_MAX_TOKENS = 200

# scoring and evaluation
SCORING_RUBRIC = {
    "stage_points": {"objection": 30, "pitch": 22, "emotional": 15, "logical": 10, "intent": 5},
    "signal_detection_max": 25,
    "objection_handling_max": 20,
    "questioning_depth_max": 15,
    "questioning_depth_per_hit": 5,
    "conversation_length_max": 10,
    "sweet_spot_turns": (7, 12),
}

STAGE_TIMEOUTTHRESHOLDS = {"intent": 6, "logical": 10, "emotional": 10}
