"""
Prompt Manager
Builds optimized prompts by merging user input with persona details,
system instructions, and conversation context.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
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
            template="""You are {persona_name}, {persona_description}

TRAINING CONTEXT:
{training_objectives}

CONVERSATION GUIDELINES:
- Stay in character as {persona_name}
- Respond naturally to sales approaches
- {persona_behavior}
- Provide realistic objections and concerns
- Keep responses focused and authentic

{conversation_context}

USER MESSAGE: {user_input}

Respond as {persona_name} would in this sales training scenario. Be natural, authentic, and true to the character profile.""",
            required_fields=["persona_name", "persona_description", "user_input"],
            optional_fields=["training_objectives", "persona_behavior", "conversation_context"],
            max_tokens=3500
        ),
        
        "feedback_analysis": PromptTemplate(
            name="feedback_analysis",
            template="""SALES PERFORMANCE ANALYSIS

CONVERSATION TRANSCRIPT:
{conversation_transcript}

PERSONA CONTEXT: {persona_name} - {persona_description}

ANALYSIS FRAMEWORK:
Evaluate the user's sales performance across these dimensions:

1. CLARITY (1-10): How clear and understandable were their messages?
2. PERSUASION (1-10): How effectively did they present value propositions?
3. EMPATHY (1-10): How well did they understand and address customer needs?
4. PACING (1-10): How appropriate was their conversation flow and timing?
5. OBJECTION HANDLING (1-10): How effectively did they address concerns?

FEEDBACK FORMAT:
- Provide specific scores for each dimension
- Give 2-3 concrete examples of what they did well
- Suggest 2-3 specific improvements with actionable steps
- Highlight one key learning moment from the conversation

Focus on constructive, actionable feedback that helps improve sales skills.""",
            required_fields=["conversation_transcript", "persona_name", "persona_description"],
            max_tokens=2000
        ),
        
        "system_instruction": PromptTemplate(
            name="system_instruction",
            template="""SYSTEM INSTRUCTION: {instruction_type}

{instruction_content}

CONTEXT: {context_info}

Execute this instruction while maintaining consistency with the current conversation state and user experience.""",
            required_fields=["instruction_type", "instruction_content"],
            optional_fields=["context_info"],
            max_tokens=1000
        ),
        
        "enhanced_response": PromptTemplate(
            name="enhanced_response",
            template="""ENHANCED RESPONSE GENERATION

BASE CONTEXT:
{base_context}

ENHANCEMENT REQUEST: {enhancement_type}
- {enhancement_details}

CONSTRAINTS:
- Maintain character authenticity
- Keep response natural and conversational
- {additional_constraints}

CURRENT USER INPUT: {user_input}

