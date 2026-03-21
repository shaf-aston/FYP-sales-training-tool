"""Finite State Machine for sales flow — state transitions and advancement logic."""

from typing import Any, Optional

from .content import generate_stage_prompt, SIGNALS
from .analysis import (
    text_contains_any_keyword,
    classify_intent_level,
    user_demands_directness,
    _extract_recent_user_text,
    commitment_or_walkaway,
)
from .loader import load_analysis_config
from .utils import Strategy, Stage

_ANALYSIS_CONFIG = load_analysis_config()

# Shared transitions used across multiple strategies (identical regardless of strategy)
_COMMON_TRANSITIONS = {
    Stage.PITCH: {
        "next": Stage.OBJECTION,
        "advance_on": "commitment_or_objection"
    },
    Stage.OBJECTION: {
        "next": None,
        "advance_on": "commitment_or_walkaway"
    }
}

FLOWS = {
    Strategy.INTENT: {
        "stages": [Stage.INTENT],
        "transitions": {
            Stage.INTENT: {
                "next": None,
                "advance_on": None,
            }
        }
    },

    Strategy.CONSULTATIVE: {
        "stages": [Stage.INTENT, Stage.LOGICAL, Stage.EMOTIONAL, Stage.PITCH, Stage.OBJECTION],
        "transitions": {
            Stage.INTENT: {
                "next": Stage.LOGICAL,
                "advance_on": "user_has_clear_intent"
            },
            Stage.LOGICAL: {
                "next": Stage.EMOTIONAL,
                "advance_on": "user_shows_doubt",
                "urgency_skip_to": Stage.PITCH,
            },
            Stage.EMOTIONAL: {
                "next": Stage.PITCH,
                "advance_on": "user_expressed_stakes"
            },
            **_COMMON_TRANSITIONS
        }
    },

    Strategy.TRANSACTIONAL: {
        "stages": [Stage.INTENT, Stage.PITCH, Stage.OBJECTION],
        "transitions": {
            Stage.INTENT: {
                "next": Stage.PITCH,
                "advance_on": "user_has_clear_intent"
            },
            **_COMMON_TRANSITIONS
        }
    }
}


# --- Advancement Rules (Pure Functions) ---

