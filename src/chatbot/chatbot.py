
from groq import Groq
import os
import threading
import re
from .strategies import get_strategy
from .config import get_product_config

class SalesChatbot:
    _last_key_idx = 0
    _key_lock = threading.Lock()
    def __init__(self, api_key=None, model_name=None, product_type="general"):
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY env var or pass api_key parameter.")
        
        self.client = Groq(api_key=api_key)
        self.model_name = model_name or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.history = []
        
        # Load product config and strategy
        config = get_product_config(product_type)
        self.product_context = config["context"]
        self.strategy = get_strategy(config["strategy"])
        self.strategy_name = config["strategy"]
        
        # Initialize stage to first stage of strategy
        self.stage = self.strategy.get_stages()[0]
        
        # Store extracted information
        self.extracted = {
            "desired_outcome": None,
            "current_strategy": None,
            "duration": None,
            "problem": None,
            "goals": [],
            "consequences": []
        }
        
        # Track probing depth
        self.probe_count = {"logical": 0, "emotional": 0}
    
    def get_stage_prompt(self):
        return self.strategy.get_stage_prompt(self.stage, self.extracted, self.product_context)
    
    def extract_info(self, user_message):
        self.extracted = self.strategy.extract_from_message(self.stage, user_message, self.extracted)
    
    def should_advance_stage(self, bot_response, user_message):
        result = self.strategy.should_advance(self.stage, self.extracted, user_message, bot_response, self.probe_count)
        
        # Track probing for consultative mode
        if self.stage in ["logical", "emotional"]:
            probes = ["what do you mean", "how do you mean", "meaning", "what caused", "how long"]
            if any(p in bot_response.lower() for p in probes):
                self.probe_count[self.stage] = self.probe_count.get(self.stage, 0) + 1
        
        return result
    
    def advance_stage(self, target_stage=None):
        """Move to next stage or jump to target stage"""
        stages = self.strategy.get_stages()
        
        if target_stage and target_stage in stages:
            self.stage = target_stage
            print(f"\n[SYSTEM] → {self.stage.upper()}\n")
        else:
            idx = stages.index(self.stage)
            if idx < len(stages) - 1:
                self.stage = stages[idx + 1]
                print(f"\n[SYSTEM] → {self.stage.upper()}\n")
    
    def _classify_initial_intent(self, first_message):
        """Detect transactional vs consultative from first user message"""
        msg_lower = first_message.lower()
        
        # Transactional signals: direct intent, urgency, short imperative
        transactional_patterns = [
            r'\bi want\b', r'\bi need\b', r'\bshow me\b', r'\bgive me\b',
            r'\blooking for\b', r'\bquick\b', r'\bnow\b', r'\btoday\b',
            r'\boptions\b', r'\bprice\b', r'\bhow much\b', r'\bbuy\b'
        ]
        
        # Consultative signals: uncertainty, exploration
        consultative_patterns = [
            r'\bnot sure\b', r'\bhelp\b', r'\badvice\b', r'\bshould i\b',
            r'\bwhat do you think\b', r'\bconfused\b', r'\bexplain\b'
        ]
        
        trans_score = sum(1 for p in transactional_patterns if re.search(p, msg_lower))
        consult_score = sum(1 for p in consultative_patterns if re.search(p, msg_lower))
        
        # Short messages (<8 words) + buying keywords = transactional
        word_count = len(first_message.split())
        if word_count < 8 and trans_score > 0:
            return "transactional"
        
        # If consultative signals dominate
        if consult_score > trans_score:
            return "consultative"
        
        # If strong transactional signals
        if trans_score >= 2:
            return "transactional"
        
        # Default to consultative (safer)
        return "consultative"

    def chat(self, user_message):
        """Main chat method with dynamic strategy switching and thread-safe round-robin API key cycling"""
        
        # On first message, classify intent and set strategy
        if len(self.history) == 0:
            detected_strategy = self._classify_initial_intent(user_message)
            if detected_strategy != self.strategy_name:
                print(f"\n[SYSTEM] Initial strategy detected: {detected_strategy}\n")
                self.strategy = get_strategy(detected_strategy)
                self.strategy_name = detected_strategy
                self.stage = self.strategy.get_stages()[0]
        
        self.history.append({"role": "user", "content": user_message})

        switch_signal = self.strategy.detect_switch_signal(user_message)
        if switch_signal and switch_signal != self.strategy_name:
            print(f"\n[SYSTEM] Switching strategy: {self.strategy_name} → {switch_signal}\n")
            self.strategy = get_strategy(switch_signal)
            self.strategy_name = switch_signal
            self.stage = self.strategy.get_stages()[0]

        recent_history = self.history[-20:] if len(self.history) > 20 else self.history
        messages = [
            {"role": "system", "content": self.get_stage_prompt()}
        ] + recent_history

        api_keys = [
            os.environ.get("GROQ_API_KEY"),
            os.environ.get("BACKUP1_GROQ_API_KEY"),
            os.environ.get("BACKUP2_GROQ_API_KEY"),
        ]
        api_keys = [k for k in api_keys if k]
        
        # Fallback to instance key if no env keys
        if not api_keys and hasattr(self, 'client'):
            try:
                api_keys = [self.client.api_key]
            except Exception:
                pass
        
        if not api_keys:
            return "Error: No API keys configured."

        # Thread-safe round-robin key selection
        cls = type(self)
        with cls._key_lock:
            idx = getattr(cls, "_last_key_idx", 0) % len(api_keys)
            key = api_keys[idx]
            cls._last_key_idx = (idx + 1) % len(api_keys)

        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.8,
                max_tokens=200
            )
            bot_response = response.choices[0].message.content
            
            # Enforce single-question budget: truncate if multiple questions
            if bot_response.count('?') > 1:
                bot_response = bot_response.split('?')[0].strip() + '?'
        except Exception as e:
            return f"Error: API key failed. {str(e)}"

        self.extract_info(user_message)
        self.history.append({"role": "assistant", "content": bot_response})
        advance_result = self.should_advance_stage(bot_response, user_message)
        if advance_result:
            if isinstance(advance_result, str):
                self.advance_stage(target_stage=advance_result)
            else:
                self.advance_stage()
        return bot_response
    
    def get_conversation_summary(self):
        """Returns summary of conversation and extracted info"""
        return {
            "current_stage": self.stage,
            "strategy": self.strategy_name,
            "extracted_info": self.extracted,
            "probe_counts": self.probe_count,
            "conversation_length": len(self.history)
        }
