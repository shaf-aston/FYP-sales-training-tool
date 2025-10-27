"""
Prompt Manager
Builds optimized prompts by merging user input with persona details,
system instructions, and conversation context.
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .context_service import get_context_manager
# Import character profiles using absolute import to work when 'src' is on sys.path
from models.character_profiles import PERSONAS

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Template for building prompts"""
    name: str
    template: str
    required_fields: List[str]
    optional_fields: List[str] = None
    max_tokens: int = 4000


class PromptManager:
    """Manages prompt construction and optimization"""
    
    # Default prompt templates
    TEMPLATES = {
        "sales_training": PromptTemplate(
            name="sales_training",
            template=(
                "### System Instructions ###\n"
                "You are a world-class sales training simulator. Your goal is to role-play as a specific persona to help a user practice their sales skills. "
                "You must stay in character at all times and respond realistically based on the persona's profile and the conversation history.\n\n"
                "### Persona Profile: {persona_name} ###\n"
                "- **Description**: {persona_description}\n"
                "- **Background**: {persona_background}\n"
                "- **Goals**: {persona_goals}\n"
                "- **Concerns**: {persona_pain_points}\n"
                "- **Communication Style**: {persona_communication_style}\n\n"
                "### Persona's Internal Monologue (Do NOT reveal this to the user) ###\n"
                "- **Current Mood**: Slightly skeptical but curious.\n"
                "- **Hidden Objection**: Worried this will be a waste of time like other programs.\n\n"
                "### Conversation Style Examples ###\n"
                "- (Good) Salesperson: \"We have a new program that might fit your goals.\"\n"
                "- (Good) {persona_name}: \"Okay, I'm listening. What makes this one different?\"\n"
                "- (Bad) Salesperson: \"You should sign up now!\"\n"
                "- (Bad) {persona_name}: \"I will sign up now.\"\n\n"
                "### Recent Conversation History ###\n"
                "{conversation_context}\n\n"
                "### Current Interaction ###\n"
                "Salesperson: {user_input}\n"
                "{persona_name}:"
            ),
            required_fields=["persona_name", "persona_description", "user_input", "persona_background", "persona_goals", "persona_pain_points", "persona_communication_style"],
            optional_fields=["conversation_context"],
            max_tokens=4000
        ),
        
        "feedback_analysis": PromptTemplate(
            name="feedback_analysis",
            template=(
                "SALES PERFORMANCE ANALYSIS\n\n"
                "CONVERSATION TRANSCRIPT:\n"
                "{conversation_transcript}\n\n"
                "PERSONA CONTEXT: {persona_name} - {persona_description}\n\n"
                "ANALYSIS FRAMEWORK:\n"
                "Evaluate the user's sales performance across these dimensions:\n\n"
                "1. CLARITY (1-10): How clear and understandable were their messages?\n"
                "2. PERSUASION (1-10): How effectively did they present value propositions?\n"
                "3. EMPATHY (1-10): How well did they understand and address customer needs?\n"
                "4. PACING (1-10): How appropriate was their conversation flow and timing?\n"
                "5. OBJECTION HANDLING (1-10): How effectively did they address concerns?\n\n"
                "FEEDBACK FORMAT:\n"
                "- Provide specific scores for each dimension\n"
                "- Give 2-3 concrete examples of what they did well\n"
                "- Suggest 2-3 specific improvements with actionable steps\n"
                "- Highlight one key learning moment from the conversation\n\n"
                "Focus on constructive, actionable feedback that helps improve sales skills."
            ),
            required_fields=["conversation_transcript", "persona_name", "persona_description"],
            max_tokens=2000
        )
    }

    def __init__(self):
        """Initialize PromptManager"""
        self.context_manager = get_context_manager()
        self.custom_templates: Dict[str, PromptTemplate] = {}

    def get_template(self, template_name: str) -> Optional[PromptTemplate]:
        """Get template by name"""
        return self.TEMPLATES.get(template_name)

    def build_persona_context(self, persona_name: str) -> Dict[str, str]:
        """Build persona context from character profiles"""
        persona = PERSONAS.get(persona_name)
        if not persona:
            logger.warning(f"Unknown persona: {persona_name}")
            return {
                "persona_name": persona_name,
                "persona_description": f"Unknown persona: {persona_name}",
                "persona_background": "No background available.",
                "persona_goals": "No goals available.",
                "persona_pain_points": "No concerns available.",
                "persona_communication_style": "Neutral."
            }
        
        return {
            "persona_name": persona.get("name", persona_name),
            "persona_description": persona.get("description", ""),
            "persona_background": persona.get("background", ""),
            "persona_goals": ", ".join(persona.get("goals", [])),
            "persona_pain_points": ", ".join(persona.get("pain_points", [])),
            "persona_communication_style": persona.get("communication_style", "")
        }

    def build_conversation_context(self, session_id: str = "", include_recent: int = 5) -> str:
        """Build conversation context from recent messages"""
        try:
            context_window = self.context_manager.build_context_window(session_id, include_recent)
            if not context_window or "CONVERSATION HISTORY:" not in context_window:
                return "This is the beginning of your conversation."
            
            history_section = context_window.split("CONVERSATION HISTORY:")[1].strip()
            return f"RECENT CONVERSATION:\n{history_section}" if history_section else "This is the beginning of your conversation."
            
        except Exception as e:
            logger.warning(f"Error building conversation context: {e}")
            return "This is the beginning of your conversation."

    def build_sales_training_prompt(
        self, 
        user_input: str,
        persona_name: str,
        session_id: str = ""
    ) -> str:
        """Build the final sales training prompt."""
        
        template = self.get_template("sales_training")
        if not template:
            raise ValueError("Sales training template not found")
        
        persona_context = self.build_persona_context(persona_name)
        conversation_context = self.build_conversation_context(session_id)
        
        prompt_vars = {
            "user_input": user_input,
            "conversation_context": conversation_context,
            **persona_context
        }
        
        try:
            prompt = template.template.format(**prompt_vars)
            
            token_count = self.context_manager.count_tokens(prompt)
            if token_count > template.max_tokens:
                logger.warning(f"Prompt exceeds token limit: {token_count} > {template.max_tokens}. Truncating...")
                # A simple truncation strategy can be implemented here if needed
                prompt = prompt[:template.max_tokens * 4] # Rough estimate

            logger.debug(f"Built sales training prompt: {self.context_manager.count_tokens(prompt)} tokens")
            return prompt
            
        except KeyError as e:
            logger.error(f"Missing required field for prompt: {e}")
            raise ValueError(f"Missing required field for prompt template: {e}")

# Global instance
_prompt_manager = None

def get_prompt_manager() -> PromptManager:
    """Get singleton PromptManager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager