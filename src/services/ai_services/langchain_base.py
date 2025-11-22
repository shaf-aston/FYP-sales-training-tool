"""
Base components for LangChain integration.
"""
import logging
import re
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from config.model_config import BASE_MODEL, LANGCHAIN_CONFIG

if TYPE_CHECKING:
    from langchain.memory import ConversationBufferWindowMemory
    from langchain.schema import BaseMessage, HumanMessage, AIMessage
    from langchain.chains import ConversationChain
    from langchain.prompts import PromptTemplate
    from langchain.llms.base import LLM
    from langchain.callbacks.manager import CallbackManagerForLLMRun
else:
    try:
        from langchain.memory import ConversationBufferWindowMemory
        from langchain.schema import BaseMessage, HumanMessage, AIMessage
        from langchain.chains import ConversationChain
        from langchain.prompts import PromptTemplate
        from langchain.llms.base import LLM
        from langchain.callbacks.manager import CallbackManagerForLLMRun
        HAS_LANGCHAIN = True
    except ImportError:
        HAS_LANGCHAIN = False
        ConversationBufferWindowMemory = None
        BaseMessage = None
        HumanMessage = None
        AIMessage = None
        ConversationChain = None
        PromptTemplate = None
        LLM = None
        CallbackManagerForLLMRun = None

logger = logging.getLogger(__name__)


class TransformersLLM(LLM):
    """Custom LangChain LLM wrapper for Transformers pipeline"""

    def __init__(
        self,
        pipeline,
        max_new_tokens=None,
        temperature=None,
        repetition_penalty=None
    ):
        super().__init__()
        self.pipeline = pipeline
        self.model_name = BASE_MODEL
        self.max_new_tokens = max_new_tokens or LANGCHAIN_CONFIG["max_new_tokens"]
        self.temperature = temperature or LANGCHAIN_CONFIG["temperature"]
        self.repetition_penalty = repetition_penalty or LANGCHAIN_CONFIG["repetition_penalty"]
        self.fallback_message = LANGCHAIN_CONFIG["fallback_message"]

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the model with the given prompt"""
        try:
            response = self.pipeline(
                prompt,
                max_new_tokens=self.max_new_tokens,
                do_sample=True,
                temperature=self.temperature,
                repetition_penalty=self.repetition_penalty,
                return_full_text=False,
                pad_token_id=self.pipeline.tokenizer.eos_token_id if hasattr(self.pipeline, 'tokenizer') else None,
                eos_token_id=self.pipeline.tokenizer.eos_token_id if hasattr(self.pipeline, 'tokenizer') else None,
            )

            generated_text = response[0]['generated_text'].strip()
            generated_text = re.sub(r'#.*', '', generated_text, flags=re.IGNORECASE)
            generated_text = re.sub(r'\b\w+\s*\(potential customer\):', '', generated_text, flags=re.IGNORECASE)
            generated_text = re.sub(r'\bMary\s*:', '', generated_text, flags=re.IGNORECASE)
            generated_text = re.sub(r"I understand the benefits", "I've heard about the benefits but I'm not sure", generated_text, flags=re.IGNORECASE)

            return generated_text.strip()

        except Exception as e:
            logger.error(f"LangChain LLM call failed: {e}")
            return self.fallback_message
        finally:
            logger.debug("LangChain LLM call completed.")

    @property
    def _llm_type(self) -> str:
        return "transformers_pipeline"


class BaseLangChainService:
    """Base class for LangChain services to share common functionality."""

    def __init__(self):
        self.conversations: Dict[str, ConversationChain] = {}
        self.memories: Dict[str, ConversationBufferWindowMemory] = {}
        self.memory_window = LANGCHAIN_CONFIG["memory_window"]
        logger.info("Base LangChain service initialized")

    def reset_conversation(self, session_id: str) -> bool:
        """Reset conversation memory for session."""
        if session_id in self.conversations:
            self.memories[session_id].clear()
            logger.info(f"Reset LangChain conversation for session {session_id}")
            return True
        return False

    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history from LangChain memory."""
        if session_id not in self.memories:
            return []

        memory = self.memories[session_id]
        messages = memory.chat_memory.messages

        history = []
        for i in range(0, len(messages), 2):
            if i + 1 < len(messages):
                history.append({
                    "user_message": messages[i].content,
                    "persona_response": messages[i + 1].content
                })

        return history
