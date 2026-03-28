"""Centralised configuration constants for chatbot behaviour.

All magic numbers and thresholds used across the chatbot system.
Modify these values to tune behaviour without touching core logic.
"""

# ============================================================================
# Conversation History & Context
# ============================================================================

# Number of recent turns to send to LLM (prevents context overflow)
RECENT_HISTORY_WINDOW = 10

# Multiplier for history window when analyzing patterns
HISTORY_WINDOW_MULTIPLIER = 2

# Turn interval for persona/strategy checkpoint reinforcement
PERSONA_CHECKPOINT_TURNS = 6

# Maximum keywords to extract from user messages for embedding
MAX_USER_KEYWORDS = 6

# Maximum reframe attempts before escalation (FUTURE - not yet implemented)
MAX_OBJECTION_REFRAMES = 3


# ============================================================================
# Web Search Enrichment
# ============================================================================

# Minimum seconds between web search API calls (rate limiting)
MIN_SECONDS_BETWEEN_SEARCHES = 30

# Default cache TTL for search results (seconds)
SEARCH_CACHE_TTL_SECONDS = 1800  # 30 minutes

# Maximum search results to inject into prompt
MAX_SEARCH_RESULTS = 3


# ============================================================================
# Voice Mode Limits
# ============================================================================

# Maximum audio file size for STT (Whisper API limit)
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25MB

# Maximum text length for TTS synthesis
MAX_TTS_TEXT_LENGTH = 5000  # characters


# ============================================================================
# Session & Performance
# ============================================================================

# Maximum lines in metrics.jsonl before rotation
MAX_METRICS_LINES = 5000

# Lines to keep after metrics rotation (keeps newest half)
METRICS_KEEP_AFTER_ROTATION = 2500

# Maximum lines in analytics.jsonl before rotation
MAX_ANALYTICS_LINES = 10000

# Lines to keep after analytics rotation
ANALYTICS_KEEP_AFTER_ROTATION = 5000

# Session idle timeout (minutes)
SESSION_IDLE_MINUTES = 360  # 6 hours

# Maximum concurrent sessions (capacity limit)
MAX_SESSIONS = 200

# Prospect mode session limit
MAX_PROSPECT_SESSIONS = 100

# Prospect mode idle timeout (minutes)
PROSPECT_IDLE_MINUTES = 30


# ============================================================================
# Input Validation & Security
# ============================================================================

# Maximum user message length (characters)
MAX_MESSAGE_LENGTH = 2000

# Maximum custom knowledge field length
MAX_FIELD_LENGTH = 5000

# Terse input threshold (word count) - triggers simplified response
TERSE_INPUT_THRESHOLD = 3


# ============================================================================
# Strategy Detection
# ============================================================================

# Minimum turns in INTENT stage before forcing consultative fallback
MIN_TURNS_BEFORE_STRATEGY_FALLBACK = 3


# ============================================================================
# LLM Provider Settings
# ============================================================================

# Default temperature for chat completions
DEFAULT_TEMPERATURE = 0.8

# Default max tokens for chat responses
DEFAULT_MAX_TOKENS = 200

# Training/coaching max tokens (longer explanations)
TRAINING_MAX_TOKENS = 300
