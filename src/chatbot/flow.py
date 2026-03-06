"""Finite State Machine for sales flow — state transitions and advancement logic."""

from .content import generate_stage_prompt, SIGNALS
from .analysis import text_contains_any_keyword, analyze_state, user_demands_directness
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
                "max_turns": 5,
                "urgency_skip_to": "pitch",
            },
            "emotional": {
                "next": "pitch",
                "advance_on": "user_expressed_stakes",
                "max_turns": 6
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
    """True when buying signals, intent keywords, or max turns reached."""
    if user_msg and any(word in user_msg.lower() for word in ["buy", "purchase"]):
        return True

    intent_keywords = ['want', 'need', 'looking for', 'help with',
                       'interested in', 'price', 'problem']
    if user_msg and text_contains_any_keyword(user_msg.lower(), intent_keywords):
        return True

    recent_text = _recent_user_text(history)
    if text_contains_any_keyword(recent_text, intent_keywords):
        return True

    intent_level = analyze_state(history, user_msg, signal_keywords=SIGNALS)["intent"]
    max_turns = 4 if intent_level == "high" else 6
    return turns >= max_turns


def user_shows_doubt(history, user_msg, turns):
    """True when user acknowledges pain points or max turns reached."""
    if len(history) < 4:
        return turns >= 5
    doubt_keywords = ['not working', 'struggling', 'problem',
                      'difficult', 'frustrated', 'true', 'right']
    return text_contains_any_keyword(_recent_user_text(history), doubt_keywords) or turns >= 5


def user_expressed_stakes(history, user_msg, turns):
    """True when user shares emotional stakes or max turns reached."""
    if len(history) < 6:
        return turns >= 6
    emotional_keywords = ['feel', 'worried', 'excited', 'scared',
                          'hope', 'fear', 'impact', 'change']
    return text_contains_any_keyword(_recent_user_text(history), emotional_keywords) or turns >= 6


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


def _recent_user_text(history, max_messages=3):
    """Combined lowercase text of last N user messages."""
    if not history:
        return ""
    recent = history[-(max_messages * 2):]
    user_msgs = [m["content"].lower() for m in recent if m["role"] == "user"]
    return " ".join(user_msgs[-max_messages:])


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
            raise ValueError(f"Unknown flow type: {flow_type}. Available: {list(FLOWS.keys())}")

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

        # Frustration/directness: skip to pitch immediately
        if user_demands_directness(self.conversation_history, user_message):
            if "pitch" in self.flow_config["stages"]:
                return "pitch"

        # Direct info request: also jumps to pitch
        direct_requests = SIGNALS.get("direct_info_requests", [])
        if text_contains_any_keyword(user_message, direct_requests):
            if "pitch" in self.flow_config["stages"]:
                return "pitch"

        # Impatience: urgency_skip_to override (consultative only)
        urgency_target = transition.get("urgency_skip_to")
        if urgency_target and text_contains_any_keyword(user_message, SIGNALS["impatience"]):
            return urgency_target

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
        """Reconstruct FSM state by replaying message pairs."""
        for i in range(0, len(history) - 1, 2):
            user_msg = history[i]["content"]
            bot_msg = history[i + 1]["content"]
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
