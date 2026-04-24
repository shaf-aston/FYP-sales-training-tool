"""Signal detection utilities for conversation turns"""

import re
from dataclasses import dataclass
from typing import Any, TypedDict, NotRequired

from .constants import MAX_USER_KEYWORDS
from .loader import load_analysis_config, load_objection_flows, load_signals
from .utils import contains_nonnegated_keyword

@dataclass
class ConversationState:
    """Snapshot of a single conversation turn"""

    intent: str  # "low", "medium", "high"
    guarded: bool  # defensive/evasive behaviour detected
    question_fatigue: bool  # bot asked too many questions recently
    decisive: bool  # high intent + not guarded

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

class ObjectionPathway(TypedDict):
    """Result of objection analysis with classification and reframe sequence.
    
    Includes objection type, recommended strategy, and reframe guidance.
    """

    # Base keys (always present)
    type: str
    strategy: str
    guidance: str

    # Enhanced keys (new pathway metadata)
    category: NotRequired[str]  # "resource", "stakeholder", "internal", "unclear"
    subtype: NotRequired[str]
    entry_question: NotRequired[str]
    reframes: NotRequired[list[str]]
    reframe_descriptions: NotRequired[dict[str, dict[str, str]]]
    funding_options: NotRequired[list[str]]
    open_wallet_applicable: NotRequired[bool]
    dialogue_guidance: NotRequired[str]
    is_primary_objection: NotRequired[bool]

ANALYSIS_CONFIG = load_analysis_config()
THRESHOLDS = ANALYSIS_CONFIG["thresholds"]
SIGNALS = load_signals()
OFLOWS = load_objection_flows()

STOP_WORDS = frozenset(
    {
        "i",
        "me",
        "my",
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "it",
        "its",
        "this",
        "that",
        "not",
        "no",
        "yes",
        "just",
        "so",
        "but",
        "and",
        "or",
        "if",
        "then",
        "than",
        "too",
        "very",
        "really",
        "also",
        "like",
        "you",
        "your",
        "dont",
        "im",
        "ive",
        "some",
        "what",
        "how",
        "about",
        "etc",
        "want",
        "need",
        "get",
        "got",
        "one",
        "know",
    }
)

# loaded once at import
_AGREEMENT_WORDS = frozenset(
    SIGNALS.get("guardedness_keywords", {}).get("agreement_words", [])
)
_DISMISSAL_WORDS = frozenset(
    SIGNALS.get("guardedness_keywords", {}).get("dismissal", [])
)

_GOAL_VERB_PATTERN = re.compile(r"\b(?:want to|need to|trying to)\s+\w+\s+\w+")

# evasive signals weigh more than defensive ones
_GUARDEDNESS_WEIGHTS = {
    "evasive": 0.5,
    "sarcasm": 0.35,
    "deflection": 0.2,
    "defensive": 0.1,
}

_TERSE_FOLLOW_UPS = frozenset(
    {
        "ok",
        "okay",
        "sure",
        "yeah",
        "yep",
        "alright",
        "fine",
        "nothing really",
        "not really",
        "nothing specific",
        "not sure",
        "idk",
        "i don't know",
        "dont know",
        "no idea",
    }
)

def has_user_stated_clear_goal(history) -> bool:
    """True if user stated a clear goal recently (intent lock)"""
    if not history:
        return False
    goal_keywords = ANALYSIS_CONFIG["goal_indicators"]
    window = THRESHOLDS["recent_history_window"]
    recent_user_msgs = [
        m.get("content", "").lower()
        for m in history[-window:]
        if m.get("role") == "user"
    ]
    if any(contains_nonnegated_keyword(msg, goal_keywords) for msg in recent_user_msgs):
        return True

    # catch goal phrasing like "want to buy a car"
    return any(_GOAL_VERB_PATTERN.search(msg) for msg in recent_user_msgs)

def flatten_keywords(keywords):
    """Flatten nested keyword groups"""
    if not keywords:
        return []
    if isinstance(keywords, list):
        return keywords
    if isinstance(keywords, dict):
        out = []
        for v in keywords.values():
            out.extend(flatten_keywords(v))
        return out
    return []

def classify_intent_level(history, user_message="", signal_keywords=None) -> str:
    """Classify intent as low, medium, or high"""
    if signal_keywords is None:
        signal_keywords = SIGNALS

    if has_user_stated_clear_goal(history):
        return "high"

    if not (user_message or history):
        return "medium"

    recent_text = (user_message + " " + extract_recent_user_text(history, 2)).lower()

    # check categories in configured priority order
    priority = signal_keywords.get(
        "signal_priority", ["high_intent", "low_intent"]
    ) or ["high_intent", "low_intent"]

    HIGH_INTENT_CATS = {
        "high_intent",
        "commitment",
        "demand_directness",
        "impatience",
        "urgency",
        "price_sensitivity",
    }
    LOW_INTENT_CATS = {"low_intent"}

    for cat in priority:
        if cat not in signal_keywords:
            continue
        keywords = flatten_keywords(signal_keywords.get(cat))
        if not keywords:
            continue
        if contains_nonnegated_keyword(recent_text, keywords):
            if cat in HIGH_INTENT_CATS:
                return "high"
            if cat in LOW_INTENT_CATS:
                return "low"

    # fallback if nothing matched in prioritised pass
    if contains_nonnegated_keyword(
        recent_text, flatten_keywords(signal_keywords.get("low_intent", []))
    ):
        return "low"
    if contains_nonnegated_keyword(
        recent_text, flatten_keywords(signal_keywords.get("high_intent", []))
    ):
        return "high"
    return "medium"

