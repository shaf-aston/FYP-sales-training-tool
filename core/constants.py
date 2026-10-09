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

# env-var defaults
DEFAULT_ALLOWED_ORIGINS = _L["defaults"]["allowed_origins"]
DEFAULT_LLM_PROVIDER_ORDER = _L["defaults"]["llm_provider_order"]
DEFAULT_GROQ_MODEL = _L["defaults"]["groq_model"]
DEFAULT_TRUST_PROXY_HEADERS = _L["defaults"]["trust_proxy_headers"]

SERVER_PORT = _L["server"]["port"]

# sessions
MAX_SELLER_SESSIONS = _L["sessions"]["seller_max"]
SELLER_IDLE_MINUTES = _L["sessions"]["seller_idle_minutes"]
MAX_BUYER_SESSIONS = _L["sessions"]["buyer_max"]
BUYER_IDLE_MINUTES = _L["sessions"]["buyer_idle_minutes"]
CLEANUP_INTERVAL_SECONDS = _L["sessions"]["cleanup_interval_seconds"]

# input validation
MAX_MESSAGE_LENGTH = _L["input"]["max_message_length"]
MAX_FIELD_LENGTH = _L["input"]["max_field_length"]
MAX_CHOSEN_OBJECTION_CHARS = _L["input"]["max_chosen_objection_chars"]
MAX_PERSONA_NAME_CHARS = _L["input"]["max_persona_name_chars"]
MAX_FEEDBACK_COMMENT_CHARS = _L["input"]["max_feedback_comment_chars"]
MAX_TURN_NUMBER = _L["input"]["max_turn_number"]
SESSION_ID_MIN_CHARS = _L["input"]["session_id_min_chars"]
SESSION_ID_MAX_CHARS = _L["input"]["session_id_max_chars"]
RATE_LIMITS = {route: tuple(limit) for route, limit in _L["rate_limits"].items()}

# LLM call profiles: router.chat_with_fallback(messages, **LLM["buyer_reply"])
LLM = _L["llm"]
DEFAULT_TEMPERATURE = LLM["default"]["temperature"]
DEFAULT_MAX_TOKENS = LLM["default"]["max_tokens"]
COACH_HISTORY_TURNS = _L["coach"]["history_turns"]


# buyer end rules
SOLD_READINESS = _L["buyer"]["sold_readiness"]
SOLD_MIN_TURNS = _L["buyer"]["sold_min_turns"]
WALK_MIN_TURNS = _L["buyer"]["walk_min_turns"]
WALK_READINESS = _L["buyer"]["walk_readiness"]

# grading
GRADE_THRESHOLDS = _L["grades"]["thresholds"]
GRADE_LABELS = _L["grades"]["labels"]

# response headers
SECURITY_HEADERS = _L["security"]["headers"]
API_HEADERS = _L["security"]["api_headers"]
CSP = _L["security"]["csp"]
