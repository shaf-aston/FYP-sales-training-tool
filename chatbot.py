from groq import Groq
import json
import os

class SalesChatbot:
    def __init__(self, api_key=None, model_name=None):
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY env var or pass api_key parameter.")
        self.client = Groq(api_key=api_key)
        self.model_name = model_name or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.history = []
        self.stage = "intent"
        
        # Store extracted information
        self.extracted = {
            "desired_outcome": None,
            "current_strategy": None,
            "problem": None,
            "goals": [],
            "consequences": []
        }
    
    def get_stage_prompt(self):
        """Returns the system prompt for current stage based on IMPACT framework"""
        
        base = f"""You are an experienced sales professional having a natural conversation. Your job is to understand what the customer wants and help them see why they need it now.

CONVERSATION RULES:
- Talk like a normal person having a real conversation
- Use casual language naturally ("man", "like", "you know")
- Keep responses SHORT (1-3 sentences max)
- Ask ONE question at a time
- NEVER mention that you're following a process, framework, or script
- If asked if you're using a script, deflect naturally, e.g: "Nah man, just trying to understand where you're at"
- Reference what they've already told you - show you're listening
- Vary your questions - don't sound repetitive

WHAT YOU KNOW SO FAR:
{json.dumps(self.extracted, indent=2)}

CURRENT FOCUS: {self.stage.upper()}
"""
        
        stage_instructions = {
            "intent": """RIGHT NOW: Figure out what they actually want

Your goal:
- Understand their desired outcome
- Find out why they want it
- Get clarity on their current situation

Natural approach:
- Start with: "Hey! What's up? How can I help you out?"
- When they answer, probe deeper: "What made you think about this now?"
- If they're vague, ask: "What would success look like for you?"

When you understand WHAT they want and WHY, acknowledge it:
"Got it, that makes sense..." then naturally move forward.
""",
            
            "logical": """RIGHT NOW: Understand what they're currently doing and why it's not working

Your goal:
- Learn about their current approach
- Identify the core problem
- Understand what they've tried

Natural approach:
- "So what have you been doing about [their goal] so far?"
- "How's that been working out?"
- "What do you like about your current setup?" (be curious, not judgmental)
- "If you could change one thing, what would it be?"

When the problem is clear, acknowledge:
"Ok, I see the issue..." then explore it more.
""",
            
            "emotional": """RIGHT NOW: Create urgency by exploring consequences and benefits

Your goal:
- Understand why they want to solve this NOW
- Paint a picture of success
- Make them feel the cost of inaction

Natural approach:
- "Why tackle this now instead of just sticking with what you're doing?"
- "Let's say you solve this - what changes for you personally?"
- "What happens if you don't fix this? Like in 6 months, a year?"
- Get 2-3 specific outcomes and consequences

When you have emotional buy-in, acknowledge:
"That's a powerful reason to act..." then transition to solution.
""",
            
            "pitch": """RIGHT NOW: Get commitment to move forward

Your goal:
- Challenge them to take ownership
- Create decision pressure
- Offer to help

Natural approach:
- "So are you cool with [bad outcome], or do you want to actually fix this?"
- "Why draw the line now instead of next month?"
- "Whose job is it to fix this - yours or someone else's?"
- "Based on everything you told me, I think I can help. Want to figure out a plan?"

Stay conversational - you're helping them commit, not selling them.
"""
        }
        
        return base + stage_instructions[self.stage]
    
    def extract_info(self, user_message, bot_response):
        """Simple extraction from conversation context"""
        user_lower = user_message.lower()
        
        # Intent stage: capture desired outcome
        if self.stage == "intent" and not self.extracted["desired_outcome"]:
            if any(word in user_lower for word in ["need", "want", "looking for", "help with"]):
                self.extracted["desired_outcome"] = user_message[:100]
        
        # Logical stage: capture strategy and problem
        if self.stage == "logical":
            if any(word in user_lower for word in ["doing", "trying", "using", "currently"]):
                self.extracted["current_strategy"] = user_message[:100]
            if any(word in user_lower for word in ["problem", "issue", "not working", "struggling"]):
                self.extracted["problem"] = user_message[:100]
        
        # Emotional stage: capture goals and consequences
        if self.stage == "emotional":
            if any(word in user_lower for word in ["would", "could", "want to", "hope"]):
                if user_message not in self.extracted["goals"]:
                    self.extracted["goals"].append(user_message[:100])
            if any(word in user_lower for word in ["if not", "without", "won't", "can't", "fail"]):
                if user_message not in self.extracted["consequences"]:
                    self.extracted["consequences"].append(user_message[:100])
    
    def should_advance_stage(self, bot_response):
        """Detect if bot has gathered enough info to move to next stage"""
        
        # Check both signal phrases and extracted data
        completion_signals = {
            "intent": ["got it", "makes sense", "understand what you", "clear on"],
            "logical": ["see the issue", "see the problem", "understand what"],
            "emotional": ["powerful reason", "big reason", "clear why", "makes sense why"]
        }
        
        if self.stage not in completion_signals:
            return False
        
        response_lower = bot_response.lower()
        has_signal = any(signal in response_lower for signal in completion_signals[self.stage])
        
        # Also check if we have extracted key info for this stage
        has_data = False
        if self.stage == "intent":
            has_data = self.extracted["desired_outcome"] is not None
        elif self.stage == "logical":
            has_data = self.extracted["problem"] is not None or self.extracted["current_strategy"] is not None
        elif self.stage == "emotional":
            has_data = len(self.extracted["goals"]) > 0 or len(self.extracted["consequences"]) > 0
        
        return has_signal and has_data
    
    def advance_stage(self):
        """Move to next stage in IMPACT framework"""
        stages = ["intent", "logical", "emotional", "pitch"]
        current_id = stages.index(self.stage)
        
        if current_id < len(stages) - 1:
            self.stage = stages[current_id + 1]
            print(f"\n[SYSTEM] Advanced to stage: {self.stage.upper()}\n")
    
    def chat(self, user_message):
        """Main chat method - handles conversation flow"""
        
        # Add user message to history
        self.history.append({"role": "user", "content": user_message})
        
        # OPTIMIZATION: Only send last 20 messages to API to prevent payload bloat
        recent_history = self.history[-20:] if len(self.history) > 20 else self.history
        messages = [
            {"role": "system", "content": self.get_stage_prompt()}
        ] + recent_history
        
        # Call Groq API
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.8,
                max_tokens=200
            )
            
            bot_response = response.choices[0].message.content
            
            # Extract info from conversation
            self.extract_info(user_message, bot_response)
            
            # Add to history
            self.history.append({"role": "assistant", "content": bot_response})
            
            # Check if should advance stage
            if self.should_advance_stage(bot_response):
                self.advance_stage()
            
            return bot_response
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                return "Error: Invalid API key. Please check your Groq API key."
            elif "rate_limit" in error_msg.lower():
                return "Error: Rate limit exceeded. Please try again in a moment."
            else:
                return f"Error: {error_msg}"
    
    def get_conversation_summary(self):
        """Returns summary of conversation and extracted info"""
        return {
            "current_stage": self.stage,
            "extracted_info": self.extracted,
            "conversation_length": len(self.history)
        }
