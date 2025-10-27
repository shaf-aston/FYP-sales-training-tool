"""
Post-processing service for response validation, refinement, and quality control
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ResponseQuality(Enum):
    """Response quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    REJECTED = "rejected"

@dataclass
class ProcessedResponse:
    """Container for post-processed response"""
    final_text: str
    quality_score: float
    safety_passed: bool
    persona_alignment: float
    tone_score: float
    validation_results: Dict
    processing_time: float

class PostProcessingService:
    """Service for post-processing AI responses"""
    
    def __init__(self):
        self.safety_filter = SafetyFilter()
        self.response_ranker = ResponseRanker()
        self.persona_refiner = PersonaRefiner()
        self.tone_adjuster = ToneAdjuster()
        self.validator = ResponseValidator()
        self.fallback_engine = FallbackEngine()
    
    async def process_response(self, raw_response: str, context: Dict, 
                             persona_attributes: Dict, user_profile: Dict = None) -> ProcessedResponse:
        """Process AI response through post-processing pipeline"""
        start_time = datetime.now().timestamp()
        
        # Step 1: Safety and compliance check
        safety_result = self.safety_filter.check_safety(raw_response)
        if not safety_result['passed']:
            logger.warning(f"Response failed safety check: {safety_result['reason']}")
            fallback_response = self.fallback_engine.get_fallback(context, persona_attributes)
            return self._create_fallback_result(fallback_response, safety_result, start_time)
        
        # Step 2: Response ranking and selection (if multiple responses)
        selected_response = self.response_ranker.select_best([raw_response], context, persona_attributes)
        
        # Step 3: Persona-specific refinement
        refined_response = self.persona_refiner.refine_for_persona(selected_response, persona_attributes)
        
        # Step 4: Tone and clarity adjustment
        adjusted_response = self.tone_adjuster.adjust_tone(refined_response, context, persona_attributes)
        
        # Step 5: Final validation
        validation_results = self.validator.validate_final_response(adjusted_response, context)
        
        if not validation_results['valid']:
            logger.warning(f"Response failed final validation: {validation_results['reason']}")
            fallback_response = self.fallback_engine.get_fallback(context, persona_attributes)
            return self._create_fallback_result(fallback_response, validation_results, start_time)
        
        processing_time = datetime.now().timestamp() - start_time
        
        return ProcessedResponse(
            final_text=adjusted_response,
            quality_score=validation_results['quality_score'],
            safety_passed=True,
            persona_alignment=validation_results['persona_alignment'],
            tone_score=validation_results['tone_score'],
            validation_results=validation_results,
            processing_time=processing_time
        )
    
    def _create_fallback_result(self, fallback_response: str, failure_info: Dict, start_time: float) -> ProcessedResponse:
        """Create result for fallback responses"""
        processing_time = datetime.now().timestamp() - start_time
        
        return ProcessedResponse(
            final_text=fallback_response,
            quality_score=0.6,  # Fallback responses get moderate score
            safety_passed=True,  # Fallbacks are pre-approved
            persona_alignment=0.7,
            tone_score=0.7,
            validation_results={'fallback_used': True, 'reason': failure_info},
            processing_time=processing_time
        )

class SafetyFilter:
    """Filter responses for safety and compliance"""
    
    def __init__(self):
        # Prohibited content patterns
        self.prohibited_patterns = [
            r'personal\s+information',
            r'medical\s+advice',
            r'financial\s+advice',
            r'legal\s+advice',
            r'inappropriate\s+content',
            r'discrimination',
            r'harassment'
        ]
        
        # Sales compliance keywords
        self.compliance_violations = [
            'guaranteed results', 'no risk', 'get rich quick', 'limited time only',
            'act now or lose forever', 'exclusive deal', 'secret formula'
        ]
    
    def check_safety(self, response: str) -> Dict:
        """Check if response meets safety and compliance standards"""
        if not response:
            return {'passed': False, 'reason': 'empty_response'}
        
        response_lower = response.lower()
        
        # Check for prohibited content
        for pattern in self.prohibited_patterns:
            if re.search(pattern, response_lower):
                return {
                    'passed': False, 
                    'reason': 'prohibited_content',
                    'pattern': pattern
                }
        
        # Check sales compliance
        for violation in self.compliance_violations:
            if violation in response_lower:
                return {
                    'passed': False,
                    'reason': 'compliance_violation',
                    'violation': violation
                }
        
        # Check length constraints
        if len(response) > 2000:
            return {'passed': False, 'reason': 'too_long'}
        
        if len(response) < 10:
            return {'passed': False, 'reason': 'too_short'}
        
        return {'passed': True, 'reason': 'passed_all_checks'}

