"""
Context Analysis Service
Analyzes conversation context sections using timestamps and thematic grouping
"""

import logging
from typing import Dict, List, Any
from collections import defaultdict

from .audio_analysis_models import ContextSection, TimestampedSegment, RolePlayPhase

logger = logging.getLogger(__name__)

class ContextAnalyzer:
    """Analyzes context sections using timestamps and thematic grouping"""
    
    def analyze(self, segments: List[TimestampedSegment], phase_indicators: Dict = None) -> List[ContextSection]:
        """Analyze context sections from segments"""
        if not segments:
            return []
        
        if phase_indicators is None:
            phase_indicators = self._get_default_phase_indicators()
        
        # Group segments into context sections based on timing and content
        sections = self._create_context_sections(segments, phase_indicators)
        
        # Enhance sections with analysis
        for section in sections:
            section.metadata.update({
                'summary': self._generate_section_summary(section.segments),
                'key_points': self._extract_key_points(section.segments),
                'techniques_used': self._identify_techniques_used(section.segments)
            })
            section.importance_score = self._calculate_section_effectiveness(section)
        
        return sections
    
    def _create_context_sections(self, segments: List[TimestampedSegment], phase_indicators: Dict) -> List[ContextSection]:
        """Create context sections based on content and timing"""
        sections = []
        current_section_segments = []
        current_phase = RolePlayPhase.OPENING
        section_id = 0
        
        for i, segment in enumerate(segments):
            # Detect phase transition
            detected_phase = self._detect_phase(segment, i, len(segments), phase_indicators)
            
            # If phase changed or we have a natural break, create new section
            if (detected_phase != current_phase and current_section_segments) or \
               (len(current_section_segments) > 10):  # Max segments per section
                
                section = self._create_section_from_segments(
                    f"section_{section_id}",
                    current_phase,
                    current_section_segments
                )
                sections.append(section)
                
                current_section_segments = []
                section_id += 1
                current_phase = detected_phase
            
            current_section_segments.append(segment)
        
        # Create final section
        if current_section_segments:
            section = self._create_section_from_segments(
                f"section_{section_id}",
                current_phase,
                current_section_segments
            )
            sections.append(section)
        
        return sections
    
    def _detect_phase(self, segment: TimestampedSegment, position: int, total: int, phase_indicators: Dict) -> RolePlayPhase:
        """Detect conversation phase for a segment"""
        text_lower = segment.text.lower()
        position_ratio = position / total if total > 0 else 0
        
        phase_scores = {}
        
        for phase, indicators in phase_indicators.items():
            score = 0.0
            
            # Keyword matching
            for keyword in indicators.get('keywords', []):
                if keyword in text_lower:
                    score += 1.0
            
            # Phrase matching
            for phrase in indicators.get('phrases', []):
                if phrase in text_lower:
                    score += 2.0
            
            # Position weighting
            position_weight = indicators.get('position_weight', 1.0)
            
            # Adjust score based on conversation position
            if phase == RolePlayPhase.OPENING and position_ratio < 0.2:
                score *= position_weight
            elif phase == RolePlayPhase.DISCOVERY and 0.1 < position_ratio < 0.5:
                score *= position_weight
            elif phase == RolePlayPhase.PRESENTATION and 0.3 < position_ratio < 0.8:
                score *= position_weight
            elif phase == RolePlayPhase.CLOSING and position_ratio > 0.7:
                score *= position_weight
            
            phase_scores[phase] = score
        
        # Return phase with highest score, default to current conversation position
        if phase_scores:
            best_phase = max(phase_scores, key=phase_scores.get)
            if phase_scores[best_phase] > 0:
                return best_phase
        
        # Fallback to position-based phase detection
        return self._get_phase_by_position(position_ratio)
    
    def _get_phase_by_position(self, position_ratio: float) -> RolePlayPhase:
        """Get phase based on position in conversation"""
        if position_ratio < 0.15:
            return RolePlayPhase.OPENING
        elif position_ratio < 0.4:
            return RolePlayPhase.DISCOVERY
        elif position_ratio < 0.7:
            return RolePlayPhase.PRESENTATION
        elif position_ratio < 0.9:
            return RolePlayPhase.OBJECTION_HANDLING
        else:
            return RolePlayPhase.CLOSING
    
    def _create_section_from_segments(self, section_id: str, phase: RolePlayPhase, 
                                    segments: List[TimestampedSegment]) -> ContextSection:
        """Create a context section from a list of segments"""
        if not segments:
            raise ValueError("Cannot create section from empty segments")
        
        start_time = segments[0].start_time
        end_time = segments[-1].end_time
        
        # Generate title and description based on phase and content
        title = self._generate_section_title(phase, segments)
        description = self._generate_section_description(phase, segments)
        
        return ContextSection(
            id=section_id,
            start_time=start_time,
            end_time=end_time,
            title=title,
            description=description,
            segments=segments,
            metadata={'phase': phase.value}
        )
    
    def _generate_section_title(self, phase: RolePlayPhase, segments: List[TimestampedSegment]) -> str:
        """Generate appropriate title for the section"""
        phase_titles = {
            RolePlayPhase.OPENING: "Opening & Introductions",
            RolePlayPhase.DISCOVERY: "Discovery & Needs Assessment",
            RolePlayPhase.PRESENTATION: "Solution Presentation",
            RolePlayPhase.OBJECTION_HANDLING: "Objection Handling",
            RolePlayPhase.CLOSING: "Closing & Next Steps",
            RolePlayPhase.FOLLOW_UP: "Follow-up Discussion"
        }
        
        return phase_titles.get(phase, f"Conversation Section ({phase.value})")
    
    def _generate_section_description(self, phase: RolePlayPhase, segments: List[TimestampedSegment]) -> str:
        """Generate description based on section content"""
        total_words = sum(len(seg.text.split()) for seg in segments)
        duration = segments[-1].end_time - segments[0].start_time
        
        return f"{phase.value.replace('_', ' ').title()} phase with {len(segments)} exchanges, " \
               f"{total_words} words over {duration:.1f} seconds"
    
    def _generate_section_summary(self, segments: List[TimestampedSegment]) -> str:
        """Generate a summary of the section content"""
        combined_text = ' '.join(seg.text for seg in segments)
        words = combined_text.split()
        
        # Simple extractive summary - take first and key sentences
        sentences = combined_text.split('.')
        if len(sentences) > 3:
            summary_sentences = [sentences[0], sentences[len(sentences)//2], sentences[-2]]
            return '. '.join(s.strip() for s in summary_sentences if s.strip()) + '.'
        
        return combined_text[:200] + '...' if len(combined_text) > 200 else combined_text
    
    def _extract_key_points(self, segments: List[TimestampedSegment]) -> List[str]:
        """Extract key points from the section"""
        key_points = []
        combined_text = ' '.join(seg.text for seg in segments).lower()
        
        # Look for important indicators
        if 'price' in combined_text or 'cost' in combined_text:
            key_points.append("Pricing discussion")
        if 'timeline' in combined_text or 'when' in combined_text:
            key_points.append("Timeline considerations")
        if 'feature' in combined_text or 'capability' in combined_text:
            key_points.append("Feature discussion")
        if 'concern' in combined_text or 'worry' in combined_text:
            key_points.append("Concerns raised")
        if 'decision' in combined_text or 'approve' in combined_text:
            key_points.append("Decision-making process")
        
        return key_points
    
    def _identify_techniques_used(self, segments: List[TimestampedSegment]) -> List[str]:
        """Identify sales techniques used in the section"""
        techniques = []
        combined_text = ' '.join(seg.text for seg in segments).lower()
        
        # Technique indicators
        if any(word in combined_text for word in ['understand', 'hear', 'tell me']):
            techniques.append("Active Listening")
        if '?' in combined_text:
            techniques.append("Questioning Technique")
        if any(word in combined_text for word in ['benefit', 'advantage', 'value']):
            techniques.append("Value Proposition")
        if any(word in combined_text for word in ['similar', 'other clients', 'example']):
            techniques.append("Social Proof")
        
        return techniques
    
    def _calculate_section_effectiveness(self, section: ContextSection) -> float:
        """Calculate effectiveness score for the section"""
        score = 0.5  # Base score
        
        # Increase score based on engagement indicators
        total_text = ' '.join(seg.text for seg in section.segments)
        
        # Questions indicate engagement
        question_count = total_text.count('?')
        score += min(question_count * 0.05, 0.2)
        
        # Varied speakers indicate interaction
        speakers = set(seg.speaker_id for seg in section.segments)
        if len(speakers) > 1:
            score += 0.1
        
        # Longer discussions might be more valuable
        duration = section.end_time - section.start_time
        if duration > 60:  # More than 1 minute
            score += 0.1
        
        # Key techniques used
        techniques_count = len(section.metadata.get('techniques_used', []))
        score += min(techniques_count * 0.05, 0.15)
        
        return min(score, 1.0)
    
    def _get_default_phase_indicators(self) -> Dict:
        """Get default phase indicators for conversation analysis"""
        return {
            RolePlayPhase.OPENING: {
                'keywords': ['hello', 'hi', 'introduction', 'meet', 'name'],
                'phrases': ['nice to meet', 'thank you for', 'pleasure to'],
                'position_weight': 2.0
            },
            RolePlayPhase.DISCOVERY: {
                'keywords': ['need', 'challenge', 'problem', 'current', 'situation'],
                'phrases': ['tell me about', 'what are you', 'how do you'],
                'position_weight': 1.5
            },
            RolePlayPhase.PRESENTATION: {
                'keywords': ['solution', 'feature', 'benefit', 'product', 'service'],
                'phrases': ['our solution', 'what we offer', 'this will help'],
                'position_weight': 1.5
            },
            RolePlayPhase.OBJECTION_HANDLING: {
                'keywords': ['concern', 'worry', 'but', 'however', 'issue'],
                'phrases': ['what if', 'i\'m not sure', 'that sounds'],
                'position_weight': 1.0
            },
            RolePlayPhase.CLOSING: {
                'keywords': ['decision', 'next', 'move forward', 'sign', 'agreement'],
                'phrases': ['next steps', 'ready to', 'shall we proceed'],
                'position_weight': 2.0
            }
        }