def detect_guardedness(user_message: str, history: list[dict[str, str]]) -> float:
    """Guardedness score 0.0–1.0; agreement-after-answer treated as not guarded"""
    if not user_message:
        return 0.0

    msg_lower = user_message.lower().strip()
    msg_length = len(user_message.split())

    # substantive reply → bot question → "ok" = agreement, not guarded
    if msg_lower in _AGREEMENT_WORDS and len(history) >= 2:
        recent_msgs = history[-4:]
        has_substantive_user = any(
            m.get("role") == "user" and len(m.get("content", "").split()) >= 8
            for m in recent_msgs
        )
        has_bot_question = any(
            m.get("role") == "assistant" and "?" in m.get("content", "")
            for m in recent_msgs
        )
        if has_substantive_user and has_bot_question:
            return 0.0

    # single-word dismissals
    if msg_lower in _DISMISSAL_WORDS:
        return 0.9

    # agreement with elaboration = low guardedness
    split_msg = msg_lower.split()
    if split_msg and split_msg[0] in _AGREEMENT_WORDS and msg_length > 3:
        return 0.1

    # weighted scoring
    guardedness_keywords = SIGNALS.get("guardedness_keywords", {})
    score = 0.0
    for category, weight in _GUARDEDNESS_WEIGHTS.items():
        keywords = guardedness_keywords.get(category, [])
        if contains_nonnegated_keyword(msg_lower, keywords):
            score += weight

    # short reply to a long question bumps the score
    if history:
        last_bot = next(
            (
                m.get("content", "")
                for m in reversed(history)
                if m.get("role") == "assistant"
            ),
            "",
        )
        if len(last_bot.split()) > 50 and msg_length < 8:
            score *= 1.4

    return min(score, 1.0)

def analyse_state(
    history: list[dict[str, str]],
    user_message: str = "",
    signal_keywords: dict[str, Any] | None = None,
) -> ConversationState:
    """Build conversation state from the current turn"""
    if signal_keywords is None:
        signal_keywords = SIGNALS

    intent = classify_intent_level(
        history, user_message, signal_keywords=signal_keywords
    )

    # guardedness
    guardedness_level = 0.0
    if user_message:
        guardedness_level = detect_guardedness(user_message, history)
    guarded = guardedness_level > 0.4

    # decisiveness
    decisive = False
    if user_message and signal_keywords:
        has_commitment = contains_nonnegated_keyword(
            user_message.lower(), signal_keywords.get("commitment", [])
        )
        has_high_intent = contains_nonnegated_keyword(
            user_message.lower(), signal_keywords.get("high_intent", [])
        )
        decisive = (has_commitment or has_high_intent) and not guarded

    # question fatigue
    question_fatigue = False
    if history:
        recent_bot = [m["content"] for m in history[-4:] if m["role"] == "assistant"]
        question_fatigue = (
            sum(1 for msg in recent_bot if "?" in msg)
            >= THRESHOLDS["question_fatigue_threshold"]
        )

    return ConversationState(
        intent=intent,
        guarded=guarded,
        question_fatigue=question_fatigue,
        decisive=decisive,
    )

def extract_preferences(history) -> str:
    """
    Scans conversation history
    Returns comma-separated preference categories the user mentioned
    e.g "cheap, reliable, time-flexible"
    """
    if not history: # If history empty
        return ""
    
    pref_config = ANALYSIS_CONFIG.get("preference_keywords", {})
    mentioned = set()
    for msg in history:
        if msg["role"] == "user":
            text = msg["content"].lower()
            for category, keywords in pref_config.items():
                if contains_nonnegated_keyword(text, keywords):
                    mentioned.add(category)
    return ", ".join(sorted(mentioned)) if mentioned else ""

def extract_user_keywords(
    history: list[dict[str, str]], max_keywords: int = MAX_USER_KEYWORDS
) -> list[str]:
    """Extract the user's key terms (nouns/descriptors) for lexical entrainment"""
    keywords = []
    for msg in history:
        if msg["role"] == "user":
            for word in msg["content"].lower().split():
                cleaned = word.strip(".,!?;:'\"")
                if (
                    cleaned
                    and len(cleaned) > 2
                    and cleaned not in STOP_WORDS
                    and cleaned not in keywords
                ):
                    keywords.append(cleaned)
    return keywords[-max_keywords:]

