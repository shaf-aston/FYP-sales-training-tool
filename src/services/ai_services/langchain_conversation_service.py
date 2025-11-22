"""
LangChain integration service for conversation management
Replaces custom prompt building with LangChain conversation chains and memory
"""
import logging
import time
from typing import Dict, Any

from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate

from .langchain_base import BaseLangChainService, TransformersLLM
from .langchain_exceptions import PersonaNotFoundError, ConversationError
from config.model_config import BASE_MODEL, LANGCHAIN_CONFIG

logger = logging.getLogger(__name__)

class LangChainConversationService(BaseLangChainService):
    """LangChain-based conversation management service."""

    def __init__(self):
        super().__init__()
        logger.info("LangChain conversation service initialized")

    def _create_persona_prompt_template(self, persona_data: Dict) -> PromptTemplate:
        """Create a LangChain prompt template for the persona."""
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

Salesperson: {input}

Now respond as {persona_name} (speak naturally, no labels):"""

        input_variables = [
            "persona_name", "age", "background", "personality_traits", 
            "goals", "concerns", "budget_range", "decision_style", 
            "expertise_level", "objections", "preferred_communication",
            "history", "input"
        ]

        return PromptTemplate(
            input_variables=input_variables,
            template=template
        )

    def get_or_create_conversation(self, session_id: str, persona_name: str, pipeline) -> ConversationChain:
        """Get existing conversation or create new one."""
        if session_id not in self.conversations:
            from .persona_service import persona_service  # Corrected import path

            persona = persona_service.get_persona(persona_name)
            if not persona:
                raise PersonaNotFoundError(f"Persona {persona_name} not found")

            memory = ConversationBufferWindowMemory(
                k=self.memory_window,
                return_messages=False,
                input_key="input",
                output_key="response"
            )

            llm = TransformersLLM(pipeline)

            prompt_template = self._create_persona_prompt_template({
                "persona_name": persona.name,
                "age": persona.age,
                "background": persona.background,
                "personality_traits": ", ".join(persona.personality_traits),
                "goals": ", ".join(persona.goals),
                "concerns": ", ".join(persona.concerns),
                "budget_range": persona.budget_range,
                "decision_style": persona.decision_style,
                "expertise_level": persona.expertise_level,
                "objections": ", ".join(persona.objections),
                "preferred_communication": persona.preferred_communication
            })

            conversation = ConversationChain(
                llm=llm,
                prompt=prompt_template,
                memory=memory,
                verbose=False,
                input_key="input",
                output_key="response"
            )

            self.conversations[session_id] = conversation
            self.memories[session_id] = memory

            logger.info(f"Created LangChain conversation for session {session_id} with persona {persona_name}")

        return self.conversations[session_id]
    
    def chat_with_persona(self, message: str, session_id: str, persona_name: str, pipeline) -> Dict[str, Any]:
        """Chat with persona using LangChain conversation management"""
        try:
            start_time = time.time()
            
            conversation = self.get_or_create_conversation(session_id, persona_name, pipeline)
            
            from .persona_service import persona_service
            persona = persona_service.get_persona(persona_name)
            
            response_data = conversation.predict(
                input=message,
                persona_name=persona.name,
                age=persona.age,
                background=persona.background,
                personality_traits=", ".join(persona.personality_traits),
                goals=", ".join(persona.goals),
                concerns=", ".join(persona.concerns),
                budget_range=persona.budget_range,
                decision_style=persona.decision_style,
                expertise_level=persona.expertise_level,
                objections=", ".join(persona.objections),
                preferred_communication=persona.preferred_communication
            )
            
            response_time = time.time() - start_time
            
            memory = self.memories[session_id]
            message_count = len(memory.chat_memory.messages) // 2
            
            logger.info(f"LangChain response generated in {response_time:.2f}s for {persona_name}")
            
            return {
                "response": response_data,
                "status": "success", 
                "session_id": session_id,
                "persona_name": persona_name,
                "response_time": response_time,
                "message_count": message_count,
                "langchain_managed": True
            }
            
        except PersonaNotFoundError as e:
            logger.error(f"Persona not found: {e}")
            return {
                "response": LANGCHAIN_CONFIG["fallback_message"],
                "status": "error",
                "session_id": session_id,
                "persona_name": persona_name,
                "error": str(e),
                "langchain_managed": False
            }
        except Exception as e:
            logger.error(f"LangChain conversation failed: {e}", exc_info=True)
            return {
                "response": LANGCHAIN_CONFIG["fallback_message"],
                "status": "error",
                "session_id": session_id,
                "persona_name": persona_name,
                "error": str(e),
                "langchain_managed": False
            }

_langchain_service = None

def get_langchain_service() -> "LangChainConversationService":
    """Get singleton LangChain service instance"""
    global _langchain_service
    if _langchain_service is None:
        _langchain_service = LangChainConversationService()
    return _langchain_service