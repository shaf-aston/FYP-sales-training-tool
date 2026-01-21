from .prompts import get_base_prompt

class TransactionalStrategy:
    """Fast-pitch strategy for low-ticket or urgent buyers"""
    
    def get_stages(self):
        return ["intent", "pitch", "objection"]
    
    def get_stage_prompt(self, stage, extracted, product_context):
        base = get_base_prompt(product_context, "transactional", extracted)
        base += "\nSTRATEGY NOTE: Be quick and direct. Present options fast. Match their urgency.\n"
        
        prompts = {
            "intent": """GOAL: What do they want?

- Quick: "What are you looking for?"
- If clear: present options immediately
- If unclear: one clarifying question max

ADVANCE: When you know what they want
""",
            
            "pitch": """GOAL: Present options

- Show 2-3 options with key differentiators
- Use vivid language
- Let them choose
- No selling - just present

ADVANCE: When they choose or object
""",
            
            "objection": """GOAL: Handle resistance quickly

MONEY: "Amount or value issue?"
TIME: "When works better?"
UNCERTAIN: "What's holding you back?"

Keep it brief. Reframe to their goal.

ADVANCE: When resolved or they walk
"""
        }
        
        return base + prompts.get(stage, "")
    
    def should_advance(self, stage, extracted, user_msg, bot_msg, probe_count):
        user_lower = user_msg.lower()
        
        if stage == "intent":
            return extracted.get("desired_outcome") is not None
        
        if stage == "pitch":
            chose = any(w in user_lower for w in ["yes", "this one", "that one", "i'll take", "both"])
            objection = any(w in user_lower for w in ["but", "expensive", "not sure", "maybe"])
            return chose or objection
        
        if stage == "objection":
            resolved = any(w in user_lower for w in ["okay", "yes", "fine", "let's do it"])
            walking = any(w in user_lower for w in ["no", "not interested", "pass"])
            return resolved or walking
        
        return False
    
    def extract_from_message(self, stage, user_msg, extracted):
        user_lower = user_msg.lower()
        
        if stage == "intent":
            if not extracted.get("desired_outcome"):
                if any(w in user_lower for w in ["need", "want", "looking", "show me"]):
                    extracted["desired_outcome"] = user_msg[:150]
        
        return extracted
    
    def detect_switch_signal(self, user_msg):
        """Detect if user needs more consultative approach"""
        user_lower = user_msg.lower()
        
        if any(w in user_lower for w in ["not sure", "confused", "help me understand", "explain"]):
            return "consultative"
        
        return None
