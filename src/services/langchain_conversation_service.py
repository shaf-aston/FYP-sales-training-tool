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
        """Get existing conversation or create new one"""
        if session_id not in self.conversations:
            # Import persona service here to avoid circular imports
            from services.persona_service import persona_service
            
            # Get persona data
            persona = persona_service.get_persona(persona_name)
            if not persona:
                raise ValueError(f"Persona {persona_name} not found")
            
            # Create memory with window of 5 exchanges (10 total messages)
            memory = ConversationBufferWindowMemory(
                k=10,
                return_messages=False,
                input_key="input",
                output_key="response"
            )
            
            # Create custom LLM wrapper
            llm = TransformersLLM(pipeline)
            
            # Create prompt template with persona data
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
            
            # Create conversation chain
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
            
            logger.info(f"🔗 Created LangChain conversation for session {session_id} with persona {persona_name}")
        
        return self.conversations[session_id]
    
    def chat_with_persona(self, message: str, session_id: str, persona_name: str, pipeline) -> Dict[str, Any]:
        """Chat with persona using LangChain conversation management"""
        try:
            start_time = time.time()
            
            # Get or create conversation chain
            conversation = self.get_or_create_conversation(session_id, persona_name, pipeline)
            
            # Get persona data for response formatting
            from services.persona_service import persona_service
            persona = persona_service.get_persona(persona_name)
            
            # Generate response using LangChain
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
            
            # Get conversation history for context
            memory = self.memories[session_id]
            message_count = len(memory.chat_memory.messages) // 2  # Pairs of human/ai messages
            
            logger.info(f"🔗 LangChain response generated in {response_time:.2f}s for {persona_name}")
            
            return {
                "response": response_data,
                "status": "success", 
                "session_id": session_id,
                "persona_name": persona_name,
                "response_time": response_time,
                "message_count": message_count,
                "langchain_managed": True
            }
            
        except Exception as e:
            logger.error(f"LangChain conversation failed: {e}")
            # Fallback to simple response
            return {
                "response": "I'm sorry, I'm having trouble responding right now. Could you try asking again?",
                "status": "error",
                "session_id": session_id,
                "persona_name": persona_name,
                "error": str(e),
                "langchain_managed": False
            }
    
    def reset_conversation(self, session_id: str) -> bool:
        """Reset conversation memory for session"""
        if session_id in self.conversations:
            self.memories[session_id].clear()
            logger.info(f"🔗 Reset LangChain conversation for session {session_id}")
            return True
        return False
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history from LangChain memory"""
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


# Global instance
_langchain_service = None

def get_langchain_service() -> LangChainConversationService:
    """Get singleton LangChain service instance"""
    global _langchain_service
    if _langchain_service is None:
        _langchain_service = LangChainConversationService()
    return _langchain_service