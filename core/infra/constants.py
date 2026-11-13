"""Every tunable number, read once from config/limits.yaml and validated."""

from core.infra.loader import load_yaml


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
GROQ_REASONING_EFFORT = _L["defaults"]["groq_reasoning_effort"]
SPEECH = _L["speech"]
DICTATION = _L["dictation"]
TRANSCRIPTION = _L["transcription"]
SOP_LIMITS = _L["sop"]
REP_WORDS = _L["rep_words"]
DEFAULT_TRUST_PROXY_HEADERS = _L["defaults"]["trust_proxy_headers"]
CLIENT_IP_HEADERS = tuple(_L["defaults"]["client_ip_headers"])
DEFAULT_LOGS_DIR = _L["defaults"]["logs_dir"]
LOG_LEVEL = _L["defaults"]["log_level"]
DEFAULT_DB_PATH = _L["defaults"]["db_path"]
DEFAULT_BACKUP_DIR = _L["defaults"]["backup_dir"]
BACKUPS_KEEP = _L["backups"]["keep"]

SERVER_PORT = _L["server"]["port"]

# sessions
MAX_SELLER_SESSIONS = _L["sessions"]["seller_max"]
SELLER_IDLE_MINUTES = _L["sessions"]["seller_idle_minutes"]
MAX_BUYER_SESSIONS = _L["sessions"]["buyer_max"]
BUYER_IDLE_MINUTES = _L["sessions"]["buyer_idle_minutes"]
CLEANUP_INTERVAL_SECONDS = _L["sessions"]["cleanup_interval_seconds"]

# input validation
MAX_REQUEST_BYTES = _L["input"]["max_request_bytes"]
MAX_MESSAGE_LENGTH = _L["input"]["max_message_length"]
MAX_FIELD_LENGTH = _L["input"]["max_field_length"]
MAX_CHOSEN_OBJECTION_CHARS = _L["input"]["max_chosen_objection_chars"]
MAX_PERSONA_NAME_CHARS = _L["input"]["max_persona_name_chars"]
MAX_CUSTOM_BUYER_TEXT_CHARS = _L["input"]["max_custom_buyer_text_chars"]
MAX_CUSTOM_BUYER_ITEMS = _L["input"]["max_custom_buyer_items"]
MAX_FEEDBACK_COMMENT_CHARS = _L["input"]["max_feedback_comment_chars"]
MAX_FEEDBACK_PAGE_CHARS = _L["input"]["max_feedback_page_chars"]
MAX_TURN_NUMBER = _L["input"]["max_turn_number"]
SESSION_ID_MIN_CHARS = _L["input"]["session_id_min_chars"]
SESSION_ID_MAX_CHARS = _L["input"]["session_id_max_chars"]
RATE_LIMIT_PEER_FACTOR = _L["rate_limit_peer_factor"]
RATE_LIMITS = {route: tuple(limit) for route, limit in _L["rate_limits"].items()}

# uploaded calls (core/calls): read-only mapping of the `calls:` block
CALL_LIMITS = _L["calls"]

# accounts
_A = _L["accounts"]
MIN_PASSWORD_CHARS = _A["min_password_chars"]
MAX_PASSWORD_CHARS = _A["max_password_chars"]
MAX_EMAIL_CHARS = _A["max_email_chars"]
MAX_ACCOUNT_NAME_CHARS = _A["max_account_name_chars"]
MAX_TEAM_NAME_CHARS = _A["max_team_name_chars"]
MAX_SKILL_ENTRIES = _A["max_skill_entries"]
MAX_SAVED_PROSPECTS = _A["max_saved_prospects"]
MAX_SAVED_WORDS = _A["max_saved_words"]
SCRYPT_N, SCRYPT_R, SCRYPT_P = _A["scrypt"]["n"], _A["scrypt"]["r"], _A["scrypt"]["p"]
SESSION_DAYS = _A["session_days"]
INVITE_CODE_LENGTH = _A["invite_code_length"]
MAX_SKILLS_PER_ENTRY = _A["max_skills_per_entry"]
MAX_SKILL_ID_CHARS = _A["max_skill_id_chars"]
LOGIN_FAILURES, LOGIN_FAILURE_WINDOW_SECONDS = _A["login_failures"]
SIGN_IN_LINKS = _A["sign_in_links"]
FRESH_LOGIN_MINUTES = _A["fresh_login_minutes"]

# provider requests
PROVIDER_TIMEOUT_SECONDS = _L["provider"]["timeout_seconds"]
PROVIDER_ATTEMPTS = _L["provider"]["attempts"]

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
