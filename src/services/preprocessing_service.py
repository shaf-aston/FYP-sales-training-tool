"""
Preprocessing service for parallel text processing, persona extraction, and context building
"""
import re
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
import concurrent.futures
from enum import Enum

logger = logging.getLogger(__name__)

class PersonaType(Enum):
    """Prospect persona types"""
    ANALYTICAL = "analytical"
    DRIVER = "driver"
    EXPRESSIVE = "expressive"
    AMIABLE = "amiable"
    SKEPTICAL = "skeptical"

@dataclass
class ProcessedInput:
    """Container for processed user input"""
    cleaned_text: str
    persona_attributes: Dict[str, Any]
    context_metadata: Dict[str, Any]
    processing_time: float
    confidence_score: float

class PreprocessingService:
    """Service for parallel preprocessing of user inputs"""
    
    def __init__(self):
        self.text_cleaners = TextCleaner()
        self.persona_extractor = PersonaExtractor()
        self.context_builder = ContextBuilder()
        self.metadata_assembler = MetadataAssembler()
    
    async def process_input(self, user_input: str, conversation_history: List[Dict], 
                          user_profile: Dict = None) -> ProcessedInput:
        """Process user input through parallel preprocessing pipeline"""
        start_time = datetime.now().timestamp()
        
        # Run preprocessing tasks in parallel
        tasks = [
            self._clean_text(user_input),
            self._extract_persona(user_input, conversation_history),
            self._build_context(user_input, conversation_history, user_profile),
            self._assemble_metadata(user_input, conversation_history, user_profile)
        ]
        
        results = await asyncio.gather(*tasks)
        cleaned_text, persona_attributes, context_metadata, additional_metadata = results
        
        # Combine metadata
        final_metadata = {**context_metadata, **additional_metadata}
        
        processing_time = datetime.now().timestamp() - start_time
        confidence_score = self._calculate_confidence(results)
        
        return ProcessedInput(
            cleaned_text=cleaned_text,
            persona_attributes=persona_attributes,
            context_metadata=final_metadata,
            processing_time=processing_time,
            confidence_score=confidence_score
        )
    
    async def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.text_cleaners.clean, text
        )
    
    async def _extract_persona(self, text: str, history: List[Dict]) -> Dict[str, Any]:
        """Extract persona attributes from text"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.persona_extractor.extract, text, history
        )
    
    async def _build_context(self, text: str, history: List[Dict], profile: Dict) -> Dict[str, Any]:
        """Build context metadata"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.context_builder.build, text, history, profile
        )
    
    async def _assemble_metadata(self, text: str, history: List[Dict], profile: Dict) -> Dict[str, Any]:
        """Assemble additional metadata"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.metadata_assembler.assemble, text, history, profile
        )
    
    def _calculate_confidence(self, results: List[Any]) -> float:
        """Calculate overall processing confidence score"""
        # Simple confidence calculation based on processing success
        confidence = 1.0
        
        # Reduce confidence if any component failed
        for result in results:
            if not result:
                confidence *= 0.8
        
        return min(confidence, 1.0)

class TextCleaner:
    """Text cleaning and normalization component"""
    
    def __init__(self):
        self.patterns = {
            'extra_spaces': re.compile(r'\s+'),
            'special_chars': re.compile(r'[^\w\s\.\!\?\,\-\']'),
            'repeated_punctuation': re.compile(r'([\.!\?]){2,}'),
            'url_pattern': re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'),
            'email_pattern': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        }
    
    def clean(self, text: str) -> str:
        """Clean and normalize text input"""
        if not text:
            return ""
        
        # Convert to lowercase for processing (preserve original case in result)
        original_text = text
        cleaned = text.strip()
        
        # Remove URLs and emails
        cleaned = self.patterns['url_pattern'].sub('[URL]', cleaned)
        cleaned = self.patterns['email_pattern'].sub('[EMAIL]', cleaned)
        
        # Clean repeated punctuation
        cleaned = self.patterns['repeated_punctuation'].sub(r'\1', cleaned)
        
        # Remove excessive special characters but keep basic punctuation
        cleaned = self.patterns['special_chars'].sub(' ', cleaned)
        
        # Normalize whitespace
        cleaned = self.patterns['extra_spaces'].sub(' ', cleaned)
        
        # Basic typo correction (simple cases)
        cleaned = self._basic_typo_correction(cleaned)
        
        return cleaned.strip()
    
    def _basic_typo_correction(self, text: str) -> str:
        """Basic typo correction for common sales terms"""
        corrections = {
            'defintely': 'definitely',
            'recieve': 'receive',
            'seperate': 'separate',
            'occurence': 'occurrence',
            'bussiness': 'business',
            'recomend': 'recommend',
            'accomodate': 'accommodate'
        }
        
        words = text.split()
        corrected_words = []
        
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in corrections:
                # Preserve original punctuation
                corrected_word = word.replace(clean_word, corrections[clean_word])
                corrected_words.append(corrected_word)
            else:
                corrected_words.append(word)
        
        return ' '.join(corrected_words)

class PersonaExtractor:
    """Extract prospect persona attributes from text"""
    
    def __init__(self):
        self.persona_indicators = {
            PersonaType.ANALYTICAL: {
                'keywords': ['data', 'statistics', 'numbers', 'research', 'analysis', 'details', 'specifics'],
                'phrases': ['show me the data', 'what are the numbers', 'i need details', 'can you prove'],
                'patterns': [r'what.*percentage', r'how.*exactly', r'prove.*that']
            },
            PersonaType.DRIVER: {
                'keywords': ['quick', 'fast', 'bottom line', 'results', 'efficient', 'time', 'deadline'],
                'phrases': ['get to the point', 'bottom line', 'how much', 'when can we start'],
                'patterns': [r'how.*long', r'when.*start', r'bottom.*line']
            },
            PersonaType.EXPRESSIVE: {
                'keywords': ['people', 'team', 'story', 'experience', 'relationship', 'social', 'community'],
                'phrases': ['tell me about', 'who else uses', 'success stories', 'what do people say'],
                'patterns': [r'other.*people', r'success.*stor', r'what.*others']
            },
            PersonaType.AMIABLE: {
                'keywords': ['comfortable', 'trust', 'relationship', 'support', 'help', 'care', 'gentle'],
                'phrases': ['i feel comfortable', 'i trust', 'will you help', 'take care of'],
                'patterns': [r'feel.*comfortable', r'trust.*you', r'help.*me']
            },
            PersonaType.SKEPTICAL: {
                'keywords': ['doubt', 'prove', 'really', 'actually', 'sure', 'guarantee', 'risk'],
                'phrases': ['i doubt that', 'are you sure', 'prove it', 'what if it fails'],
                'patterns': [r'doubt.*that', r'really.*work', r'what.*if.*fail']
            }
        }
    
    def extract(self, text: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Extract persona attributes from text and conversation history"""
        if not text:
            return {}
        
        text_lower = text.lower()
        persona_scores = {}
        
        # Analyze current message
        for persona_type, indicators in self.persona_indicators.items():
            score = 0.0
            
            # Check keywords
            for keyword in indicators['keywords']:
                if keyword in text_lower:
                    score += 1.0
            
            # Check phrases
            for phrase in indicators['phrases']:
                if phrase in text_lower:
                    score += 2.0
            
            # Check patterns
            for pattern in indicators['patterns']:
                if re.search(pattern, text_lower):
                    score += 1.5
            
            persona_scores[persona_type.value] = score
        
        # Analyze conversation history for persona consistency
        history_scores = self._analyze_conversation_history(conversation_history)
        
        # Combine current and historical scores
        combined_scores = {}
        for persona in persona_scores:
            current_score = persona_scores[persona]
            historical_score = history_scores.get(persona, 0.0)
            combined_scores[persona] = (current_score * 0.7) + (historical_score * 0.3)
        
        # Determine primary persona
        primary_persona = max(combined_scores, key=combined_scores.get) if combined_scores else PersonaType.AMIABLE.value
        
        return {
            'primary_persona': primary_persona,
            'persona_scores': combined_scores,
            'confidence': max(combined_scores.values()) / 10.0 if combined_scores else 0.5,
            'behavioral_traits': self._extract_behavioral_traits(text_lower),
            'communication_style': self._determine_communication_style(text_lower)
        }
    
    def _analyze_conversation_history(self, history: List[Dict]) -> Dict[str, float]:
        """Analyze conversation history for persona patterns"""
        history_scores = {}
        
        if not history:
            return history_scores
        
        # Analyze last few exchanges
        recent_messages = history[-3:] if len(history) > 3 else history
        
        for exchange in recent_messages:
            user_message = exchange.get('user', '').lower()
            if user_message:
                # Run persona extraction on historical message
                for persona_type, indicators in self.persona_indicators.items():
                    score = 0.0
                    for keyword in indicators['keywords']:
                        if keyword in user_message:
                            score += 0.5
                    
                    persona_key = persona_type.value
                    history_scores[persona_key] = history_scores.get(persona_key, 0.0) + score
        
        return history_scores
    
    def _extract_behavioral_traits(self, text: str) -> List[str]:
        """Extract behavioral traits from text"""
        traits = []
        
        trait_indicators = {
            'direct': ['directly', 'straight', 'frank', 'blunt'],
            'detailed': ['detailed', 'specific', 'thorough', 'comprehensive'],
            'relationship_focused': ['together', 'relationship', 'partnership', 'collaboration'],
            'results_oriented': ['results', 'outcomes', 'achievement', 'success'],
            'cautious': ['careful', 'cautious', 'considered', 'thoughtful'],
            'enthusiastic': ['excited', 'great', 'amazing', 'fantastic']
        }
        
        for trait, keywords in trait_indicators.items():
            if any(keyword in text for keyword in keywords):
                traits.append(trait)
        
        return traits
    
    def _determine_communication_style(self, text: str) -> str:
        """Determine preferred communication style"""
        if len(text.split()) < 5:
            return 'concise'
        elif any(word in text for word in ['detail', 'explain', 'tell me more']):
            return 'detailed'
        elif '?' in text:
            return 'inquisitive'
        elif any(word in text for word in ['quick', 'fast', 'brief']):
            return 'brief'
        else:
            return 'balanced'

