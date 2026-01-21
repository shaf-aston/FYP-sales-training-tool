from .prompts import get_base_prompt

class ConsultativeStrategy:
    """IMPACT framework for high-touch consultative selling"""
    
    def get_stages(self):
        return ["intent", "logical", "emotional", "pitch", "objection"]
    
    def get_stage_prompt(self, stage, extracted, product_context):
        base = get_base_prompt(product_context, "consultative", extracted)
        
        prompts = {
            "intent": """STAGE: INTENT
GOAL: Understand their desired outcome

- If outcome already known (see context above): validate and ask ONE clarifying question
- If unclear: casual opener like "Hey, how can I help?"
- Don't ask what they want if you already know

ADVANCE: When desired outcome is clear
""",
            
            "logical": """STAGE: LOGICAL
GOAL: Create doubt in current approach

- Acknowledge what they've shared
- Ask ONE question about their current situation
- Options: "What are you doing now?" / "How long have you tried this?" / "What caused you to start?"
- Don't repeat questions about known context

ADVANCE: When problem + doubt established (2+ probes) OR user shows impatience
""",
            
            "emotional": """STAGE: EMOTIONAL
GOAL: Identity shift + consequence stacking

- Ask ONE question per turn
- "Why look elsewhere vs doubling down?"
- "So you getting X, what does that do for you?"
- "What happens if you don't change? Where are you in 2 months?"
- IDENTITY: "Big difference between WANTING and DOING. Your current mindset got you here. It won't get you there."

ADVANCE: When 2+ goals and 2+ consequences captured
""",
            
            "pitch": """GOAL: Make THEM commit

1. "Are you willing to settle for [consequence]?"
2. "Why NOW vs later? You haven't for [duration]."
3. "Whose responsibility is it?"
4. Bridge: "Based on [problem] and [goal], I think we can help. Want to put together a game plan?"
5. Present solution with 3 pillars tied to their specific problems

ADVANCE: When they commit or object
""",
            
            "objection": """GOAL: Handle resistance (NEPQ)

MONEY: "Is it the amount or the value?"
TIME: "When's right? What changes?"
PARTNER: "What would they want for you?" (expose smokescreen)
FEAR: "What's REALLY holding you back?"

Reframe: "You said [consequence] if you don't change. Is [objection] worth staying stuck?"

ADVANCE: When resolved or they walk
"""
        }
        
        return base + prompts.get(stage, "")
    
    def should_advance(self, stage, extracted, user_msg, bot_msg, probe_count):
        user_lower = user_msg.lower()
        
        # Urgency override - skip to pitch
        if any(word in user_lower for word in ["just show me", "just tell me", "let's go", "hurry"]):
            return "pitch"
        
        if stage == "intent":
            return extracted.get("desired_outcome") is not None
        
        if stage == "logical":
            has_strategy = extracted.get("current_strategy") is not None
            has_problem = extracted.get("problem") is not None
            enough_probes = probe_count.get("logical", 0) >= 2
            return has_strategy and has_problem and enough_probes
        
        if stage == "emotional":
            has_goals = len(extracted.get("goals", [])) >= 2
            has_consequences = len(extracted.get("consequences", [])) >= 2
            return has_goals and has_consequences
        
        if stage == "pitch":
            commit = any(word in user_lower for word in ["yes", "let's do it", "i'm in", "okay"])
            objection = any(word in user_lower for word in ["but", "expensive", "not sure", "think about"])
            return commit or objection
        
        if stage == "objection":
            resolved = any(word in user_lower for word in ["okay", "yes", "let's go"])
            walking = any(word in user_lower for word in ["no thanks", "not interested", "pass"])
            return resolved or walking
        
        return False
    
    def extract_from_message(self, stage, user_msg, extracted):
        user_lower = user_msg.lower()
        
        if stage == "intent":
            if not extracted.get("desired_outcome"):
                if any(w in user_lower for w in ["need", "want", "help with", "looking for"]):
                    extracted["desired_outcome"] = user_msg[:150]
        
        if stage == "logical":
            if not extracted.get("current_strategy"):
                if any(w in user_lower for w in ["doing", "using", "trying", "currently"]):
                    extracted["current_strategy"] = user_msg[:150]
            
            if not extracted.get("duration"):
                if any(w in user_lower for w in ["months", "years", "weeks", "since"]):
                    extracted["duration"] = user_msg[:100]
            
            if not extracted.get("problem"):
                if any(w in user_lower for w in ["problem", "issue", "struggling", "change", "improve"]):
                    extracted["problem"] = user_msg[:150]
        
        if stage == "emotional":
            if any(w in user_lower for w in ["would", "could", "achieve", "get to"]):
                if len(extracted.get("goals", [])) < 3:
                    extracted.setdefault("goals", []).append(user_msg[:150])
            
            if any(w in user_lower for w in ["if not", "without", "won't", "stuck", "fail"]):
                if len(extracted.get("consequences", [])) < 3:
                    extracted.setdefault("consequences", []).append(user_msg[:150])
        
        return extracted
    
    def detect_switch_signal(self, user_msg):
        """Detect if user needs transactional approach (impatience/directness)"""
        user_lower = user_msg.lower()
        
        # Impatience/directness signals → switch to transactional
        impatience_signals = [
            "just show me", "just tell me", "get to the point", "options",
            "what do you have", "cut to the chase", "too many questions",
            "hurry", "quick", "recommendations", "suggest something",
            "what are my options", "show me", "give me"
        ]
        
        # Short disengaged responses (likely frustration)
        if len(user_msg.split()) <= 3 and user_msg.lower() in ["yes", "ys", "ok", "yeah", "sure", "fine"]:
            # User giving minimal effort = wants direct approach
            return "transactional"
        
        if any(phrase in user_lower for phrase in impatience_signals):
            return "transactional"
        
        return None
