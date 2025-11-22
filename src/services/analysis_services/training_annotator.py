"""
Training Annotation Component
Generates intelligent training feedback and improvement suggestions
"""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
import re

from .audio_analysis_models import (
    TimestampedSegment, TrainingAnnotation, Speaker, RolePlayBlock
)

logger = logging.getLogger(__name__)

class TrainingAnnotator:
    """
    Specialized component for generating training annotations
    Provides feedback and improvement suggestions for sales training
    """
    
    def __init__(self):
        """Initialize the training annotator"""
        self.annotation_rules = {
            'questioning_technique': {
                'patterns': [r'\b(what|how|when|where|why)\b.*\?', r'tell me about', r'can you explain'],
                'positive_feedback': "Excellent use of open-ended questioning to gather information",
                'improvement_suggestions': [
                    "Consider asking more probing follow-up questions",
                    "Try using the 'funnel technique' - broad to specific questions"
                ],
                'effectiveness_boost': 0.8
            },
            'active_listening': {
                'patterns': [r'\b(i understand|i see|that makes sense|i hear you)\b'],
                'positive_feedback': "Good demonstration of active listening skills",
                'improvement_suggestions': [
                    "Consider paraphrasing what you heard to confirm understanding",
                    "Use more empathetic responses to build rapport"
                ],
                'effectiveness_boost': 0.7
            },
            'benefit_presentation': {
                'patterns': [r'\b(benefit|advantage|save|increase|improve|help you)\b'],
                'positive_feedback': "Strong focus on benefits rather than just features",
                'improvement_suggestions': [
                    "Connect benefits more directly to customer's specific needs",
                    "Use concrete examples and quantify the benefits when possible"
                ],
                'effectiveness_boost': 0.9
            },
            'objection_handling': {
                'patterns': [r'\b(understand your concern|appreciate|i see your point)\b'],
                'positive_feedback': "Professional approach to handling objections",
                'improvement_suggestions': [
                    "Use the 'feel, felt, found' technique for objection handling",
                    "Address the underlying concern, not just the surface objection"
                ],
                'effectiveness_boost': 0.8
            },
            'closing_attempt': {
                'patterns': [r'\b(next step|move forward|get started|ready to|sign up)\b'],
                'positive_feedback': "Good attempt at moving the conversation forward",
                'improvement_suggestions': [
                    "Use trial closes throughout the conversation, not just at the end",
                    "Create urgency by highlighting limited-time benefits"
                ],
                'effectiveness_boost': 0.85
            },
            'rapport_building': {
                'patterns': [r'\b(great|excellent|exactly|perfect|i love that)\b'],
                'positive_feedback': "Nice rapport building through positive reinforcement",
                'improvement_suggestions': [
                    "Find more personal connection points with the prospect",
                    "Mirror the prospect's communication style and pace"
                ],
                'effectiveness_boost': 0.6
            }
        }
        
        self.negative_patterns = {
            'talking_too_much': {
                'min_words': 50,
                'feedback': "Consider allowing more space for the prospect to talk",
                'suggestions': ["Use the 80/20 rule - prospect talks 80%, you talk 20%"]
            },
            'feature_dumping': {
                'patterns': [r'\b(feature|specification|technical|version)\b'],
                'threshold': 3,
                'feedback': "Avoid feature dumping - focus on benefits instead",
                'suggestions': ["For every feature mentioned, explain the benefit to the customer"]
            },
            'weak_language': {
                'patterns': [r'\b(maybe|might|could possibly|i think|sort of)\b'],
                'threshold': 2,
                'feedback': "Use more confident language to build trust",
                'suggestions': ["Replace tentative language with confident statements"]
            }
        }
        
        logger.info("✅ Training Annotator initialized")
    
    def generate_annotations(self, segments: List[TimestampedSegment], 
                           speakers: List[Speaker],
                           roleplay_blocks: List[RolePlayBlock]) -> List[TrainingAnnotation]:
        """
        Generate comprehensive training annotations
        
        Args:
            segments: Conversation segments
            speakers: Identified speakers
            roleplay_blocks: Role-play analysis results
            
        Returns:
            List of training annotations with feedback
        """
        try:
            if not segments:
                return []
            
            logger.info(f"Generating training annotations for {len(segments)} segments")
            
            annotations = []
            
            salesperson_segments = self._get_salesperson_segments(segments, speakers)
            
            if not salesperson_segments:
                logger.warning("No salesperson identified - generating generic annotations")
                salesperson_segments = segments
            
            positive_annotations = self._generate_positive_annotations(salesperson_segments)
            annotations.extend(positive_annotations)
            
            improvement_annotations = self._generate_improvement_annotations(salesperson_segments)
            annotations.extend(improvement_annotations)
            
            phase_annotations = self._generate_phase_annotations(roleplay_blocks)
            annotations.extend(phase_annotations)
            
            logger.info(f"Generated {len(annotations)} training annotations")
            return annotations
            
        except Exception as e:
            logger.error(f"Annotation generation failed: {e}")
            return []
    
    def _get_salesperson_segments(self, segments: List[TimestampedSegment], 
                                speakers: List[Speaker]) -> List[TimestampedSegment]:
        """Extract segments spoken by the salesperson"""
        salesperson_speakers = [s for s in speakers if s.role.value == 'salesperson']
        
        if not salesperson_speakers:
            return []
        
        salesperson_id = salesperson_speakers[0].id
        return [s for s in segments if s.speaker_id == salesperson_id]
    
    def _generate_positive_annotations(self, segments: List[TimestampedSegment]) -> List[TrainingAnnotation]:
        """Generate positive feedback annotations"""
        annotations = []
        annotation_id = 0
        
        for segment in segments:
            text_lower = segment.text.lower()
            
            for technique, rule in self.annotation_rules.items():
                pattern_matches = any(
                    re.search(pattern, text_lower) for pattern in rule['patterns']
                )
                
                if pattern_matches:
                    annotation = TrainingAnnotation(
                        id=f"positive_{annotation_id}",
                        timestamp=segment.start_time,
                        technique=technique,
                        description=rule['positive_feedback'],
                        effectiveness_rating=int(rule['effectiveness_boost'] * 10),
                        improvement_suggestions=rule['improvement_suggestions'],
                        related_segment_id=f"segment_{segments.index(segment)}",
                        metadata={
                            'annotation_type': 'positive',
                            'technique_category': technique,
                            'auto_generated': True,
                            'confidence': rule['effectiveness_boost']
                        }
                    )
                    annotations.append(annotation)
                    annotation_id += 1
        
        return annotations
    
    def _generate_improvement_annotations(self, segments: List[TimestampedSegment]) -> List[TrainingAnnotation]:
        """Generate improvement opportunity annotations"""
        annotations = []
        annotation_id = 1000
        
        for segment in segments:
            text_lower = segment.text.lower()
            word_count = len(segment.text.split())
            
            for issue, rule in self.negative_patterns.items():
                should_annotate = False
                
                if issue == 'talking_too_much':
                    should_annotate = word_count >= rule['min_words']
                elif 'patterns' in rule:
                    pattern_count = sum(
                        len(re.findall(pattern, text_lower)) for pattern in rule['patterns']
                    )
                    should_annotate = pattern_count >= rule.get('threshold', 1)
                
                if should_annotate:
                    annotation = TrainingAnnotation(
                        id=f"improvement_{annotation_id}",
                        timestamp=segment.start_time,
                        technique=issue,
                        description=rule['feedback'],
                        effectiveness_rating=4,
                        improvement_suggestions=rule['suggestions'],
                        related_segment_id=f"segment_{segments.index(segment)}",
                        metadata={
                            'annotation_type': 'improvement',
                            'issue_category': issue,
                            'auto_generated': True,
                            'severity': 'medium'
                        }
                    )
                    annotations.append(annotation)
                    annotation_id += 1
        
        return annotations
    
    def _generate_phase_annotations(self, roleplay_blocks: List[RolePlayBlock]) -> List[TrainingAnnotation]:
        """Generate phase-specific training annotations"""
        annotations = []
        annotation_id = 2000
        
        phase_feedback = {
            'opening': {
                'good_score': 0.7,
                'positive': "Strong opening that establishes rapport and sets agenda",
                'improvement': "Opening could be more engaging - consider a provocative question or relevant insight"
            },
            'discovery': {
                'good_score': 0.8,
                'positive': "Excellent discovery phase with probing questions",
                'improvement': "Discovery phase needs more depth - ask more 'why' and 'how' questions"
            },
            'presentation': {
                'good_score': 0.7,
                'positive': "Well-structured presentation focused on customer benefits",
                'improvement': "Presentation should be more tailored to discovered needs"
            },
            'handling_objections': {
                'good_score': 0.6,
                'positive': "Professional handling of customer concerns",
                'improvement': "Objection handling could be more empathetic and solution-focused"
            },
            'closing': {
                'good_score': 0.7,
                'positive': "Clear next steps and strong close",
                'improvement': "Closing could be more assumptive - act as if the customer will move forward"
            }
        }
        
        for block in roleplay_blocks:
            phase_key = block.phase.value
            
            if phase_key in phase_feedback:
                feedback_rule = phase_feedback[phase_key]
                
                is_positive = block.effectiveness_score >= feedback_rule['good_score']
                
                annotation = TrainingAnnotation(
                    id=f"phase_{annotation_id}",
                    timestamp=block.start_time,
                    technique=f"{phase_key}_phase",
                    description=feedback_rule['positive'] if is_positive else feedback_rule['improvement'],
                    effectiveness_rating=int(block.effectiveness_score * 10),
                    improvement_suggestions=self._get_phase_suggestions(phase_key, is_positive),
                    related_segment_id=f"block_{block.id}",
                    metadata={
                        'annotation_type': 'phase_feedback',
                        'phase': phase_key,
                        'block_effectiveness': block.effectiveness_score,
                        'auto_generated': True
                    }
                )
                annotations.append(annotation)
                annotation_id += 1
        
        return annotations
    
    def _get_phase_suggestions(self, phase: str, is_positive: bool) -> List[str]:
        """Get phase-specific improvement suggestions"""
        suggestions_map = {
            'opening': {
                True: ["Maintain this engaging approach in future calls", "Consider adding a relevant industry insight"],
                False: ["Start with a provocative question", "Mention a relevant success story", "Set clear agenda upfront"]
            },
            'discovery': {
                True: ["Continue this thorough discovery approach", "Document these needs for follow-up"],
                False: ["Ask more open-ended questions", "Probe deeper into pain points", "Use silence to encourage elaboration"]
            },
            'presentation': {
                True: ["Maintain this benefit-focused approach", "Consider adding more customer proof points"],
                False: ["Connect features to discovered needs", "Use customer success stories", "Focus on quantifiable benefits"]
            },
            'handling_objections': {
                True: ["Great objection handling technique", "Remember to confirm resolution before moving on"],
                False: ["Acknowledge the concern first", "Use 'feel, felt, found' technique", "Address root cause, not symptoms"]
            },
            'closing': {
                True: ["Strong closing approach", "Ensure clear follow-up timeline"],
                False: ["Use more assumptive language", "Create appropriate urgency", "Confirm commitment level"]
            }
        }
        
        return suggestions_map.get(phase, {}).get(is_positive, ["Continue practicing this skill area"])
    
    def get_annotation_summary(self, annotations: List[TrainingAnnotation]) -> Dict[str, Any]:
        """Generate summary statistics for annotations"""
        if not annotations:
            return {}
        
        positive_count = sum(1 for a in annotations if a.metadata.get('annotation_type') == 'positive')
        improvement_count = sum(1 for a in annotations if a.metadata.get('annotation_type') == 'improvement')
        phase_count = sum(1 for a in annotations if a.metadata.get('annotation_type') == 'phase_feedback')
        
        avg_rating = sum(a.effectiveness_rating for a in annotations) / len(annotations)
        
        techniques = [a.technique for a in annotations]
        technique_counts = {tech: techniques.count(tech) for tech in set(techniques)}
        
        return {
            'total_annotations': len(annotations),
            'positive_feedback': positive_count,
            'improvement_opportunities': improvement_count,
            'phase_feedback': phase_count,
            'average_effectiveness_rating': round(avg_rating, 1),
            'technique_frequency': technique_counts,
            'top_strengths': [tech for tech, count in technique_counts.items() 
                            if any(a.technique == tech and a.effectiveness_rating >= 7 
                                  for a in annotations)][:3],
            'improvement_areas': [tech for tech, count in technique_counts.items() 
                                if any(a.technique == tech and a.effectiveness_rating < 6 
                                      for a in annotations)][:3]
        }