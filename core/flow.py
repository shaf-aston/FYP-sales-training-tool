"""LAYER 1: Stage-Gating (FSM) - Enforces conversation pacing via state machine.

Manages conversation stages (INTENT -> LOGICAL -> EMOTIONAL -> PITCH -> OBJECTION -> OUTCOME).
Prevents stage progression until user signals meet advancement thresholds:
- To leave INTENT: Need 2+ problem statements (user_has_clear_intent)
- To reach PITCH: Need emotional commitment signals
- To reach OBJECTION: Need buyer objection, not smokescreen

Uses signal detections from analysis.py to make advancement decisions.
Execution order: 2nd (after signal detection in chatbot.chat()).
Conceptually: Outermost defensive layer (prevents bad state progressions earliest).
See three_layer_architecture.puml for full defense-in-depth diagram.
"""

from copy import deepcopy
from typing import Any, Optional

from .analysis import (
    classify_intent_level,
    commitment_or_walkaway,
    user_demands_directness,
)
from .content import generate_stage_prompt
from .loader import QuickMatcher, load_analysis_config, load_signals
from .utils import Stage, Strategy, contains_nonnegated_keyword

SIGNALS = load_signals()
ANALYSIS_CONFIG = load_analysis_config()


def _get_signal_terms(*keys: str) -> list[str]:
    """Return the first configured signal list for the given keys."""
    for key in keys:
        values = SIGNALS.get(key)
        if isinstance(values, list):
            return values
    return []


USER_CONSULTATIVE_SIGNALS = _get_signal_terms(
    "user_consultative_signals",
    "user_consultativeSIGNALS",
)
USER_TRANSACTIONAL_SIGNALS = _get_signal_terms(
    "user_transactional_signals",
    "user_transactionalSIGNALS",
)

COMMON_TRANSITIONS = {
    Stage.PITCH: {"next": Stage.OBJECTION, "advance_on": "objection_only"},
    Stage.OBJECTION: {"next": Stage.OUTCOME, "advance_on": "commitment_or_walkaway"},
    Stage.OUTCOME: {"next": None, "advance_on": None},
}

TRANSACTIONAL_TRANSITIONS = {
    Stage.PITCH: {"next": Stage.NEGOTIATION, "advance_on": "terms_requested_or_resolved"},
    Stage.NEGOTIATION: {"next": Stage.OBJECTION, "advance_on": "objection_only"},
    Stage.OBJECTION: {"next": Stage.OUTCOME, "advance_on": "commitment_or_walkaway"},
    Stage.OUTCOME: {"next": None, "advance_on": None},
}

FLOWS: dict[str | Strategy, dict[str, Any]] = {
    Strategy.INTENT: {
        "stages": [Stage.INTENT],
        "transitions": {
            Stage.INTENT: {
                "next": None,
                "advance_on": None,
            }
        },
    },
    Strategy.CONSULTATIVE: {
        "stages": [
            Stage.INTENT,
            Stage.LOGICAL,
            Stage.EMOTIONAL,
            Stage.PITCH,
            Stage.OBJECTION,
            Stage.OUTCOME,
        ],
        "transitions": {
            Stage.INTENT: {
                "next": Stage.LOGICAL,
                "advance_on": "user_has_clear_intent",
            },
            Stage.LOGICAL: {
                "next": Stage.EMOTIONAL,
                "advance_on": "user_shows_doubt",
            },
            Stage.EMOTIONAL: {
                "next": Stage.PITCH,
                "advance_on": "user_expressed_stakes",
            },
            **deepcopy(COMMON_TRANSITIONS),
        },
    },
    Strategy.TRANSACTIONAL: {
        "stages": [Stage.INTENT, Stage.PITCH, Stage.NEGOTIATION, Stage.OBJECTION, Stage.OUTCOME],
        "transitions": {
            Stage.INTENT: {"next": Stage.PITCH, "advance_on": "user_has_clear_intent"},
            **deepcopy(TRANSACTIONAL_TRANSITIONS),
        },
    },
}

