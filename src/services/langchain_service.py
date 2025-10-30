"""
LangChain integration service for conversation management
Replaces custom prompt building with LangChain conversation chains and memory
"""
import logging
from typing import Dict, List, Optional, Any
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)


class TransformersLLM(LLM):
    """Custom LangChain LLM wrapper for Transformers pipeline"""
    
    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self.model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the model with the given prompt"""
        try:
            # Use optimized generation params
            response = self.pipeline(
                prompt,
                max_new_tokens=50,
                do_sample=False,
                temperature=1.0,
                repetition_penalty=1.1,
                return_full_text=False,
                pad_token_id=self.pipeline.tokenizer.eos_token_id if hasattr(self.pipeline, 'tokenizer') else None,
                eos_token_id=self.pipeline.tokenizer.eos_token_id if hasattr(self.pipeline, 'tokenizer') else None,
            )
            
            generated_text = response[0]['generated_text'].strip()
            
            # Clean response - remove any persona labels or formatting
            import re
            generated_text = re.sub(r'###.*?###', '', generated_text, flags=re.IGNORECASE | re.DOTALL)
            generated_text = re.sub(r'\b\w+\s*\(potential customer\):', '', generated_text, flags=re.IGNORECASE)
            generated_text = re.sub(r'\bMary\s*:', '', generated_text, flags=re.IGNORECASE)
            generated_text = re.sub(r"I understand the benefits", "I've heard about the benefits but I'm not sure", generated_text, flags=re.IGNORECASE)
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"LangChain LLM call failed: {e}")
            return "I'm sorry, I'm having trouble responding right now. Could you try asking again?"
    
    @property
    def _llm_type(self) -> str:
        return "transformers_pipeline"


class LangChainConversationService:
    """LangChain-based conversation management service"""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationChain] = {}
        self.memories: Dict[str, ConversationBufferWindowMemory] = {}
        logger.info("🔗 LangChain conversation service initialized")
    
    def _create_persona_prompt_template(self, persona_data: Dict) -> PromptTemplate:
        """Create a LangChain prompt template for the persona"""
        template = """You are {persona_name}, a {age}-year-old potential fitness customer.

CRITICAL PERSONALITY RULES:
- You are CAUTIOUS and UNCERTAIN about fitness - NOT confident or experienced
- You have real CONCERNS and FEARS about starting exercise (express these!)
- You're seeking HELP because you DON'T know what to do - you're not an expert
- When asked about past exercise, be HONEST about your gaps and worries
- NEVER say "I understand the benefits" - say "I've heard about benefits but I'm worried..."

YOUR PROFILE:
- Background: {background}
- Personality: {personality_traits}
- Goals: {goals}
- Main Concerns: {concerns}
- Budget Range: {budget_range}
- Decision Style: {decision_style}
- Expertise Level: {expertise_level}

BEHAVIORAL GUIDELINES:
- Respond naturally as {persona_name} would in first person
- Show your concerns: {concerns}
- Use objections when appropriate: {objections}
- Communication style: {preferred_communication}
- Consider your budget: {budget_range}
- DO NOT include any labels like "{persona_name}:" in your response
- Just speak naturally as yourself

Current conversation:
{history}