def detect_topic_drift(user_message: str, stage: str) -> str:
    """Return a course-correction directive if the user drifted from the stage goal, else ''."""
    drift_cfg = ANALYSIS_CONFIG.get("drift_detection", {})
    if stage not in drift_cfg.get("stages", []):
        return ""
    if len(user_message.split()) < drift_cfg.get("min_message_words", 8):
        return ""

    anchor_key = "doubt_keywords" if stage == "logical" else "stakes_keywords"
    anchors = ANALYSIS_CONFIG.get("advancement", {}).get(stage, {}).get(anchor_key, [])
    if not anchors or contains_nonnegated_keyword(user_message.lower(), anchors):
        return ""

    redirect = drift_cfg.get("redirect_phrase", {}).get(stage, "")
    if not redirect:
        return ""

    return (
        f"\nSTAGE FOCUS: The user's message may not engage with the current discovery goal. "
        f"If so, briefly acknowledge what they said and naturally guide back to {redirect}.\n"
    )

def is_literal_question(user_message) -> bool:
    """True if the user is asking for information (not rhetorical)"""
    if not user_message:
        return False
    msg = user_message.lower().strip()
    patterns = ANALYSIS_CONFIG.get("question_patterns", {})
    starters = patterns.get("starters", [])
    rhetorical = patterns.get("rhetorical_markers", [])

    # starts with interrogative word or ends with "?"
    is_question = any(msg.startswith(w) for w in starters) or msg.endswith("?")

    # normalize punctuation so "that's obvious, right?" matches rhetorical marker
    msg_norm = re.sub(r"[^\w\s']", " ", msg)
    msg_norm = re.sub(r"\s+", " ", msg_norm).strip()

    def _norm(s: str) -> str:
        s2 = re.sub(r"[^\w\s']", " ", s.lower())
        return re.sub(r"\s+", " ", s2).strip()

    is_rhetorical = any(_norm(rmk) and _norm(rmk) in msg_norm for rmk in rhetorical)

    return is_question and not is_rhetorical

def commitment_or_walkaway(
    history: list[dict[str, str]], user_msg: str, turns: int
) -> bool:
    """True when user commits or walks away (objection stage exit)"""
    return contains_nonnegated_keyword(
        user_msg.lower(), SIGNALS.get("commitment", [])
    ) or contains_nonnegated_keyword(user_msg.lower(), SIGNALS.get("walking", []))

def detect_ack_context(
    user_message: str,
    history: list[dict[str, str]],
    state: ConversationState,
) -> str:
    """Choose ack level: 'full' | 'light' | 'none'"""
    if not user_message:
        return "none"

    msg_lower = user_message.lower()
    word_count = len(user_message.split())
    emotional_keywords = SIGNALS.get("emotional_disclosure", [])
    recent_user = [
        m["content"].lower() for m in history[-4:] if m["role"] == "user"
    ] if history else []
    recent_emotional_context = any(
        contains_nonnegated_keyword(m, emotional_keywords) for m in recent_user
    )

    if msg_lower in _TERSE_FOLLOW_UPS:
        return "none"

    # Don't re-validate dead-end follow-ups after an emotional moment.
    if recent_emotional_context and word_count <= 3 and not is_literal_question(user_message):
        return "none"

    # skip ack for direct info requests
    direct_requests = SIGNALS.get("direct_info_requests", [])
    if contains_nonnegated_keyword(msg_lower, direct_requests):
        return "none"

    # skip ack for low-engagement filler
    low_intent = SIGNALS.get("low_intent", [])
    if (
        contains_nonnegated_keyword(msg_lower, low_intent)
        and word_count < 6
    ):
        return "none"

    # full ack when user shared something emotional
    if contains_nonnegated_keyword(msg_lower, emotional_keywords):
        return "full"

    # light ack if recent emotional context + literal question now
    if recent_emotional_context and is_literal_question(user_message):
        return "light"

    # light ack for guarded users
    if state.guarded:
        if word_count <= THRESHOLDS.get("short_message_limit", 4):
            return "none"
        return "light"

    # short factual question, skip it
    if is_literal_question(user_message) and word_count < 8:
        return "none"

    return "none"

def user_demands_directness(history, user_message) -> bool:
    """Detects frustration or demand for a straight answer"""
    demand_keywords = SIGNALS.get("demand_directness", [])
    msg_lower = user_message.lower()

    if contains_nonnegated_keyword(msg_lower, demand_keywords):
        return True

    if history and len(history) >= 2 and "i said" in msg_lower:
        return True

    return False

# get_objection_data removed (unused); use objection.py:classify_objection() directly where needed

def extract_recent_user_text(history, max_messages=None) -> str:
    """Combined lowercase text of the N most recent user messages"""
    if max_messages is None:
        max_messages = THRESHOLDS["recent_text_messages"]
    if not history:
        return ""
    recent = history[-(max_messages * 2) :]
    user_msgs = [m["content"].lower() for m in recent if m["role"] == "user"]
    return " ".join(user_msgs[-max_messages:])