class ResponseRanker:
    """Rank and select best responses when multiple options available"""
    
    def select_best(self, responses: List[str], context: Dict, persona_attributes: Dict) -> str:
        """Select the best response from available options"""
        if len(responses) == 1:
            return responses[0]
        
        scored_responses = []
        
        for response in responses:
            score = self._calculate_response_score(response, context, persona_attributes)
            scored_responses.append((response, score))
        
        # Sort by score and return best
        scored_responses.sort(key=lambda x: x[1], reverse=True)
        return scored_responses[0][0]
    
    def _calculate_response_score(self, response: str, context: Dict, persona_attributes: Dict) -> float:
        """Calculate quality score for a response"""
        score = 0.0
        
        # Length appropriateness (50-500 words ideal for sales)
        word_count = len(response.split())
        if 50 <= word_count <= 500:
            score += 2.0
        elif 20 <= word_count < 50 or 500 < word_count <= 800:
            score += 1.0
        
        # Persona alignment
        persona_score = self._check_persona_alignment(response, persona_attributes)
        score += persona_score
        
        # Context relevance
        context_score = self._check_context_relevance(response, context)
        score += context_score
        
        # Sales effectiveness indicators
        sales_score = self._check_sales_effectiveness(response)
        score += sales_score
        
        return score
    
    def _check_persona_alignment(self, response: str, persona_attributes: Dict) -> float:
        """Check how well response aligns with persona"""
        primary_persona = persona_attributes.get('primary_persona', 'amiable')
        response_lower = response.lower()
        
        persona_keywords = {
            'analytical': ['data', 'statistics', 'research', 'facts', 'details'],
            'driver': ['results', 'efficient', 'bottom line', 'quickly', 'direct'],
            'expressive': ['people', 'story', 'experience', 'relationship', 'social'],
            'amiable': ['comfortable', 'support', 'help', 'care', 'gentle'],
            'skeptical': ['understand', 'concerns', 'proof', 'guarantee', 'evidence']
        }
        
        keywords = persona_keywords.get(primary_persona, [])
        matches = sum(1 for keyword in keywords if keyword in response_lower)
        
        return min(matches * 0.5, 2.0)
    
    def _check_context_relevance(self, response: str, context: Dict) -> float:
        """Check context relevance of response"""
        conversation_stage = context.get('conversation_stage', 'discovery')
        response_lower = response.lower()
        
        stage_keywords = {
            'opening': ['hello', 'introduction', 'name', 'pleasure', 'meet'],
            'discovery': ['tell me', 'understand', 'learn', 'discover', 'needs'],
            'presentation': ['solution', 'features', 'benefits', 'help you', 'offer'],
            'handling_objections': ['understand your concern', 'however', 'actually', 'consider'],
            'closing': ['ready', 'move forward', 'next steps', 'start', 'decision']
        }
        
        keywords = stage_keywords.get(conversation_stage, [])
        matches = sum(1 for keyword in keywords if keyword in response_lower)
        
        return min(matches * 0.3, 1.5)
    
    def _check_sales_effectiveness(self, response: str) -> float:
        """Check sales effectiveness indicators"""
        response_lower = response.lower()
        effectiveness_score = 0.0
        
        # Check for questions (good for engagement)
        if '?' in response:
            effectiveness_score += 0.5
        
        # Check for benefits language
        benefit_words = ['benefit', 'advantage', 'help you', 'save', 'improve', 'increase']
        matches = sum(1 for word in benefit_words if word in response_lower)
        effectiveness_score += min(matches * 0.2, 1.0)
        
        # Check for empathy indicators
        empathy_words = ['understand', 'appreciate', 'realize', 'see your point']
        matches = sum(1 for phrase in empathy_words if phrase in response_lower)
        effectiveness_score += min(matches * 0.3, 1.0)
        
        return effectiveness_score

