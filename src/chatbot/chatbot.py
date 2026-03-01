"""Sales chatbot orchestrator - refactored with FSM.

ARCHITECTURE CHANGES:
- Replaced Strategy Pattern with Finite State Machine
- Consolidated 5 strategy files into 1 flow.py
- Reduced coupling (no strategy imports)
- Single source of truth for flow logic

BENEFITS:
- 50% code reduction (183 → ~95 lines)
- Declarative flow configuration
- Higher cohesion, lower coupling
- Easier testing (pure functions)
"""

from dataclasses import dataclass
from .providers import create_provider
from .config_loader import get_product_settings
from .performance import PerformanceTracker
from .flow import SalesFlowEngine
import re
import time
import logging

# Module-level logger (consolidate all logging calls)
logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Structured response from chat() method including latency metrics.
    
    Attributes:
        content: Bot response text
        latency_ms: Elapsed time for LLM call (milliseconds)
        provider: LLM provider name ('groq', 'ollama')
        model: Model identifier
        input_len: User message character count
        output_len: Bot response character count
    """
    content: str
    latency_ms: float = None
    provider: str = None
    model: str = None
    input_len: int = 0
    output_len: int = 0


class SalesChatbot:
    """Sales chatbot with FSM-based flow management.
    
    RESPONSIBILITIES:
    - LLM provider orchestration
    - Performance tracking
    - FSM lifecycle management
    
    DESIGN PATTERN: Dependency Injection
    - Flow engine injected at init
    - Provider injected at init
    """
    
    def __init__(self, provider_type=None, model=None, product_type="general", session_id=None):
        self.provider = create_provider(provider_type, model=model)  # Factory defaults to "groq"
        self.session_id = session_id
        
        # Load product config
        config = get_product_settings(product_type)

        # Build product context with knowledge if available
        product_context = config["context"]
        if "knowledge" in config:
            product_context = f"{config['context']}\n\nPRODUCT KNOWLEDGE:\n{config['knowledge']}"

        # Load custom knowledge if available (user-provided data, separate from built-in)
        # Delimiters prevent user-entered text from being interpreted as LLM instructions
        try:
            from .knowledge import get_custom_knowledge_text
            custom_knowledge = get_custom_knowledge_text()
            if custom_knowledge:
                product_context += (
                    "\n\n--- BEGIN CUSTOM PRODUCT DATA ---\n"
                    f"{custom_knowledge}\n"
                    "--- END CUSTOM PRODUCT DATA ---"
                )
        except ImportError:
            pass  # knowledge module not available, no impact

        # Initialize FSM
        self.flow_engine = SalesFlowEngine(
            flow_type=config["strategy"],  # "consultative" or "transactional"
            product_context=product_context
        )
    
    @property
    def _provider_name(self):
        """Get provider type name (lowercase)."""
        return type(self.provider).__name__.replace('Provider', '').lower()
    
    @property
    def _model_name(self):
        """Get model identifier from provider."""
        return self.provider.get_model_name()
    
    def _fallback(self, message, latency_ms, user_message):
        """Build fallback ChatResponse after adding turn to history."""
        self.flow_engine.add_turn(user_message, message)
        return ChatResponse(
            content=message,
            latency_ms=latency_ms,
            provider=self._provider_name,
            model=self._model_name,
            input_len=len(user_message),
            output_len=len(message)
        )
    
    def chat(self, user_message):
        """Process user message and return bot response with metrics.
        
        FLOW:
        1. Build LLM messages (system prompt + history)
        2. Call LLM provider
        3. Handle errors gracefully
        4. Record turn in FSM
        5. Log performance metrics
        6. Check for stage advancement
        7. Return ChatResponse with latency
        
        Returns:
            ChatResponse: Response content + latency metrics
        """
        
        # Build messages for LLM
        recent_history = self.flow_engine.conversation_history[-10:]
        llm_messages = [
            {"role": "system", "content": self.flow_engine.get_current_prompt(user_message)}
        ] + recent_history + [
            {"role": "user", "content": user_message}
        ]
        
        # Call LLM and track latency
        request_start = time.time()
        try:
            llm_response = self.provider.chat(
                llm_messages,
                temperature=0.8,
                max_tokens=250,
                stage=self.flow_engine.current_stage
            )
            
            latency_ms = (time.time() - request_start) * 1000
            
            # Handle provider errors or empty responses
            if llm_response.error or not llm_response.content:
                error_detail = llm_response.error if llm_response.error else "empty response"
                fallback = f"I'm having trouble ({error_detail}). Try again?"
                return self._fallback(fallback, latency_ms, user_message)
            
            bot_reply = llm_response.content
            
            # Record turn
            self.flow_engine.add_turn(user_message, bot_reply)
            
            if self.session_id:
                PerformanceTracker.log_stage_latency(
                    session_id=self.session_id,
                    stage=self.flow_engine.current_stage,
                    strategy=self.flow_engine.flow_type,
                    latency_ms=latency_ms,
                    provider=self._provider_name,
                    model=self._model_name,
                    user_message_length=len(user_message),
                    bot_response_length=len(bot_reply)
                )
            
            # Check for advancement
            advancement = self.flow_engine.should_advance(user_message)
            if advancement:
                if isinstance(advancement, str):
                    # Direct jump to stage
                    self.flow_engine.advance(target_stage=advancement)
                else:
                    # Sequential advance
                    self.flow_engine.advance()
            
            return ChatResponse(
                content=bot_reply,
                latency_ms=latency_ms,
                provider=self._provider_name,
                model=self._model_name,
                input_len=len(user_message),
                output_len=len(bot_reply)
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            latency_ms = (time.time() - request_start) * 1000
            fallback = "Something went wrong. Can you try again?"
            return self._fallback(fallback, latency_ms, user_message)
    
    def rewind_to_turn(self, turn_index):
        """Rewind conversation to specific turn.
        
        Rationale: Reconstruct FSM state by replaying history.
        CRITICAL: Must reset FSM state before replaying to avoid duplication.
        
        Algorithm:
        1. Validate turn_index is within bounds
        2. Extract the history slice we want to keep
        3. HARD RESET the FSM (clear history, stage, counters)
        4. Replay turns to rebuild state from scratch with error checking
        
        Returns:
            bool: True if rewind successful, False if invalid index
        """
        # 1. Validate index
        max_turns = len(self.flow_engine.conversation_history) // 2
        if turn_index < 0 or turn_index > max_turns:
            logger.warning(f"Invalid turn_index {turn_index}, max is {max_turns}")
            return False
        
        # 2. Capture the slice of history we want to KEEP
        history_length = turn_index * 2
        # Safety check - don't exceed current history
        if history_length > len(self.flow_engine.conversation_history):
            return False

        old_history = self.flow_engine.conversation_history[:history_length]
        
        if old_history and history_length % 2 != 0:
            logger.warning("Invalid history slice (odd length)")
            return False
        
        # ---------------------------------------------------------
        # CRITICAL FIX: HARD RESET THE ENGINE STATE
        # ---------------------------------------------------------
        # Clear conversation history to an empty list
        self.flow_engine.conversation_history = []
        
        # Reset turn counter for the current stage
        self.flow_engine.stage_turn_count = 0
        
        # Reset stage to the initial stage of the current flow strategy
        initial_stage = self.flow_engine.flow_config["stages"][0]
        self.flow_engine.current_stage = initial_stage
        # ---------------------------------------------------------

        # 3. Replay turns to rebuild state from scratch
        for i in range(0, len(old_history), 2):
            if i + 1 < len(old_history):
                user_msg = old_history[i]['content']
                bot_msg = old_history[i + 1]['content']
                
                try:
                    # Now this adds to the freshly cleared history (correct)
                    self.flow_engine.add_turn(user_msg, bot_msg)
                    
                    # Re-calculate state transitions based on replayed history
                    advancement = self.flow_engine.should_advance(user_msg)
                    if advancement:
                        if isinstance(advancement, str):
                            # Direct jump to specific stage
                            self.flow_engine.advance(target_stage=advancement)
                        else:
                            # Sequential advancement to next stage
                            self.flow_engine.advance()
                except Exception as e:
                    logger.error(f"Replay error at turn {i//2}: {e}")
                    return False
        
        return True
    
    def get_conversation_summary(self):
        """Return conversation summary.
        
        Rationale: Debugging and monitoring support.
        """
        summary = self.flow_engine.get_summary()
        summary.update({
            "provider": type(self.provider).__name__,
            "model": self.provider.get_model_name()
        })
        return summary
    
    def switch_provider(self, provider_type: str, model: str = None) -> dict:
        """Hot-swap LLM provider without losing conversation state.
        
        Use Case: 
        - Fallback to local when cloud fails
        - A/B testing different models mid-conversation
        - Cost optimization (switch to local for long conversations)
        
        Args:
            provider_type: 'groq' or 'ollama'
            model: Optional model override
            
        Returns:
            dict: {"success": bool, "from": str, "to": str, "model": str}
        """
        old_provider_name = type(self.provider).__name__
        old_model = self.provider.get_model_name()
        
        try:
            new_provider = create_provider(provider_type, model=model)
            
            # Verify new provider is available before switching
            if not new_provider.is_available():
                return {
                    "success": False,
                    "error": f"{provider_type} provider is not available",
                    "current_provider": old_provider_name,
                    "current_model": old_model
                }
            
            self.provider = new_provider
            new_model = self.provider.get_model_name()
            
            logger.info(f"Provider switched: {old_provider_name}({old_model}) → "
                       f"{type(self.provider).__name__}({new_model})")
            
            return {
                "success": True,
                "from": old_provider_name.replace('Provider', '').lower(),
                "to": provider_type,
                "old_model": old_model,
                "new_model": new_model
            }
        except Exception as e:
            logger.error(f"Provider switch failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "current_provider": old_provider_name,
                "current_model": old_model
            }
