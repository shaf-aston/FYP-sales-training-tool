"""
Context Memory Service
Manages conversation history and persona consistency
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ContextMemoryService:
    """Manages conversation context and memory across chat sessions"""
    
    def __init__(self):
        self.conversations: Dict[str, List[Dict]] = {}  # session_id -> messages
        self.persona_facts: Dict[str, Dict[str, Any]] = {}  # persona -> facts
        self.user_context: Dict[str, Dict[str, Any]] = {}  # user_id -> context
        
    def add_message(self, session_id: str, message: str, sender: str, persona: str = None):
        """Add message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
            
        message_data = {
            "message": message,
            "sender": sender,
            "timestamp": datetime.now().isoformat(),
            "persona": persona
        }
        
        self.conversations[session_id].append(message_data)
        
        # Keep last 30 messages for better context (increased from 20)
        if len(self.conversations[session_id]) > 30:
            self.conversations[session_id] = self.conversations[session_id][-15:]
    
    def get_conversation_context(self, session_id: str, max_messages: int = 10) -> str:
        """Get formatted conversation history for context"""
        if session_id not in self.conversations:
            return ""
            
        messages = self.conversations[session_id][-max_messages:]
        context_parts = []
        
        for msg in messages:
            sender = "Human" if msg["sender"] == "user" else msg.get("persona", "AI")
            context_parts.append(f"{sender}: {msg['message']}")
            
        return "\n".join(context_parts)
    
    def add_persona_fact(self, persona: str, key: str, value: Any):
        """Store consistent facts about a persona"""
        if persona not in self.persona_facts:
            self.persona_facts[persona] = {}
            
        self.persona_facts[persona][key] = {
            "value": value,
            "created": datetime.now().isoformat(),
            "source": "conversation"
        }
        
        logger.info(f"Stored fact for {persona}: {key} = {value}")
    
    def get_persona_facts(self, persona: str) -> Dict[str, Any]:
        """Get all stored facts about a persona"""
        return self.persona_facts.get(persona, {})
    
    def build_enhanced_prompt(self, persona: str, user_message: str, session_id: str) -> str:
        """Build comprehensive prompt with context and persona consistency"""
        
        # Get conversation history
        conversation_history = self.get_conversation_context(session_id, max_messages=15)
        
        # Get persona facts
        persona_facts = self.get_persona_facts(persona)
        facts_str = ""
        if persona_facts:
            facts_list = [f"- {key}: {data['value']}" for key, data in persona_facts.items()]
            facts_str = f"\n\nKnown facts about {persona} (MAINTAIN CONSISTENCY):\n" + "\n".join(facts_list)
        
        # Build comprehensive prompt with STRONG user message focus
        enhanced_prompt = f"""You are {persona}, a sales training persona. Respond naturally and consistently with your character.

CRITICAL INSTRUCTIONS:
1. FOCUS HEAVILY on the user's current message - it has the HIGHEST priority
2. Give detailed, contextual responses (3-5 sentences minimum)
3. Stay completely in character as {persona}
4. If you don't know specific details, say "I'm not sure about that" or "I don't have that information" - DO NOT make things up
5. Be consistent with facts mentioned in previous conversations
6. Respond directly to what the user is asking with high relevance
7. Show personality and emotion appropriate to your character
8. If making up a detail is necessary for realism, remember it and stay consistent{facts_str}

Recent Conversation History:
{conversation_history}

USER'S CURRENT MESSAGE (HIGHEST PRIORITY - ANSWER THIS DIRECTLY):
{user_message}

Respond as {persona} with a detailed, relevant answer focusing on the user's message:"""

        return enhanced_prompt
    
    def extract_new_facts(self, persona: str, ai_response: str):
        """Extract new facts from AI response to maintain consistency"""
        # Simple keyword-based fact extraction
        # In production, you could use NLP to extract entities and facts
        
        fact_indicators = [
            "I work at", "My job is", "I am", "I have", "My family",
            "I live in", "My budget is", "I earn", "My concern is",
            "I need", "I want", "I prefer", "I like", "I dislike"
        ]
        
        for indicator in fact_indicators:
            if indicator.lower() in ai_response.lower():
                # Extract the sentence containing the fact
                sentences = ai_response.split('.')
                for sentence in sentences:
                    if indicator.lower() in sentence.lower():
                        fact_key = indicator.lower().replace(" ", "_")
                        self.add_persona_fact(persona, fact_key, sentence.strip())
                        break
    
    def clear_session(self, session_id: str):
        """Clear specific session history"""
        if session_id in self.conversations:
            del self.conversations[session_id]
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of session for analytics"""
        if session_id not in self.conversations:
            return {"message_count": 0, "duration": 0}
            
        messages = self.conversations[session_id]
        if not messages:
            return {"message_count": 0, "duration": 0}
            
        start_time = datetime.fromisoformat(messages[0]["timestamp"])
        end_time = datetime.fromisoformat(messages[-1]["timestamp"])
        duration = (end_time - start_time).total_seconds()
        
        return {
            "message_count": len(messages),
            "duration": duration,
            "start_time": messages[0]["timestamp"],
            "end_time": messages[-1]["timestamp"],
            "personas_involved": list(set(msg.get("persona") for msg in messages if msg.get("persona")))
        }

# Global context memory service
context_memory = ContextMemoryService()