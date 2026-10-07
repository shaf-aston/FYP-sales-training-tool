"""Every tunable number, read once from config/limits.yaml and validated."""

from .loader import load_yaml


def _check_positive(node, path="limits"):
    """Fail loud on any zero or negative number anywhere in the tree."""
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        if node <= 0:
            raise ValueError(f"{path} must be > 0, got {node}")
    elif isinstance(node, dict):
        for key, value in node.items():
            _check_positive(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _check_positive(value, f"{path}[{i}]")


_L = load_yaml("limits.yaml")
_check_positive(_L)

# stage display
UNDETERMINED_STAGE = "----"  # shown when intent strategy hasn't resolved yet

# conversation context
RECENT_HISTORY_WINDOW = _L["context"]["recent_history_window"]
MAX_USER_KEYWORDS = _L["context"]["max_user_keywords"]
TERSE_INPUT_THRESHOLD = _L["context"]["terse_input_threshold"]
MIN_TURNS_BEFORE_ADVANCE = _L["context"]["min_turns_before_advance"]

# sessions
MAX_SESSIONS = _L["sessions"]["seller_max"]
SESSION_IDLE_MINUTES = _L["sessions"]["seller_idle_minutes"]
MAX_PROSPECT_SESSIONS = _L["sessions"]["buyer_max"]
PROSPECT_IDLE_MINUTES = _L["sessions"]["buyer_idle_minutes"]
CLEANUP_INTERVAL_SECONDS = _L["sessions"]["cleanup_interval_seconds"]

# input validation
MAX_MESSAGE_LENGTH = _L["input"]["max_message_length"]
MAX_FIELD_LENGTH = _L["input"]["max_field_length"]
MAX_CHOSEN_OBJECTION_CHARS = _L["input"]["max_chosen_objection_chars"]
MAX_PERSONA_NAME_CHARS = _L["input"]["max_persona_name_chars"]
RATE_LIMITS = {route: tuple(limit) for route, limit in _L["rate_limits"].items()}

# LLM call profiles: router.chat_with_fallback(messages, **LLM["buyer_reply"])
LLM = _L["llm"]
DEFAULT_TEMPERATURE = LLM["default"]["temperature"]
DEFAULT_MAX_TOKENS = LLM["default"]["max_tokens"]


# buyer end rules
SOLD_READINESS = _L["buyer"]["sold_readiness"]
SOLD_MIN_TURNS = _L["buyer"]["sold_min_turns"]
WALK_MIN_TURNS = _L["buyer"]["walk_min_turns"]
WALK_READINESS = _L["buyer"]["walk_readiness"]

# grading
GRADE_THRESHOLDS = _L["grades"]["thresholds"]
GRADE_LABELS = _L["grades"]["labels"]