# Phrases signalling clear buying intent, checked before consulting signals.yaml
# NOTE: "price" and "budget" are NOT intent signals; they indicate transactional preference.
# Actual intent requires BOTH a specific need/problem statement AND transactional signals.
EXPLICIT_INTENT_PHRASES = [
    "looking for",
    "help with",
    "interested in",
    "problem",
    "buy",
    "purchase",
    "struggling",
    "have to",
    "ready to buy",
    "looking to buy",
]

# Safety valve: auto-advance from intent after this many turns if no signal detected.
# Calibrated against test sessions (intent signals typically appear between turns 2-5).
INTENT_MAX_TURNS = 6


def _user_signals_specific_budget_or_product(user_message: str) -> bool:
    """Return True when the user already sounds ready for a direct path."""
    user_text = (user_message or "").lower()
    if not user_text:
        return False

    direct_transactional_terms = []
    direct_transactional_terms.extend(SIGNALS.get("demand_directness", []))
    direct_transactional_terms.extend(SIGNALS.get("direct_info_requests", []))
    direct_transactional_terms.extend(USER_TRANSACTIONAL_SIGNALS)
    direct_transactional_terms.extend(
        ANALYSIS_CONFIG.get("preference_keywords", {}).get("budget", [])
    )

    if contains_nonnegated_keyword(user_text, direct_transactional_terms):
        return True

    matched_product, confidence = QuickMatcher.match_product(user_message)
    return bool(matched_product and confidence >= 0.9)


def _user_has_clear_intent(
    history: list[dict[str, str]], user_msg: str, turns: int, turn_state=None
) -> bool:
    """Return True when the user shows intent or the turn cap is reached.

    NOTE: Budget/price mention alone is not intent; it is a transactional signal.
    Clear intent requires explicit problem or need statement.
    """
    if user_msg and contains_nonnegated_keyword(
        user_msg.lower(), EXPLICIT_INTENT_PHRASES
    ):
        return True

    if turn_state is not None:
        # High intent must come from explicit intent phrases, not just budget mention
        return turn_state.intent == "high" or turns >= INTENT_MAX_TURNS

    intent_level = classify_intent_level(history, user_msg, signal_keywords=SIGNALS)
    # Only advance on "high" intent if it's not just a budget/price mention
    if intent_level == "high":
        user_text = (user_msg or "").lower()
        # If user only mentioned budget/price without a problem statement, don't advance
        # Force confirmation of actual needs first
        has_budget_only = (
            contains_nonnegated_keyword(user_text, ["budget", "price", "cost", "afford"])
            and not contains_nonnegated_keyword(user_text, EXPLICIT_INTENT_PHRASES)
        )
        if has_budget_only:
            return False
        return True

    return turns >= INTENT_MAX_TURNS


def _check_advancement_condition(
    history: list[dict[str, str]],
    user_msg: str,
    turns: int,
    stage_name: Stage,
    min_turns: int = 2,
    turn_state=None,
) -> bool:
    """Return True when the signal appears or the stage turn cap is reached."""
    if turns < min_turns:
        return False

    stage_config = ANALYSIS_CONFIG.get("advancement", {}).get(stage_name, {})
    max_turns = stage_config.get("max_turns", 10)

    # Use precomputed flags when available.
    if turn_state is not None:
        state_signal_attribute = {
            Stage.LOGICAL: "doubt",
            Stage.EMOTIONAL: "stakes",
        }.get(stage_name)
        if state_signal_attribute is not None:
            return getattr(turn_state, state_signal_attribute, False) or turns >= max_turns

    keyword_key = {
        Stage.LOGICAL: "doubt_keywords",
        Stage.EMOTIONAL: "stakes_keywords",
    }.get(stage_name, f"{stage_name}_keywords")
    keywords = stage_config.get(keyword_key, [])

    # Only inspect messages from the current stage window.
    user_msgs = [m["content"].lower() for m in history if m.get("role") == "user"]
    current_msg = (user_msg or "").lower().strip()
    if current_msg and (not user_msgs or user_msgs[-1] != current_msg):
        user_msgs.append(current_msg)

    # Allow direct tests that pass more turns than available messages.
    available_turns = min(turns, len(user_msgs))
    current_stage_window = user_msgs[-available_turns:] if available_turns > 0 else []
    recent_text = " ".join(current_stage_window)
    has_signal = contains_nonnegated_keyword(recent_text, keywords)

    # Auto-advance once the stage limit is reached.
    return has_signal or turns >= max_turns