def user_has_clear_intent(history: list[dict[str, str]], user_msg: str, turns: int) -> bool:
    """True when buying signals, intent keywords, or max turns reached.

    Intent stage is discovery - allow turn-based advancement since user may be reticent.
    NOTE: 'want' and 'need' are deliberately excluded - they are stopwords (analysis.py)
    and fire on generic statements ("I want to make money") that carry no buying intent.
    """
    explicit_intent_phrases = [
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
    if user_msg and text_contains_any_keyword(user_msg.lower(), explicit_intent_phrases):
        return True

    intent_level = classify_intent_level(history, user_msg, signal_keywords=SIGNALS)
    if intent_level == "high":
        return True

    # Allow turn-based advancement for intent stage only
    max_turns = 4 if intent_level == "high" else 6
    return turns >= max_turns


def _check_advancement_condition(
    history: list[dict[str, str]],
    user_msg: str,
    turns: int,
    stage_name: str,
    min_turns: int = 2,
) -> bool:
    """Generic advancement detector: check config keywords + safety valve.

    Used by stages that require signal detection before auto-advancement.
    FRAMEWORK: Must detect actual signal (doubt, stakes) or hit max_turns safety valve.
    Do NOT auto-advance on turn count alone - violates consultative framework.

    Args:
        turns: Number of turns in the CURRENT stage (stage_turn_count)
        min_turns: Minimum turns required in this stage before checking signals
    """
    if turns < min_turns:
        return False

    # Load config and keywords for this stage
    stage_config = _ANALYSIS_CONFIG.get('advancement', {}).get(stage_name, {})
    keyword_key = {
        'logical': 'doubt_keywords',
        'emotional': 'stakes_keywords'
    }.get(stage_name, f'{stage_name}_keywords')

    keywords = stage_config.get(keyword_key, [])
    max_turns = stage_config.get('max_turns', 10)

    # Check only messages from current stage window to avoid prior-stage leakage.
    user_msgs = [m["content"].lower() for m in history if m.get("role") == "user"]
    recent_stage_msgs = user_msgs[-max(turns, 0):] if turns > 0 else []
    recent_text = " ".join(recent_stage_msgs)
    has_signal = text_contains_any_keyword(recent_text, keywords)

    # Safety valve: auto-advance if max_turns exceeded (resistant prospect)
    return has_signal or turns >= max_turns


def user_shows_doubt(history: list[dict[str, str]], user_msg: str, turns: int) -> bool:
    """True when user acknowledges pain points or current approach isn't working.

    FRAMEWORK REQUIREMENT: Must detect actual doubt/problem acknowledgment.
    Safety valve: After max_turns without doubt signals, assume resistant prospect and advance.
    """
    return _check_advancement_condition(history, user_msg, turns, 'logical', min_turns=2)


def user_expressed_stakes(history: list[dict[str, str]], user_msg: str, turns: int) -> bool:
    """True when user shares emotional stakes or consequences.

    FRAMEWORK REQUIREMENT: Must detect actual emotional investment.
    Safety valve: After max_turns without stakes, assume low-emotion prospect and advance.
    """
    return _check_advancement_condition(history, user_msg, turns, 'emotional', min_turns=3)


def commitment_or_objection(history: list[dict[str, str]], user_msg: str, turns: int) -> bool:
    """True when user commits or objects. Short messages excluded (likely fillers)."""
    if len(user_msg.split()) < 3:
        return False
    return (text_contains_any_keyword(user_msg, SIGNALS["commitment"]) or
            text_contains_any_keyword(user_msg, SIGNALS["objection"]))


# commitment_or_walkaway moved to analysis.py to avoid circular imports


ADVANCEMENT_RULES = {
    "user_has_clear_intent": user_has_clear_intent,
    "user_shows_doubt": user_shows_doubt,
    "user_expressed_stakes": user_expressed_stakes,
    "commitment_or_objection": commitment_or_objection,
    "commitment_or_walkaway": commitment_or_walkaway,
}


# --- FSM Engine ---

class SalesFlowEngine:
    """FSM managing stage state, transitions, history, and prompt generation."""

    def __init__(self, flow_type: str, product_context: str) -> None:
        if flow_type not in FLOWS:
            raise ValueError(f"Invalid flow_type: {flow_type}")
        self._initial_flow_type = flow_type  # Track initial strategy for rewind
        self.flow_config = FLOWS[flow_type]
        self.flow_type = flow_type
        self.product_context = product_context
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []

    @property
    def strategy_for_prompts(self):
        """Map flow_type to the strategy key used by content.py prompts.

        'intent' discovery mode uses consultative-style prompting since it's doing
        open discovery, not product-matching.
        """
        if self.flow_type in (Strategy.CONSULTATIVE, Strategy.TRANSACTIONAL):
            return self.flow_type
        return Strategy.CONSULTATIVE

    def get_current_prompt(self, user_message: str = "") -> str:
        """Generate system prompt for current stage via content.py."""
        return generate_stage_prompt(
            strategy=self.strategy_for_prompts,
            stage=self.current_stage,
            product_context=self.product_context,
            history=self.conversation_history,
            user_message=user_message,
        )

    def get_advance_target(self, user_message: str) -> Optional[str]:
        """Return target stage name, or None to stay in current stage."""
        transition = self.flow_config["transitions"].get(self.current_stage)
        if not transition:
            return None

        has_pitch_stage = Stage.PITCH in self.flow_config["stages"]

        # Fast path: explicit commitment during discovery stages jumps to pitch.
        if has_pitch_stage and self.current_stage in (Stage.LOGICAL, Stage.EMOTIONAL):
            commitment_terms = SIGNALS.get("commitment", []) + ["sign up"]
            if text_contains_any_keyword(user_message.lower(), commitment_terms):
                return Stage.PITCH

        # Frustration/directness OR direct info request: skip to pitch immediately
        if has_pitch_stage:
            if user_demands_directness(self.conversation_history, user_message):
                return Stage.PITCH

            direct_requests = SIGNALS.get("direct_info_requests", [])
            if text_contains_any_keyword(user_message, direct_requests):
                return Stage.PITCH

        # Impatience: urgency_skip_to override (consultative only)
        if transition.get("urgency_skip_to"):
            if text_contains_any_keyword(user_message, SIGNALS.get("impatience", [])):
                return transition["urgency_skip_to"]

        rule_name = transition.get("advance_on")
        if rule_name and rule_name in ADVANCEMENT_RULES:
            if ADVANCEMENT_RULES[rule_name](self.conversation_history, user_message, self.stage_turn_count):
                return transition.get("next")

        return None

    def should_advance(self, user_message: str):
        """Compatibility API: return False (stay), True (next), or str (jump stage)."""
        transition = self.flow_config["transitions"].get(self.current_stage)
        target = self.get_advance_target(user_message)
        if not target:
            return False
        if transition and target == transition.get("next"):
            return True
        return target

    def advance(self, target_stage: Optional[str] = None) -> None:
        """Advance to target_stage (jump) or next sequential stage."""
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
        """Append user/assistant messages and increment turn counter."""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        self.stage_turn_count += 1

    def switch_strategy(self, new_strategy: str) -> bool:
        """Switch FSM to a different strategy. Resets to first stage."""
        if new_strategy not in FLOWS:
            return False
        self.flow_type = new_strategy
        self.flow_config = FLOWS[new_strategy]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        return True

    def reset_to_initial(self) -> None:
        """Reset FSM to initial flow type (before any strategy switches). Clears history."""
        self.flow_type = self._initial_flow_type
        self.flow_config = FLOWS[self._initial_flow_type]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []

    def get_summary(self) -> dict[str, Any]:
        """Return current FSM state as a dict."""
        return {
            "flow_type": self.flow_type,
            "display_strategy": self.strategy_for_prompts,
            "current_stage": self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turns": len(self.conversation_history) // 2,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore FSM state from dictionary (deserialize)."""
        self.flow_type = state["flow_type"]
        self.current_stage = state["current_stage"]
        self.stage_turn_count = state["stage_turn_count"]
        self.conversation_history = state.get("conversation_history", [])
        self._initial_flow_type = state.get("initial_flow_type", self.flow_type)
        if self.flow_type in FLOWS:
            self.flow_config = FLOWS[self.flow_type]
