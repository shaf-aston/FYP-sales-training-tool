"""Finite State Machine for sales flow — state transitions and advancement logic."""

from .content import generate_stage_prompt, SIGNALS
from .analysis import text_contains_any_keyword, analyze_state, user_demands_directness, _extract_recent_user_text
from .loader import load_analysis_config

_STAGE_CONFIG = load_analysis_config()

# Shared transitions used across multiple strategies (identical regardless of strategy)
_COMMON_TRANSITIONS = {
    "pitch": {
        "next": "objection",
        "advance_on": "commitment_or_objection"
    },
    "objection": {
        "next": None,
        "advance_on": "commitment_or_walkaway"
    }
}

FLOWS = {
    "intent": {
        "stages": ["intent"],
        "transitions": {
            "intent": {
                "next": None,
                "advance_on": None,
            }
        }
    },

    "consultative": {
        "stages": ["intent", "logical", "emotional", "pitch", "objection"],
        "transitions": {
            "intent": {
                "next": "logical",
                "advance_on": "user_has_clear_intent"
            },
            "logical": {
                "next": "emotional",
                "advance_on": "user_shows_doubt",
                "urgency_skip_to": "pitch",
            },
            "emotional": {
                "next": "pitch",
                "advance_on": "user_expressed_stakes"
            },
            **_COMMON_TRANSITIONS
        }
    },

    "transactional": {
        "stages": ["intent", "pitch", "objection"],
        "transitions": {
            "intent": {
                "next": "pitch",
                "advance_on": "user_has_clear_intent"
            },
            **_COMMON_TRANSITIONS
        }
    }
}


# --- Advancement Rules (Pure Functions) ---

def user_has_clear_intent(history, user_msg, turns):
    """True when buying signals, intent keywords, or max turns reached.

    Intent stage is discovery - allow turn-based advancement since user may be reticent.
    NOTE: 'want' and 'need' are deliberately excluded - they are stopwords (analysis.py)
    and fire on generic statements ("I want to make money") that carry no buying intent.
    """
    intent_keywords = ['looking for', 'help with', 'interested in',
                       'price', 'problem', 'buy', 'purchase', 'struggling',
                       'have to', 'ready to buy', 'looking to buy']
    if user_msg and text_contains_any_keyword(user_msg.lower(), intent_keywords):
        return True

    recent_text = _extract_recent_user_text(history, max_messages=3)
    if text_contains_any_keyword(recent_text, intent_keywords):
        return True

    # Allow turn-based advancement for intent stage only
    intent_level = analyze_state(history, user_msg, signal_keywords=SIGNALS)["intent"]
    max_turns = 4 if intent_level == "high" else 6
    return turns >= max_turns


def _check_advancement_condition(history, user_msg, turns, stage_name, min_turns=2):
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
    stage_config = _STAGE_CONFIG.get('advancement', {}).get(stage_name, {})
    keyword_key = {
        'logical': 'doubt_keywords',
        'emotional': 'stakes_keywords'
    }.get(stage_name, f'{stage_name}_keywords')

    keywords = stage_config.get(keyword_key, [])
    max_turns = stage_config.get('max_turns', 10)

    # Check for signal in recent conversation
    recent_text = _extract_recent_user_text(history, max_messages=5)
    has_signal = text_contains_any_keyword(recent_text, keywords)

    # Safety valve: auto-advance if max_turns exceeded (resistant prospect)
    return has_signal or turns >= max_turns


def user_shows_doubt(history, user_msg, turns):
    """True when user acknowledges pain points or current approach isn't working.

    FRAMEWORK REQUIREMENT: Must detect actual doubt/problem acknowledgment.
    Safety valve: After max_turns without doubt signals, assume resistant prospect and advance.
    """
    return _check_advancement_condition(history, user_msg, turns, 'logical', min_turns=2)


def user_expressed_stakes(history, user_msg, turns):
    """True when user shares emotional stakes or consequences.

    FRAMEWORK REQUIREMENT: Must detect actual emotional investment.
    Safety valve: After max_turns without stakes, assume low-emotion prospect and advance.
    """
    return _check_advancement_condition(history, user_msg, turns, 'emotional', min_turns=3)


def commitment_or_objection(history, user_msg, turns):
    """True when user commits or objects. Short messages excluded (likely fillers)."""
    if len(user_msg.split()) < 3:
        return False
    return (text_contains_any_keyword(user_msg, SIGNALS["commitment"]) or
            text_contains_any_keyword(user_msg, SIGNALS["objection"]))


def commitment_or_walkaway(history, user_msg, turns):
    """True when user commits or walks away — objection stage exit."""
    return (text_contains_any_keyword(user_msg, SIGNALS["commitment"]) or
            text_contains_any_keyword(user_msg, SIGNALS["walking"]))


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

    def __init__(self, flow_type, product_context):
        if flow_type not in FLOWS:
            flow_type = "consultative"
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
        if self.flow_type in ("consultative", "transactional"):
            return self.flow_type
        return "consultative"

    def get_current_prompt(self, user_message=""):
        """Generate system prompt for current stage via content.py."""
        return generate_stage_prompt(
            strategy=self.strategy_for_prompts,
            stage=self.current_stage,
            product_context=self.product_context,
            history=self.conversation_history,
            user_message=user_message,
        )

    def should_advance(self, user_message):
        """Return False (stay), True (next stage), or str (jump to named stage)."""
        transition = self.flow_config["transitions"].get(self.current_stage)
        if not transition:
            return False

        has_pitch_stage = "pitch" in self.flow_config["stages"]
        
        # Frustration/directness OR direct info request: skip to pitch immediately
        if has_pitch_stage:
            if user_demands_directness(self.conversation_history, user_message):
                return "pitch"
            
            direct_requests = SIGNALS.get("direct_info_requests", [])
            if text_contains_any_keyword(user_message, direct_requests):
                return "pitch"

        # Impatience: urgency_skip_to override (consultative only)
        if transition.get("urgency_skip_to"):
            if text_contains_any_keyword(user_message, SIGNALS.get("impatience", [])):
                return transition["urgency_skip_to"]

        rule_name = transition.get("advance_on")
        if rule_name and rule_name in ADVANCEMENT_RULES:
            if ADVANCEMENT_RULES[rule_name](self.conversation_history, user_message, self.stage_turn_count):
                return True

        return False

    def advance(self, target_stage=None):
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

    def add_turn(self, user_message, bot_response):
        """Append user/assistant messages and increment turn counter."""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        self.stage_turn_count += 1

    def switch_strategy(self, new_strategy):
        """Switch FSM to a different strategy. Resets to first stage."""
        if new_strategy not in FLOWS:
            return False
        self.flow_type = new_strategy
        self.flow_config = FLOWS[new_strategy]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        return True

    def reset_to_initial(self):
        """Reset FSM to initial flow type (before any strategy switches). Clears history."""
        self.flow_type = self._initial_flow_type
        self.flow_config = FLOWS[self._initial_flow_type]
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []

    def get_summary(self):
        """Return current FSM state as a dict."""
        return {
            "flow_type": self.flow_type,
            "display_strategy": self.strategy_for_prompts,
            "current_stage": self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turns": len(self.conversation_history) // 2,
        }