def _user_shows_doubt(
    history: list[dict[str, str]], user_msg: str, turns: int, turn_state=None
) -> bool:
    """Return True when the user shows doubt or the limit is reached."""
    return _check_advancement_condition(
        history, user_msg, turns, Stage.LOGICAL, min_turns=2, turn_state=turn_state
    )


def _user_expressed_stakes(
    history: list[dict[str, str]], user_msg: str, turns: int, turn_state=None
) -> bool:
    """Return True when the user shows stakes or the limit is reached."""
    return _check_advancement_condition(
        history, user_msg, turns, Stage.EMOTIONAL, min_turns=3, turn_state=turn_state
    )


def _commitment_or_objection(
    history: list[dict[str, str]], user_msg: str, turns: int, turn_state=None
) -> bool:
    """Return True when the user commits or objects."""
    msg_lower = user_msg.lower()
    return contains_nonnegated_keyword(
        msg_lower, SIGNALS.get("commitment", [])
    ) or contains_nonnegated_keyword(msg_lower, SIGNALS.get("objection", []))


def _objection_only(
    history: list[dict[str, str]], user_msg: str, turns: int, turn_state=None
) -> bool:
    """Return True when the user raises a genuine objection."""
    return contains_nonnegated_keyword(user_msg.lower(), SIGNALS.get("objection", []))


def _terms_requested_or_resolved(
    history: list[dict[str, str]], user_msg: str, turns: int, turn_state=None
) -> bool:
    """Return True when transactional terms discussion is underway."""
    if turn_state is not None and getattr(turn_state, "terms", False):
        return True

    if _user_signals_specific_budget_or_product(user_msg):
        return True

    msg_lower = user_msg.lower()
    if contains_nonnegated_keyword(msg_lower, SIGNALS.get("direct_info_requests", [])):
        return True
    if contains_nonnegated_keyword(msg_lower, SIGNALS.get("demand_directness", [])):
        return True
    if turn_state is not None and getattr(turn_state, "decisive", False):
        return True
    return False

# commitment_or_walkaway moved to analysis.py to avoid circular imports


ADVANCEMENT_RULES = {
    "user_has_clear_intent": _user_has_clear_intent,
    "user_shows_doubt": _user_shows_doubt,
    "user_expressed_stakes": _user_expressed_stakes,
    "terms_requested_or_resolved": _terms_requested_or_resolved,
    "commitment_or_objection": _commitment_or_objection,
    "objection_only": _objection_only,
    "commitment_or_walkaway": commitment_or_walkaway,
}