Generate an enhanced response that incorporates the requested improvements while staying true to the character and scenario.""",
            required_fields=["base_context", "enhancement_type", "user_input"],
            optional_fields=["enhancement_details", "additional_constraints"],
            max_tokens=2500
        )
    }
    
    def __init__(self):
        """Initialize PromptManager"""
        self.context_manager = get_context_manager()
        self.custom_templates: Dict[str, PromptTemplate] = {}
    
    def add_template(self, template: PromptTemplate) -> None:
        """Add custom prompt template"""
        self.custom_templates[template.name] = template
        logger.info(f"Added custom template: {template.name}")
    
    def get_template(self, template_name: str) -> Optional[PromptTemplate]:
        """Get template by name"""
        # Check custom templates first
        if template_name in self.custom_templates:
            return self.custom_templates[template_name]
        
        # Check default templates
        return self.TEMPLATES.get(template_name)
    
    def build_persona_context(self, persona_name: str) -> Dict[str, str]:
        """Build persona context from character profiles"""
        persona = PERSONAS.get(persona_name)
        if not persona:
            logger.warning(f"Unknown persona: {persona_name}")
            return {
                "persona_name": persona_name,
                "persona_description": f"Unknown persona: {persona_name}",
                "persona_behavior": "Act naturally and engage in conversation"
            }
        
        return {
            "persona_name": persona["name"],
            "persona_description": persona["description"],
            "persona_behavior": persona.get("behavior", ""),
            "persona_background": persona.get("background", ""),
            "persona_goals": persona.get("goals", ""),
            "persona_pain_points": persona.get("pain_points", ""),
            "persona_communication_style": persona.get("communication_style", "")
        }
    
    def build_training_context(self, session_data: Dict[str, Any] = None) -> str:
        """Build training context and objectives"""
        if not session_data:
            return "General sales training scenario focused on building rapport and understanding customer needs."
        
        objectives = session_data.get("objectives", [])
        scenario = session_data.get("scenario", "")
        focus_areas = session_data.get("focus_areas", [])
        
        context_parts = []
        
        if scenario:
            context_parts.append(f"SCENARIO: {scenario}")
        
        if objectives:
            context_parts.append(f"TRAINING OBJECTIVES:")
            for obj in objectives:
                context_parts.append(f"- {obj}")
        
        if focus_areas:
            context_parts.append(f"FOCUS AREAS:")
            for area in focus_areas:
                context_parts.append(f"- {area}")
        
        return "\n".join(context_parts) if context_parts else "General sales training scenario"
    
    def build_conversation_context(self, session_id: str = "", 
                                 include_recent: int = 5) -> str:
        """Build conversation context from recent messages"""
        try:
            # Get recent conversation context
            context_window = self.context_manager.build_context_window(include_recent)
            
            if not context_window:
                return "This is the beginning of your conversation."
            
            # Extract just the conversation history part
            if "CONVERSATION HISTORY:" in context_window:
                history_section = context_window.split("CONVERSATION HISTORY:")[1].strip()
                if history_section:
                    return f"RECENT CONVERSATION:\n{history_section}"
            
            return "This is the beginning of your conversation."
            
        except Exception as e:
            logger.warning(f"Error building conversation context: {e}")
            return "This is the beginning of your conversation."
    
    def build_sales_training_prompt(self, 
                                  user_input: str,
                                  persona_name: str,
                                  session_data: Dict[str, Any] = None,
                                  session_id: str = "") -> str:
        """Build sales training prompt"""
        
        template = self.get_template("sales_training")
        if not template:
            raise ValueError("Sales training template not found")
        
        # Build components
        persona_context = self.build_persona_context(persona_name)
        training_context = self.build_training_context(session_data)
        conversation_context = self.build_conversation_context(session_id)
        
        # Merge all context
        prompt_vars = {
            "user_input": user_input,
            "training_objectives": training_context,
            "conversation_context": conversation_context,
            **persona_context
        }
        
        # Build the prompt
        try:
            prompt = template.template.format(**prompt_vars)
            
            # Verify token count
            token_count = self.context_manager.count_tokens(prompt)
            if token_count > template.max_tokens:
                logger.warning(f"Prompt exceeds token limit: {token_count} > {template.max_tokens}")
                # Truncate conversation context if needed
                if len(conversation_context) > 500:
                    truncated_context = conversation_context[:500] + "...\n[Previous conversation truncated]"
                    prompt_vars["conversation_context"] = truncated_context
                    prompt = template.template.format(**prompt_vars)
            
            logger.debug(f"Built sales training prompt: {self.context_manager.count_tokens(prompt)} tokens")
            return prompt
            
        except KeyError as e:
            logger.error(f"Missing required field for prompt: {e}")
            raise ValueError(f"Missing required field: {e}")
    
    def build_feedback_prompt(self, 
                            conversation_transcript: str,
                            persona_name: str) -> str:
        """Build feedback analysis prompt"""
        
        template = self.get_template("feedback_analysis")
        if not template:
            raise ValueError("Feedback analysis template not found")
        
        persona_context = self.build_persona_context(persona_name)
        
        prompt_vars = {
            "conversation_transcript": conversation_transcript,
            "persona_name": persona_context["persona_name"],
            "persona_description": persona_context["persona_description"]
        }
        
        try:
            prompt = template.template.format(**prompt_vars)
            
            # Check token limit
            token_count = self.context_manager.count_tokens(prompt)
            if token_count > template.max_tokens:
                # Truncate transcript if needed
                max_transcript_tokens = template.max_tokens - 1000  # Reserve for other content
                transcript_tokens = self.context_manager.count_tokens(conversation_transcript)
                
                if transcript_tokens > max_transcript_tokens:
                    # Truncate from beginning, keep recent conversation
                    truncated = self._truncate_transcript(conversation_transcript, max_transcript_tokens)
                    prompt_vars["conversation_transcript"] = truncated
                    prompt = template.template.format(**prompt_vars)
            
            logger.debug(f"Built feedback prompt: {self.context_manager.count_tokens(prompt)} tokens")
            return prompt
            
        except KeyError as e:
            logger.error(f"Missing required field for feedback prompt: {e}")
            raise ValueError(f"Missing required field: {e}")
    
    def build_enhanced_response_prompt(self,
                                     user_input: str,
                                     enhancement_type: str,
                                     base_context: str,
                                     enhancement_details: str = "",
                                     constraints: str = "") -> str:
        """Build enhanced response generation prompt"""
        
        template = self.get_template("enhanced_response")
        if not template:
            raise ValueError("Enhanced response template not found")
        
        prompt_vars = {
            "user_input": user_input,
            "enhancement_type": enhancement_type,
            "base_context": base_context,
            "enhancement_details": enhancement_details or f"Apply {enhancement_type} enhancement",
            "additional_constraints": constraints or "None"
        }
        
        try:
            prompt = template.template.format(**prompt_vars)
            logger.debug(f"Built enhanced response prompt: {self.context_manager.count_tokens(prompt)} tokens")
            return prompt
            
        except KeyError as e:
            logger.error(f"Missing required field for enhanced response prompt: {e}")
            raise ValueError(f"Missing required field: {e}")
    
    def build_system_instruction_prompt(self,
                                      instruction_type: str,
                                      instruction_content: str,
                                      context_info: str = "") -> str:
        """Build system instruction prompt"""
        
        template = self.get_template("system_instruction")
        if not template:
            raise ValueError("System instruction template not found")
        
        prompt_vars = {
            "instruction_type": instruction_type,
            "instruction_content": instruction_content,
            "context_info": context_info or "No additional context"
        }
        
        try:
            prompt = template.template.format(**prompt_vars)
            logger.debug(f"Built system instruction prompt: {self.context_manager.count_tokens(prompt)} tokens")
            return prompt
            
        except KeyError as e:
            logger.error(f"Missing required field for system instruction prompt: {e}")
            raise ValueError(f"Missing required field: {e}")
    
    def _truncate_transcript(self, transcript: str, max_tokens: int) -> str:
        """Truncate transcript while preserving structure"""
        lines = transcript.split('\n')
        
        # Try to keep complete exchanges (USER: ... ASSISTANT: ... pairs)
        truncated_lines = []
        current_tokens = 0
        
        # Start from the end to keep most recent conversation
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            line_tokens = self.context_manager.count_tokens(line)
            
            if current_tokens + line_tokens <= max_tokens:
                truncated_lines.insert(0, line)
                current_tokens += line_tokens
            else:
                break
        
        truncated_transcript = '\n'.join(truncated_lines)
        
        # Add truncation notice if we removed content
        if len(truncated_lines) < len(lines):
            truncated_transcript = "[Earlier conversation truncated]\n\n" + truncated_transcript
        
        return truncated_transcript
    
    def optimize_prompt_length(self, prompt: str, max_tokens: int) -> str:
        """Optimize prompt to fit within token limit"""
        current_tokens = self.context_manager.count_tokens(prompt)
        
        if current_tokens <= max_tokens:
            return prompt
        
        # Try to intelligently truncate while preserving important sections
        sections = prompt.split('\n\n')
        
        # Priority order for sections (keep these first)
        priority_keywords = ['SYSTEM:', 'PERSONA:', 'USER MESSAGE:', 'TRAINING CONTEXT:']
        
        priority_sections = []
        other_sections = []
        
        for section in sections:
            is_priority = any(keyword in section for keyword in priority_keywords)
            if is_priority:
                priority_sections.append(section)
            else:
                other_sections.append(section)
        
        # Build optimized prompt
        optimized_sections = priority_sections.copy()
        used_tokens = self.context_manager.count_tokens('\n\n'.join(optimized_sections))
        
        # Add other sections until we hit the limit
        for section in other_sections:
            section_tokens = self.context_manager.count_tokens(section)
            if used_tokens + section_tokens <= max_tokens:
                optimized_sections.append(section)
                used_tokens += section_tokens
            else:
                break
        
        optimized_prompt = '\n\n'.join(optimized_sections)
        
        # Final check and truncation if needed
        if self.context_manager.count_tokens(optimized_prompt) > max_tokens:
            # Hard truncate as last resort
            tokens = self.context_manager.encoding.encode(optimized_prompt)
            truncated_tokens = tokens[:max_tokens]
            optimized_prompt = self.context_manager.encoding.decode(truncated_tokens)
        
        logger.warning(f"Optimized prompt from {current_tokens} to {self.context_manager.count_tokens(optimized_prompt)} tokens")
        return optimized_prompt
    
    def validate_prompt(self, prompt: str, template_name: str = None) -> Dict[str, Any]:
        """Validate prompt structure and content"""
        template = self.get_template(template_name) if template_name else None
        
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "token_count": self.context_manager.count_tokens(prompt),
            "estimated_response_tokens": 0
        }
        
        # Check token count
        if template and validation_result["token_count"] > template.max_tokens:
            validation_result["errors"].append(
                f"Prompt exceeds template limit: {validation_result['token_count']} > {template.max_tokens}"
            )
            validation_result["valid"] = False
        
        # Estimate response tokens needed
        if "sales_training" in prompt.lower():
            validation_result["estimated_response_tokens"] = 200
        elif "feedback" in prompt.lower():
            validation_result["estimated_response_tokens"] = 400
        else:
            validation_result["estimated_response_tokens"] = 150
        
        # Check for required sections
        required_sections = ["USER MESSAGE:", "PERSONA"]
        for section in required_sections:
            if section not in prompt:
                validation_result["warnings"].append(f"Missing recommended section: {section}")
        
        # Check prompt structure
        if not prompt.strip():
            validation_result["errors"].append("Empty prompt")
            validation_result["valid"] = False
        
        return validation_result


# Global instance
_prompt_manager = None

def get_prompt_manager() -> PromptManager:
    """Get singleton PromptManager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager