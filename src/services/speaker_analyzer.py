"""
Speaker Analysis Service
Handles speaker diarization, role identification, and characteristic analysis
"""

import logging
from typing import Dict, List, Any
from collections import defaultdict

from .audio_analysis_models import Speaker, TimestampedSegment, SpeakerRole

logger = logging.getLogger(__name__)

class SpeakerAnalyzer:
    """Analyzes speakers and performs diarization mapping"""
    
    def analyze(self, segments: List[TimestampedSegment]) -> List[Speaker]:
        """Analyze speakers from segments and map to roles"""
        if not segments:
            return []
        
        # Group segments by speaker
        speaker_segments = defaultdict(list)
        for segment in segments:
            speaker_segments[segment.speaker_id].append(segment)
        
        speakers = []
        
        for speaker_id, speaker_segs in speaker_segments.items():
            # Calculate speaking characteristics
            total_time = sum((seg.end_time - seg.start_time) for seg in speaker_segs)
            turn_count = len(speaker_segs)
            avg_confidence = sum(seg.confidence for seg in speaker_segs) / len(speaker_segs)
            
            # Determine role based on speaking patterns and content
            role = self._determine_speaker_role(speaker_segs)
            
            # Extract characteristics
            characteristics = self._extract_speaker_characteristics(speaker_segs)
            characteristics.update({
                'speaking_time': total_time,
                'turn_count': turn_count
            })
            
            speaker = Speaker(
                id=speaker_id,
                role=role,
                confidence=avg_confidence,
                voice_characteristics=characteristics
            )
            
            speakers.append(speaker)
        
        return sorted(speakers, key=lambda s: s.voice_characteristics.get('speaking_time', 0), reverse=True)
    
    def _determine_speaker_role(self, segments: List[TimestampedSegment]) -> SpeakerRole:
        """Determine speaker role based on content analysis"""
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        # Sales role indicators
        sales_indicators = [
            'our product', 'our service', 'our company', 'we offer', 'i can help',
            'let me show you', 'our solution', 'benefits include', 'roi'
        ]
        
        # Prospect role indicators  
        prospect_indicators = [
            'we need', 'our budget', 'our requirements', 'we\'re looking for',
            'our current', 'we use', 'our situation', 'our challenge'
        ]
        
        sales_score = sum(1 for indicator in sales_indicators if indicator in combined_text)
        prospect_score = sum(1 for indicator in prospect_indicators if indicator in combined_text)
        
        if sales_score > prospect_score:
            return SpeakerRole.SALESPERSON
        elif prospect_score > sales_score:
            return SpeakerRole.PROSPECT
        else:
            return SpeakerRole.UNKNOWN
    
    def _extract_speaker_characteristics(self, segments: List[TimestampedSegment]) -> Dict[str, Any]:
        """Extract speaker characteristics from their segments"""
        combined_text = ' '.join(seg.text for seg in segments)
        words = combined_text.split()
        
        total_duration = sum((seg.end_time - seg.start_time) for seg in segments)
        
        characteristics = {
            'avg_words_per_turn': len(words) / len(segments) if segments else 0,
            'total_words': len(words),
            'avg_turn_duration': total_duration / len(segments) if segments else 0,
            'speaking_pace': len(words) / total_duration * 60 if total_duration > 0 else 0,  # words per minute
            'question_count': sum(seg.text.count('?') for seg in segments),
            'interruption_count': self._count_interruptions(segments),
            'enthusiasm_indicators': self._count_enthusiasm(combined_text),
            'professionalism_score': self._calculate_professionalism(combined_text)
        }
        
        return characteristics
    
    def _count_interruptions(self, segments: List[TimestampedSegment]) -> int:
        """Count potential interruptions (incomplete sentences, cut-offs)"""
        interruption_count = 0
        
        for segment in segments:
            text = segment.text.strip()
            # Look for incomplete sentences or cut-offs
            if text.endswith(('-', '--')) or len(text.split()) < 3:
                interruption_count += 1
        
        return interruption_count
    
    def _count_enthusiasm(self, text: str) -> int:
        """Count enthusiasm indicators in text"""
        enthusiasm_words = ['great', 'excellent', 'fantastic', 'amazing', 'wonderful', 'perfect', 'excited']
        text_lower = text.lower()
        return sum(text_lower.count(word) for word in enthusiasm_words)
    
    def _calculate_professionalism(self, text: str) -> float:
        """Calculate professionalism score based on language patterns"""
        text_lower = text.lower()
        
        # Professional indicators
        professional_words = [
            'solution', 'implement', 'strategic', 'optimize', 'efficient',
            'professional', 'expertise', 'experience', 'qualified'
        ]
        
        # Unprofessional indicators
        unprofessional_words = [
            'umm', 'uh', 'like', 'whatever', 'dunno', 'gonna', 'yeah'
        ]
        
        professional_count = sum(text_lower.count(word) for word in professional_words)
        unprofessional_count = sum(text_lower.count(word) for word in unprofessional_words)
        
        total_words = len(text.split())
        if total_words == 0:
            return 0.5
        
        # Calculate score (0-1 scale)
        score = (professional_count - unprofessional_count) / total_words
        return max(0.0, min(1.0, score + 0.5))  # Normalize to 0-1 range