class ContextBuilder:
    """Build contextual metadata for conversations"""
    
    def build(self, text: str, history: List[Dict], profile: Dict) -> Dict[str, Any]:
        """Build context metadata from input and history"""
        context = {
            'message_length': len(text.split()) if text else 0,
            'conversation_stage': self._determine_conversation_stage(history),
            'urgency_level': self._assess_urgency(text),
            'emotional_tone': self._detect_emotional_tone(text),
            'sales_intent': self._detect_sales_intent(text),
            'question_type': self._classify_question_type(text),
            'engagement_level': self._assess_engagement(text, history)
        }
        
        return context
    
    def _determine_conversation_stage(self, history: List[Dict]) -> str:
        """Determine current stage of sales conversation"""
        if not history:
            return 'opening'
        elif len(history) < 3:
            return 'discovery'
        elif len(history) < 7:
            return 'presentation'
        elif len(history) < 10:
            return 'handling_objections'
        else:
            return 'closing'
    
    def _assess_urgency(self, text: str) -> str:
        """Assess urgency level from text"""
        if not text:
            return 'low'
        
        text_lower = text.lower()
        urgent_keywords = ['urgent', 'immediately', 'asap', 'quickly', 'deadline', 'rush']
        
        if any(keyword in text_lower for keyword in urgent_keywords):
            return 'high'
        elif any(word in text_lower for word in ['soon', 'fast', 'quick']):
            return 'medium'
        else:
            return 'low'
    
    def _detect_emotional_tone(self, text: str) -> str:
        """Detect emotional tone in text"""
        if not text:
            return 'neutral'
        
        text_lower = text.lower()
        
        positive_words = ['great', 'excellent', 'amazing', 'fantastic', 'love', 'excited']
        negative_words = ['disappointed', 'frustrated', 'angry', 'upset', 'concerned', 'worried']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _detect_sales_intent(self, text: str) -> str:
        """Detect sales-related intent"""
        if not text:
            return 'unknown'
        
        text_lower = text.lower()
        
        intent_patterns = {
            'price_inquiry': ['cost', 'price', 'expensive', 'budget', 'afford'],
            'feature_inquiry': ['features', 'capabilities', 'what does', 'how does'],
            'comparison': ['compare', 'versus', 'difference', 'better than'],
            'objection': ['but', 'however', 'concern', 'worried', 'doubt'],
            'interest': ['interested', 'want to know', 'tell me more', 'sounds good'],
            'closing_signal': ['ready', 'start', 'sign up', 'proceed', 'next steps']
        }
        
        for intent, keywords in intent_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent
        
        return 'general_inquiry'
    
    def _classify_question_type(self, text: str) -> str:
        """Classify the type of question being asked"""
        if not text or '?' not in text:
            return 'statement'
        
        text_lower = text.lower()
        
        if text_lower.startswith(('what', 'how', 'when', 'where', 'why', 'which')):
            return 'open_ended'
        elif text_lower.startswith(('is', 'are', 'can', 'do', 'does', 'will', 'would')):
            return 'closed_ended'
        else:
            return 'clarification'
    
    def _assess_engagement(self, text: str, history: List[Dict]) -> str:
        """Assess user engagement level"""
        if not text:
            return 'low'
        
        # Length-based assessment
        word_count = len(text.split())
        
        # Question-based assessment
        question_count = text.count('?')
        
        # Historical engagement
        avg_history_length = 0
        if history:
            total_words = sum(len(exchange.get('user', '').split()) for exchange in history)
            avg_history_length = total_words / len(history)
        
        # Calculate engagement score
        engagement_score = 0
        
        if word_count > 10:
            engagement_score += 2
        elif word_count > 5:
            engagement_score += 1
        
        if question_count > 0:
            engagement_score += 1
        
        if word_count > avg_history_length:
            engagement_score += 1
        
        if engagement_score >= 3:
            return 'high'
        elif engagement_score >= 1:
            return 'medium'
        else:
            return 'low'

class MetadataAssembler:
    """Assemble comprehensive metadata for processed inputs"""
    
    def assemble(self, text: str, history: List[Dict], profile: Dict) -> Dict[str, Any]:
        """Assemble metadata from various sources"""
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'input_length': len(text) if text else 0,
            'word_count': len(text.split()) if text else 0,
            'conversation_turn': len(history) + 1 if history else 1,
            'has_profile': bool(profile),
            'processing_version': '1.0'
        }
        
        # Add profile-based metadata
        if profile:
            metadata.update({
                'user_experience_level': profile.get('experience_level', 'unknown'),
                'user_preferences': profile.get('preferences', {}),
                'user_goals': profile.get('goals', [])
            })
        
        return metadata

# Global preprocessing service instance
preprocessing_service = PreprocessingService()