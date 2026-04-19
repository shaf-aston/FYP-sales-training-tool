"""FSM transitions and advancement rules for conversation flow"""

from typing import Any, Optional

from .analysis import (
    classify_intent_level,
    commitment_or_walkaway,
    user_demands_directness,
)
from .content import generate_stage_prompt
from .loader import load_analysis_config, load_signals
from .utils import Stage, Strategy, contains_nonnegated_keyword

SIGNALS = load_signals()
ANALYSIS_CONFIG = load_analysis_config()

COMMON_TRANSITIONS = {
    Stage.PITCH: {"next": Stage.OBJECTION, "advance_on": "commitment_or_objection"},
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
                "urgency_skip_to": Stage.PITCH,
            },
            Stage.EMOTIONAL: {
                "next": Stage.PITCH,
                "advance_on": "user_expressed_stakes",
            },
            **COMMON_TRANSITIONS,
        },
    },
    Strategy.TRANSACTIONAL: {
        "stages": [Stage.INTENT, Stage.PITCH, Stage.OBJECTION, Stage.OUTCOME],
        "transitions": {
            Stage.INTENT: {"next": Stage.PITCH, "advance_on": "user_has_clear_intent"},
            **COMMON_TRANSITIONS,
        },
    },
}

# Phrases signalling clear buying intent, checked before consulting signals.yaml
EXPLICIT_INTENT_PHRASES = [
    "looking for",
    "help with",
    "interested in",
    "price",
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

def _user_has_clear_intent(
    history: list[dict[str, str]], user_msg: str, turns: int
) -> bool:
    """Return True if user signals buying intent or safety valve (max turns) triggers.

    Checks explicit phrases first, then NLU classification. Safety valve prevents
    getting stuck in intent stage with hard-to-read prospects.
    """
    if user_msg and contains_nonnegated_keyword(
        user_msg.lower(), EXPLICIT_INTENT_PHRASES
    ):
        return True

    intent_level = classify_intent_level(history, user_msg, signal_keywords=SIGNALS)
    if intent_level == "high":
        return True

    return turns >= INTENT_MAX_TURNS

def _check_advancement_condition(
    history: list[dict[str, str]],
    user_msg: str,
    turns: int,
    stage_name: str,
    min_turns: int = 2,
) -> bool:
    """Return True if advancement signal detected or safety valve (max_turns) triggers.

    Enforces min_turns guard to ensure adequate rapport before advancing.
    Tolerant when turns exceed available history (supports direct test calls).
    """
    if turns < min_turns:
        return False

    stage_config = ANALYSIS_CONFIG.get("advancement", {}).get(stage_name, {})
    keyword_key = {"logical": "doubt_keywords", "emotional": "stakes_keywords"}.get(
        stage_name, f"{stage_name}_keywords"
    )

    keywords = stage_config.get(keyword_key, [])
    max_turns = stage_config.get("max_turns", 10)

    # Slice to current-stage messages only (ignore earlier stages if switched).
    user_msgs = [m["content"].lower() for m in history if m.get("role") == "user"]

    # Tolerant when turns exceed available messages. Supports direct test calls
    # where helper is used without full engine context.
    available_turns = min(turns, len(user_msgs))
    current_stage_window = user_msgs[-available_turns:] if available_turns > 0 else []
    recent_text = " ".join(current_stage_window)
    has_signal = contains_nonnegated_keyword(recent_text, keywords)

    # Safety valve: auto-advance when max_turns exceeded (resistant prospect).
    return has_signal or turns >= max_turns

def _user_shows_doubt(history: list[dict[str, str]], user_msg: str, turns: int) -> bool:
    """True when user shows doubt/pain or safety valve triggers"""
    return _check_advancement_condition(
        history, user_msg, turns, "logical", min_turns=2
    )

def _user_expressed_stakes(
    history: list[dict[str, str]], user_msg: str, turns: int
) -> bool:
    """True when user shares emotional stakes or safety valve fires"""
    # emotional needs more rapport before advancing
    return _check_advancement_condition(
        history, user_msg, turns, "emotional", min_turns=3
    )

def _commitment_or_objection(
    history: list[dict[str, str]], user_msg: str, turns: int
) -> bool:
    """True when user commits or objects; short messages treated as fillers"""
    # filters conversational fillers like "yeah" or "ok sure"
    if len(user_msg.split()) < 3:
        return False
    return contains_nonnegated_keyword(
        user_msg, SIGNALS["commitment"]
    ) or contains_nonnegated_keyword(user_msg, SIGNALS["objection"])

# commitment_or_walkaway moved to analysis.py to avoid circular imports

ADVANCEMENT_RULES = {
    "user_has_clear_intent": _user_has_clear_intent,
    "user_shows_doubt": _user_shows_doubt,
    "user_expressed_stakes": _user_expressed_stakes,
    "commitment_or_objection": _commitment_or_objection,
    "commitment_or_walkaway": commitment_or_walkaway,
}

def _check_priority_overrides(flow_config, current_stage, user_message, history) -> Optional[str]:
    """Check for high-priority signals that jump the FSM immediately."""
    transition = flow_config["transitions"].get(current_stage)
    if not transition:
        return None

    has_pitch_stage = Stage.PITCH in flow_config["stages"]
    msg_lower = user_message.lower()

    # Explicit commitment during discovery
    if has_pitch_stage and current_stage in (Stage.LOGICAL, Stage.EMOTIONAL):
        commitment_terms = SIGNALS.get("commitment", []) + ["sign up"]
        if contains_nonnegated_keyword(msg_lower, commitment_terms):
            return Stage.PITCH

    # User demands directness or direct info request
    if has_pitch_stage:
        if user_demands_directness(history, user_message):
            return Stage.PITCH
        direct_requests = SIGNALS.get("direct_info_requests", [])
        if contains_nonnegated_keyword(msg_lower, direct_requests):
            return Stage.PITCH

    # Impatience override (usually skips to a specific transition stage, e.g. pitch)
    if transition.get("urgency_skip_to"):
        if contains_nonnegated_keyword(msg_lower, SIGNALS.get("impatience", [])):
            return transition["urgency_skip_to"]

    return None

class SalesFlowEngine:
    """Finite state machine managing stage progression and prompt context.

    Tracks current stage, turn count per stage, and conversation history.
    Provides advancement detection and strategy switching for mid-session pivots.
    """

    def __init__(self, flow_type: str, product_context: str) -> None:
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
        """Number of user messages in conversation history"""
        return sum(1 for m in self.conversation_history if m.get("role") == "user")

    @property
    def _strategy_for_prompts(self):
        """Map flow_type to strategy used by content.py prompts.

        Intent flow uses consultative style (open discovery) not transactional.
        """
        if self.flow_type in (Strategy.CONSULTATIVE, Strategy.TRANSACTIONAL):
            return self.flow_type
        return Strategy.CONSULTATIVE

    def get_current_prompt(
        self, user_message: str = "", objection_data: dict | None = None, pre_state=None
    ) -> str:
        """Generate system prompt for current stage"""
        return generate_stage_prompt(
            strategy=self._strategy_for_prompts,
            stage=self.current_stage,
            product_context=self.product_context,
            history=self.conversation_history,
            user_message=user_message,
            objection_data=objection_data,
            pre_state=pre_state,
        )

    def get_advance_target(self, user_message: str) -> Optional[str]:
        """Determine next stage or None if staying in current stage.

        Priority order: high-priority overrides (commitments, demands), then standard advancement rule.
        """
        transition = self.flow_config["transitions"].get(self.current_stage)
        if not transition:
            return None

        # 1. Check declarative high-priority override paths
        override_target = _check_priority_overrides(
            self.flow_config, self.current_stage, user_message, self.conversation_history
        )
        if override_target:
            return override_target

        # 2. Check standard FSM transition rules
        rule_name = transition.get("advance_on")
        if rule_name and rule_name in ADVANCEMENT_RULES:
            if ADVANCEMENT_RULES[rule_name](
                self.conversation_history, user_message, self.stage_turn_count
            ):
                return transition.get("next")

        return None

    def advance(self, target_stage: Optional[str] = None) -> None:
        """Advance to target_stage (jump) or next sequential stage"""
        stages = self.flow_config["stages"]
        if target_stage and target_stage in stages:
            self.current_stage = target_stage
            self.stage_turn_count = 0
        else:
            idx = stages.index(self.current_stage)
            if idx < len(stages) - 1:
                self.current_stage = stages[idx + 1]
                self.stage_turn_count = 0

    def add_turn(self, user_message: str, bot_response: str) -> None:
        """Append user and assistant messages to history and increment stage turn counter."""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        self.stage_turn_count += 1

    def switch_strategy(self, new_strategy: str) -> bool:
        """Switch FSM to a different strategy and reset to first stage.
        Return False if strategy is invalid.
        """
        if new_strategy not in FLOWS:
            return False
        self.flow_type = new_strategy
        self.flow_config = FLOWS[new_strategy]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        return True

    def reset_to_initial(self) -> None:
        """Reset FSM to initial flow type and clear conversation history.
        Used to rewind after mid-session strategy switches.
        """
        self.flow_type = self.initial_flow_type
        self.flow_config = FLOWS[self.initial_flow_type]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []

    def get_summary(self) -> dict[str, Any]:
        """Return current FSM state as a dict"""
        return {
            "flow_type": self.flow_type,
            "display_strategy": self._strategy_for_prompts,
            "current_stage": self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turns": len(self.conversation_history) // 2,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore FSM from serialized state dict (e.g., from session persistence)."""
        self.flow_type = state["flow_type"]
        self.current_stage = state["current_stage"]
        self.stage_turn_count = state["stage_turn_count"]
        self.conversation_history = state.get("conversation_history", [])
        self.initial_flow_type = state.get("initial_flow_type", self.flow_type)
        if self.flow_type in FLOWS:
            self.flow_config = FLOWS[self.flow_type]