class PersonaRefiner:
    """Refine responses to match specific persona requirements"""
    
    def refine_for_persona(self, response: str, persona_attributes: Dict) -> str:
        """Refine response to better match persona"""
        primary_persona = persona_attributes.get('primary_persona', 'amiable')
        
        refinement_methods = {
            'analytical': self._refine_for_analytical,
            'driver': self._refine_for_driver,
            'expressive': self._refine_for_expressive,
            'amiable': self._refine_for_amiable,
            'skeptical': self._refine_for_skeptical
        }
        
        refine_method = refinement_methods.get(primary_persona, self._refine_for_amiable)
        return refine_method(response, persona_attributes)
    
    def _refine_for_analytical(self, response: str, attributes: Dict) -> str:
        """Refine response for analytical persona"""
        # Add data-driven language if missing
        if not any(word in response.lower() for word in ['data', 'statistics', 'research', 'study']):
            # Insert analytical language naturally
            response = response.replace('This helps', 'Research shows this helps')
            response = response.replace('many people', 'studies indicate that people')
        
        return response
    
    def _refine_for_driver(self, response: str, attributes: Dict) -> str:
        """Refine response for driver persona"""
        # Make more direct and results-focused
        response = response.replace('I think', 'The result is')
        response = response.replace('maybe we could', 'we will')
        response = response.replace('possibly', 'definitely')
        
        return response
    
    def _refine_for_expressive(self, response: str, attributes: Dict) -> str:
        """Refine response for expressive persona"""
        # Add relationship and social elements
        if 'people' not in response.lower():
            response = response.replace('This solution', 'People love this solution because it')
        
        return response
    
    def _refine_for_amiable(self, response: str, attributes: Dict) -> str:
        """Refine response for amiable persona"""
        # Add supportive and caring language
        response = response.replace('You should', 'You might want to consider')
        response = response.replace('You need to', 'It would be helpful if you')
        
        return response
    
    def _refine_for_skeptical(self, response: str, attributes: Dict) -> str:
        """Refine response for skeptical persona"""
        # Add proof and evidence elements
        if not any(word in response.lower() for word in ['proof', 'evidence', 'guarantee', 'proven']):
            response = response.replace('This works', 'This proven approach works')
        
        return response

class ToneAdjuster:
    """Adjust tone and clarity of responses"""
    
    def adjust_tone(self, response: str, context: Dict, persona_attributes: Dict) -> str:
        """Adjust response tone for clarity and appropriateness"""
        emotional_tone = context.get('emotional_tone', 'neutral')
        
        # Adjust based on emotional context
        if emotional_tone == 'negative':
            response = self._add_empathy(response)
        elif emotional_tone == 'positive':
            response = self._maintain_enthusiasm(response)
        
        # Ensure professional tone
        response = self._ensure_professional_tone(response)
        
        # Improve clarity
        response = self._improve_clarity(response)
        
        return response
    
    def _add_empathy(self, response: str) -> str:
        """Add empathetic language for negative emotions"""
        empathy_starters = [
            "I understand your concerns. ",
            "I can see why you'd feel that way. ",
            "That's a valid point. "
        ]
        
        # Add empathy if not already present
        if not any(phrase in response for phrase in ['understand', 'see your point', 'appreciate']):
            response = empathy_starters[0] + response
        
        return response
    
    def _maintain_enthusiasm(self, response: str) -> str:
        """Maintain appropriate enthusiasm for positive emotions"""
        # Ensure response matches positive energy without being excessive
        if not any(word in response.lower() for word in ['great', 'excellent', 'wonderful', 'fantastic']):
            response = response.replace('good', 'great')
        
        return response
    
    def _ensure_professional_tone(self, response: str) -> str:
        """Ensure professional sales tone"""
        # Replace casual language
        replacements = {
            ' gonna ': ' going to ',
            ' wanna ': ' want to ',
            ' gotta ': ' need to ',
            'yeah': 'yes',
            'nah': 'no',
            'cool': 'excellent'
        }
        
        for casual, professional in replacements.items():
            response = response.replace(casual, professional)
        
        return response
    
    def _improve_clarity(self, response: str) -> str:
        """Improve response clarity"""
        # Break up long sentences
        sentences = response.split('. ')
        
        improved_sentences = []
        for sentence in sentences:
            # Split very long sentences
            if len(sentence.split()) > 25:
                # Find natural break point
                words = sentence.split()
                mid_point = len(words) // 2
                
                # Look for conjunction near midpoint
                for i in range(max(mid_point - 5, 0), min(mid_point + 5, len(words))):
                    if words[i].lower() in ['and', 'but', 'because', 'however', 'while']:
                        first_part = ' '.join(words[:i])
                        second_part = ' '.join(words[i+1:])
                        improved_sentences.extend([first_part, second_part])
                        break
                else:
                    improved_sentences.append(sentence)
            else:
                improved_sentences.append(sentence)
        
        return '. '.join(improved_sentences)

