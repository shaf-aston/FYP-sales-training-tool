"""Finite State Machine for sales flow management.

Provides: Single source of truth for flow logic and state transitions.

DESIGN PRINCIPLES:
- Declarative configuration (data > code)
- Pure functions for advancement logic
- Single Responsibility: FSM owns state transitions
"""

from .content import generate_stage_prompt, SIGNALS
from .analysis import (
    text_contains_any_keyword,
    check_user_intent_keywords,
    analyze_state,
    user_demands_directness
)
from .config_loader import load_analysis_config

# Cache config to avoid disk I/O on every stage check
_STAGE_CONFIG = load_analysis_config()


# ============================================================================
# DECLARATIVE FLOW CONFIGURATION
# ============================================================================

FLOWS = {
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
                "urgency_skip_to": "pitch"  # Impatience override
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
                "next": None,  # Terminal state
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


# ============================================================================
# ADVANCEMENT LOGIC (Pure Functions)
# ============================================================================

def _get_max_turns(stage, intent_level='medium'):
    """Get max turns for stage from config.
    
    Rationale: Avoid hardcoded magic numbers.
    """
    advancement = _STAGE_CONFIG.get('advancement', {})
    
    if stage == 'intent':
        intent_config = advancement.get('intent', {})
        if intent_level == 'low':
            return intent_config.get('low_intent_max_turns', 6)
        return intent_config.get('high_intent_max_turns', 4)
    
    return advancement.get(stage, {}).get('max_turns', 5)


def user_has_clear_intent(history, user_msg, turns):
    """Check if user expressed clear buying/problem intent.

    Advance when:
    1. Buying signals (high intent) - in CURRENT message
    2. Intent keywords (moderate intent) - in history OR current
    3. Max turns based on intent level (forced progression)

    Note: Direct info requests are handled by should_advance() as pitch jumps.
    """
    # Buying signals - high intent
    if user_msg and any(word in user_msg.lower() for word in ["buy", "purchase"]):
        return True
    
    # Intent keywords - check CURRENT message + history
    intent_keywords = ['want', 'need', 'looking for', 'help with', 
                      'interested in', 'price', 'problem']
    if user_msg and text_contains_any_keyword(user_msg.lower(), intent_keywords):
        return True
    if check_user_intent_keywords(history, intent_keywords):
        return True
    
    # Max turns based on intent level (avoid stagnation)
    intent_level = analyze_state(history, user_msg)["intent"]
    max_turns = _get_max_turns('intent', intent_level)
    return turns >= max_turns


def user_shows_doubt(history, user_msg, turns):
    """Detect doubt in current solution.
    
    Rationale: Logical stage probes current pain points. Advance when:
    1. User acknowledges problems with status quo
    2. Max turns reached (move to emotional stakes)
    """
    if len(history) < 4:
        return turns >= 5
    
    doubt_keywords = ['not working', 'struggling', 'problem', 
                     'difficult', 'frustrated', 'true', 'right']
    return check_user_intent_keywords(history, doubt_keywords) or turns >= 5


def user_expressed_stakes(history, user_msg, turns):
    """Detect emotional investment.
    
    Rationale: Emotional stage reveals personal impact. Advance when:
    1. User shares feelings/consequences
    2. Max turns reached (move to solution)
    """
    if len(history) < 6:
        return turns >= 6
    
    emotional_keywords = ['feel', 'worried', 'excited', 'scared', 
                         'hope', 'fear', 'impact', 'change']
    return check_user_intent_keywords(history, emotional_keywords) or turns >= 6


def commitment_or_objection(history, user_msg, turns):
    """Detect commitment or objection signals.
    
    Rationale: Pitch stage aims for decision. Advance when user shows:
    1. Commitment signals (ready to buy)
    2. Objections (need handling before close)
    """
    return (text_contains_any_keyword(user_msg, SIGNALS["commitment"]) or
            text_contains_any_keyword(user_msg, SIGNALS["objection"]))


def commitment_or_walkaway(history, user_msg, turns):
    """Detect deal close or walkaway.
    
    Rationale: Objection stage is final decision point. Stay until:
    1. Commitment (deal closed)
    2. Walkaway (deal lost)
    """
    return (text_contains_any_keyword(user_msg, SIGNALS["commitment"]) or
            text_contains_any_keyword(user_msg, SIGNALS["walking"]))


# Map function names to callables
ADVANCEMENT_RULES = {
    "user_has_clear_intent": user_has_clear_intent,
    "user_shows_doubt": user_shows_doubt,
    "user_expressed_stakes": user_expressed_stakes,
    "commitment_or_objection": commitment_or_objection,
    "commitment_or_walkaway": commitment_or_walkaway
}


# ============================================================================
# FSM ENGINE
# ============================================================================

class SalesFlowEngine:
    """Finite State Machine for sales conversation flow.
    
    RESPONSIBILITIES:
    - Current state tracking
    - Transition logic evaluation
    - Stage-specific prompt generation
    - Conversation history management
    
    DESIGN PATTERN: Finite State Machine
    - States: intent, logical, emotional, pitch, objection
    - Transitions: Declarative rules in FLOWS config
    - Events: User messages trigger advancement checks
    """
    
    def __init__(self, flow_type, product_context):
        if flow_type not in FLOWS:
            raise ValueError(f"Unknown flow type: {flow_type}. Available: {list(FLOWS.keys())}")
        
        self.flow_config = FLOWS[flow_type]
        self.flow_type = flow_type
        self.product_context = product_context
        
        # State tracking
        self.current_stage = self.flow_config["stages"][0]
        self.stage_turn_count = 0
        self.conversation_history = []
    
    def get_current_prompt(self, user_message=""):
        """Generate prompt for current stage.
        
        Rationale: Delegates to prompts.py for content generation.
        FSM only manages flow logic, not content.
        """
        strategy = "consultative" if "emotional" in self.flow_config["stages"] else "transactional"
        return generate_stage_prompt(
            strategy=strategy,
            stage=self.current_stage,
            product_context=self.product_context,
            history=self.conversation_history,
            user_message=user_message
        )
    
    def should_advance(self, user_message):
        """Determine if should transition to next stage.
        
        Returns:
        - False: Stay in current stage
        - True: Advance to next sequential stage
        - str: Jump to specific stage (urgency override)
        
        Rationale: Centralized decision logic. Checks:
        1. Frustration override (skip to pitch immediately)
        2. Urgency overrides (skip stages)
        3. Advancement rules (data-driven)
        """
        transition = self.flow_config["transitions"].get(self.current_stage)
        if not transition:
            return False
        
        # Check frustration override FIRST (overrides all other rules)
        if user_demands_directness(self.conversation_history, user_message):
            # Skip directly to pitch stage if available
            if "pitch" in self.flow_config["stages"]:
                return "pitch"  # Jump to pitch, skip intermediate stages

        # Check for direct information requests (advance to pitch)
        direct_requests = SIGNALS.get("direct_info_requests", [])
        if any(phrase in user_message.lower() for phrase in direct_requests):
            if "pitch" in self.flow_config["stages"]:
                return "pitch"
        
        # Check urgency override (consultative only - impatience)
        urgency_target = transition.get("urgency_skip_to")
        if urgency_target and text_contains_any_keyword(user_message, SIGNALS["impatience"]):
            return urgency_target
        
        # Check advancement rule
        rule_name = transition.get("advance_on")
        if rule_name and rule_name in ADVANCEMENT_RULES:
            rule_func = ADVANCEMENT_RULES[rule_name]
            if rule_func(self.conversation_history, user_message, self.stage_turn_count):
                return True
        
        return False
    
    def advance(self, target_stage=None):
        """Move to next stage.
        
        Args:
        - target_stage: Specific stage to jump to (urgency override)
        - None: Sequential advancement
        
        Rationale: Supports both linear progression and stage skipping.
        """
        stages = self.flow_config["stages"]
        
        if target_stage and target_stage in stages:
            # Direct jump (urgency override)
            self.current_stage = target_stage
            self.stage_turn_count = 0
        else:
            # Sequential advancement
            current_idx = stages.index(self.current_stage)
            if current_idx < len(stages) - 1:
                self.current_stage = stages[current_idx + 1]
                self.stage_turn_count = 0
    
    def add_turn(self, user_message, bot_response):
        """Record conversation turn.
        
        Rationale: FSM owns conversation state. Single source of truth.
        """
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": bot_response})
        self.stage_turn_count += 1
    
    def get_summary(self):
        """Return current state summary.
        
        Rationale: Debugging and monitoring support.
        """
        return {
            "flow_type": self.flow_type,
            "current_stage": self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turns": len(self.conversation_history) // 2
        }
