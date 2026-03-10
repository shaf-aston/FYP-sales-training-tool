"""Finite State Machine for sales flow — state transitions and advancement logic."""

from .content import generate_stage_prompt, SIGNALS
from .analysis import text_contains_any_keyword, analyze_state, user_demands_directness, _extract_recent_user_text
from .config_loader import load_analysis_config

_STAGE_CONFIG = load_analysis_config()


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
                "advance_on": "user_has_clear_intent",
                "max_turns": {"low_intent": 6, "high_intent": 4}
            },
            "logical": {
                "next": "emotional",
                "advance_on": "user_shows_doubt",
                "max_turns": 10,
                "urgency_skip_to": "pitch",
            },
            "emotional": {
                "next": "pitch",
                "advance_on": "user_expressed_stakes",
                "max_turns": 10
            },
            "pitch": {
                "next": "objection",
                "advance_on": "commitment_or_objection"
            },
            "objection": {
                "next": None,
                "advance_on": "commitment_or_walkaway"
            }
        }
    },

    "transactional": {
        "stages": ["intent", "pitch", "objection"],
        "transitions": {
            "intent": {
                "next": "pitch",
                "advance_on": "user_has_clear_intent",
                "max_turns": {"low_intent": 6, "high_intent": 4}
            },
            "pitch": {
                "next": "objection",
                "advance_on": "commitment_or_objection"
            },
            "objection": {
                "next": None,
                "advance_on": "commitment_or_walkaway"
            }
        }
    }
}


# --- Advancement Rules (Pure Functions) ---

def user_has_clear_intent(history, user_msg, turns):
    """True when buying signals, intent keywords, or max turns reached.
    
    Intent stage is discovery - allow turn-based advancement since user may be reticent.
    """
    if user_msg and any(word in user_msg.lower() for word in ["buy", "purchase"]):
        return True

    intent_keywords = ['want', 'need', 'looking for', 'help with',
                       'interested in', 'price', 'problem']
    if user_msg and text_contains_any_keyword(user_msg.lower(), intent_keywords):
        return True

    recent_text = _extract_recent_user_text(history, max_messages=3)
    if text_contains_any_keyword(recent_text, intent_keywords):
        return True

    # Allow turn-based advancement for intent stage only
    intent_level = analyze_state(history, user_msg, signal_keywords=SIGNALS)["intent"]
    max_turns = 4 if intent_level == "high" else 6
    return turns >= max_turns


def user_shows_doubt(history, user_msg, turns):
    """True when user acknowledges pain points or current approach isn't working.
    
    FRAMEWORK REQUIREMENT: Must detect actual doubt/problem acknowledgment.
    Do NOT auto-advance on turn count - this violates the consultative framework.
    Safety valve: After max_turns without doubt signals, assume resistant prospect and advance.
    """
    if len(history) < 4:
        return False
    
    # Load config-driven keywords and thresholds
    logical_config = _STAGE_CONFIG.get('advancement', {}).get('logical', {})
    doubt_keywords = logical_config.get('doubt_keywords', [
        'not working', 'struggling', 'problem', 'difficult', 'frustrated'
    ])
    max_turns = logical_config.get('max_turns', 10)
    
    # Require actual doubt signals - user acknowledging current approach has problems
    recent_text = _extract_recent_user_text(history, max_messages=5)
    has_doubt = text_contains_any_keyword(recent_text, doubt_keywords)
    
    # Safety valve: if max_turns+ with no doubt, prospect may be resistant - advance anyway
    return has_doubt or turns >= max_turns


def user_expressed_stakes(history, user_msg, turns):
    """True when user shares emotional stakes or consequences.
    
    FRAMEWORK REQUIREMENT: Must detect actual emotional investment.
    Do NOT auto-advance on turn count - this violates the consultative framework.
    Safety valve: After max_turns without stakes, assume low-emotion prospect and advance.
    """
    if len(history) < 6:
        return False
    
    # Load config-driven keywords and thresholds
    emotional_config = _STAGE_CONFIG.get('advancement', {}).get('emotional', {})
    stakes_keywords = emotional_config.get('stakes_keywords', [
        'feel', 'worried', 'excited', 'scared', 'hope', 'fear'
    ])
    max_turns = emotional_config.get('max_turns', 10)
    
    # Require actual emotional stakes - user expressing why this matters personally
    recent_text = _extract_recent_user_text(history, max_messages=5)
    has_stakes = text_contains_any_keyword(recent_text, stakes_keywords)
    
    # Safety valve: if max_turns+ with no stakes, prospect may not be emotional - advance anyway
    return has_stakes or turns >= max_turns


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

    def replay_history(self, history):
        """Replay a history list, advancing FSM state as if turns happened live."""
        pairs = zip(history[::2], history[1::2])
        for user_msg_dict, bot_msg_dict in pairs:
            user_msg = user_msg_dict.get("content", "")
            bot_msg = bot_msg_dict.get("content", "")
            self.add_turn(user_msg, bot_msg)
            advancement = self.should_advance(user_msg)
            if advancement:
                self.advance(target_stage=advancement if isinstance(advancement, str) else None)

    def get_summary(self):
        """Return current FSM state as a dict."""
        return {
            "flow_type": self.flow_type,
            "current_stage": self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turns": len(self.conversation_history) // 2,
        }