class ResponseValidator:
    """Final validation of processed responses"""
    
    def validate_final_response(self, response: str, context: Dict) -> Dict:
        """Perform final validation on processed response"""
        validation_result = {
            'valid': True,
            'quality_score': 0.0,
            'persona_alignment': 0.0,
            'tone_score': 0.0,
            'issues': []
        }
        
        # Check basic requirements
        if not response or len(response.strip()) < 10:
            validation_result['valid'] = False
            validation_result['issues'].append('response_too_short')
            return validation_result
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(response, context)
        validation_result['quality_score'] = quality_score
        
        # Calculate persona alignment
        persona_alignment = self._calculate_persona_alignment(response, context)
        validation_result['persona_alignment'] = persona_alignment
        
        # Calculate tone score
        tone_score = self._calculate_tone_score(response, context)
        validation_result['tone_score'] = tone_score
        
        # Determine if response passes minimum thresholds
        if quality_score < 0.5:
            validation_result['valid'] = False
            validation_result['issues'].append('low_quality_score')
        
        validation_result['reason'] = 'passed_validation' if validation_result['valid'] else 'failed_validation'
        
        return validation_result
    
    def _calculate_quality_score(self, response: str, context: Dict) -> float:
        """Calculate overall quality score"""
        score = 0.0
        
        # Length appropriateness
        word_count = len(response.split())
        if 30 <= word_count <= 200:
            score += 0.3
        elif 10 <= word_count < 30 or 200 < word_count <= 400:
            score += 0.2
        
        # Grammatical indicators (simple checks)
        if response.count('.') > 0:  # Has sentences
            score += 0.1
        
        if response.count('?') > 0:  # Has questions (good for engagement)
            score += 0.1
        
        # Professional language indicators
        professional_indicators = ['however', 'therefore', 'additionally', 'furthermore', 'specifically']
        matches = sum(1 for indicator in professional_indicators if indicator in response.lower())
        score += min(matches * 0.1, 0.3)
        
        return min(score, 1.0)
    
    def _calculate_persona_alignment(self, response: str, context: Dict) -> float:
        """Calculate persona alignment score"""
        # Placeholder - in full implementation, this would check against persona requirements
        return 0.8
    
    def _calculate_tone_score(self, response: str, context: Dict) -> float:
        """Calculate tone appropriateness score"""
        # Placeholder - in full implementation, this would analyze tone matching
        return 0.8

class FallbackEngine:
    """Generate fallback responses when AI responses fail validation"""
    
    def __init__(self):
        self.fallback_templates = {
            'general': [
                "I appreciate your question. Let me make sure I understand what you're looking for.",
                "That's a great point. Can you tell me a bit more about your specific needs?",
                "I want to make sure I give you the most helpful information. What's most important to you right now?"
            ],
            'analytical': [
                "Let me gather some specific information that would be most relevant to your situation.",
                "I want to provide you with the most accurate details. What specific data would be most helpful?",
                "That's an important consideration. Let me address that with some concrete information."
            ],
            'driver': [
                "Let me get right to the point about what this means for you.",
                "I'll give you the bottom line on this.",
                "Here's what you need to know to move forward."
            ],
            'expressive': [
                "I love that question! Let me share something that might really resonate with you.",
                "That reminds me of other people who've asked similar questions.",
                "I think you'll find this interesting based on what others have experienced."
            ],
            'amiable': [
                "I want to make sure you feel comfortable with everything we discuss.",
                "Let me help you understand this in a way that feels right for you.",
                "I'm here to support you in making the best decision for your needs."
            ],
            'skeptical': [
                "That's a very valid concern, and I can understand why you'd want to know more.",
                "I appreciate your thoroughness in asking about this.",
                "Let me address that concern with some concrete information."
            ]
        }
    
    def get_fallback(self, context: Dict, persona_attributes: Dict) -> str:
        """Get appropriate fallback response"""
        primary_persona = persona_attributes.get('primary_persona', 'general')
        
        # Get templates for persona
        templates = self.fallback_templates.get(primary_persona, self.fallback_templates['general'])
        
        # Select template based on context
        conversation_stage = context.get('conversation_stage', 'discovery')
        
        # Simple selection logic - in production, this would be more sophisticated
        if conversation_stage == 'opening':
            return templates[0]
        elif conversation_stage in ['discovery', 'presentation']:
            return templates[1] if len(templates) > 1 else templates[0]
        else:
            return templates[-1]

# Global post-processing service instance
postprocessing_service = PostProcessingService()