def _check_priority_overrides(
    flow_type, flow_config, current_stage, user_message, history
) -> Optional[str]:
    """Return an override stage for high-priority signals, if any."""
    transition = flow_config["transitions"].get(current_stage)
    if not transition:
        return None

    has_pitch_stage = Stage.PITCH in flow_config["stages"]
    msg_lower = user_message.lower()
    pitch_is_ahead = False
    if has_pitch_stage:
        stages = flow_config["stages"]
        pitch_idx = stages.index(Stage.PITCH)
        current_idx = stages.index(current_stage)
        pitch_is_ahead = current_idx < pitch_idx

    # Let commitment jump to pitch from EMOTIONAL stage (skip objection handling if ready).
    # Do NOT apply from LOGICAL - must build emotional context first.
    if has_pitch_stage and current_stage == Stage.EMOTIONAL:
        commitment_terms = SIGNALS.get("commitment", []) + ["sign up"]
        if contains_nonnegated_keyword(msg_lower, commitment_terms):
            return Stage.PITCH

    if has_pitch_stage and current_stage in (Stage.PITCH, Stage.NEGOTIATION):
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("commitment", [])):
            return Stage.OUTCOME
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("objection", [])):
            return Stage.OBJECTION

    # Transactional flows can jump to pitch on direct requests.
    if flow_type == Strategy.TRANSACTIONAL and pitch_is_ahead:
        if user_demands_directness(history, user_message):
            return Stage.PITCH
        direct_requests = SIGNALS.get("direct_info_requests", [])
        if contains_nonnegated_keyword(msg_lower, direct_requests):
            return Stage.PITCH

    # Impatience can skip to the configured stage.
    if transition.get("urgency_skip_to"):
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("impatience", [])):
            return transition["urgency_skip_to"]

    return None


def _detect_and_switch_strategy(flow_engine, user_message: str) -> bool:
    """Switch strategy from INTENT when the user's preference is clear."""
    user_text = (user_message or "").lower()
    has_cons_user = contains_nonnegated_keyword(
        user_text, USER_CONSULTATIVE_SIGNALS
    )
    has_trans_user = contains_nonnegated_keyword(
        user_text, USER_TRANSACTIONAL_SIGNALS
    )

    if has_cons_user:
        flow_engine.switch_strategy(Strategy.CONSULTATIVE)
        return True
    if has_trans_user or _user_signals_specific_budget_or_product(user_message):
        flow_engine.switch_strategy(Strategy.TRANSACTIONAL)
        return True

    from .constants import MIN_TURNS_BEFORE_ADVANCE
    if flow_engine.stage_turn_count >= MIN_TURNS_BEFORE_ADVANCE:
        flow_engine.switch_strategy(
            _default_strategy_after_intent_probe(flow_engine, user_message)
        )
        return True
    return False


def _default_strategy_after_intent_probe(flow_engine, user_message: str) -> str:
    """Pick a fallback strategy after the probing window ends."""
    user_text = (user_message or "").lower()
    if _user_signals_specific_budget_or_product(user_message):
        return Strategy.TRANSACTIONAL

    has_directness_demand = contains_nonnegated_keyword(
        user_text, SIGNALS.get("demand_directness", [])
    ) or contains_nonnegated_keyword(
        user_text, SIGNALS.get("direct_info_requests", [])
    )
    intent_level = classify_intent_level(
        flow_engine.conversation_history,
        user_message,
        signal_keywords=SIGNALS,
    )

    if has_directness_demand or intent_level == "high":
        return Strategy.TRANSACTIONAL
    return Strategy.CONSULTATIVE


class SalesFlowEngine:
    """FSM for stage progression, turn tracking, and strategy switching."""

    def __init__(self, flow_type: str, product_context: str) -> None:
        """Start a flow engine at the first stage of the chosen strategy."""
        if flow_type not in FLOWS:
            raise ValueError(f"Invalid flow_type: {flow_type}")
        self.initial_flow_type = flow_type  # Track initial strategy for rewind
        self.flow_config = FLOWS[flow_type]
        self.flow_type = flow_type
        self.product_context = product_context
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []

    @property
    def user_turn_count(self) -> int:
        return sum(1 for m in self.conversation_history if m.get("role") == "user")

    @property
    def _strategy_for_prompts(self):
        """Return the strategy used when building prompts."""
        if self.flow_type in (Strategy.CONSULTATIVE, Strategy.TRANSACTIONAL):
            return self.flow_type
        return Strategy.CONSULTATIVE

    def get_current_prompt(
        self,
        user_message: str = "",
        objection_data: dict | None = None,
        turn_state=None,
        include_history: bool = True,
    ) -> str:
        """Generate the system prompt for the current stage."""
        return generate_stage_prompt(
            strategy=self._strategy_for_prompts,
            stage=self.current_stage,
            product_context=self.product_context,
            history=self.conversation_history,
            user_message=user_message,
            objection_data=objection_data,
            turn_state=turn_state,
            include_history=include_history,
        )

    def should_advance(self, user_message: str, turn_state=None) -> Optional[str]:
        """Return the next stage when the FSM should advance, otherwise None."""
        override = _check_priority_overrides(
            self.flow_type,
            self.flow_config,
            self.current_stage,
            user_message,
            self.conversation_history,
        )
        if override:
            return override

        transition = self.flow_config["transitions"].get(self.current_stage)
        if not transition:
            return None
        rule_name = transition.get("advance_on")
        if rule_name and rule_name in ADVANCEMENT_RULES:
            if ADVANCEMENT_RULES[rule_name](
                self.conversation_history,
                user_message,
                self.stage_turn_count,
                turn_state=turn_state,
            ):
                return transition.get("next")
        return None

    def evaluate_strategy_switch(self, user_message: str) -> bool:
        """Return True when INTENT should switch to another strategy."""
        if self.flow_type != Strategy.INTENT:
            return False
        return _detect_and_switch_strategy(self, user_message)

    def advance(self, target_stage: Optional[str] = None) -> None:
        """Advance to a target stage or the next stage in sequence."""
        stages = self.flow_config["stages"]
        if target_stage is not None:
            if target_stage not in stages:
                raise ValueError(
                    f"Target stage '{target_stage}' not in current flow '{self.flow_type}'."
                )
            self.current_stage = target_stage
            self.stage_turn_count = 0
            return

        idx = stages.index(self.current_stage)
        if idx < len(stages) - 1:
            self.current_stage = stages[idx + 1]
            self.stage_turn_count = 0

    def add_turn(self, user_message: str, bot_response: str) -> None:
        """Append a turn to history and increment the stage counter."""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        self.stage_turn_count += 1

    def switch_strategy(self, new_strategy: str) -> bool:
        """Switch to a new strategy and restart the new flow at INTENT."""
        if new_strategy not in FLOWS:
            return False
        self.flow_type = new_strategy
        self.flow_config = FLOWS[new_strategy]

        # Always restart at INTENT so the new strategy establishes intent first.
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        return True

    def reset_to_initial(self) -> None:
        """Reset the FSM to its initial flow and clear history."""
        self.flow_type = self.initial_flow_type
        self.flow_config = FLOWS[self.initial_flow_type]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []

    def get_summary(self) -> dict[str, Any]:
        """Return the current FSM state as a dict."""
        return {
            "flow_type": self.flow_type,
            "display_strategy": self._strategy_for_prompts,
            "current_stage": self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turns": len(self.conversation_history) // 2,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore the FSM from a saved state dict."""
        flow_type = state["flow_type"]
        if flow_type not in FLOWS:
            raise ValueError(f"Invalid flow_type in saved state: {flow_type}")

        self.flow_type = flow_type
        self.flow_config = FLOWS[self.flow_type]
        self.current_stage = state["current_stage"]
        if self.current_stage not in self.flow_config["stages"]:
            raise ValueError(
                f"Invalid current_stage '{self.current_stage}' for flow '{self.flow_type}'"
            )
        self.stage_turn_count = state.get("stage_turn_count", 0)
        self.conversation_history = state.get("conversation_history", [])
        self.initial_flow_type = state.get("initial_flow_type", self.flow_type)
        if self.initial_flow_type not in FLOWS:
            raise ValueError(
                f"Invalid initial_flow_type in saved state: {self.initial_flow_type}"
            )
