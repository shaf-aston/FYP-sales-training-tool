"""
Refactored Advanced Audio Analysis Service
Orchestrates audio analysis components with improved modularity
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .audio_analysis_models import (
    AdvancedAudioAnalysis, TimestampedSegment, Speaker, ContextSection,
    RolePlayBlock, TrainingAnnotation
)
from .speaker_analyzer import SpeakerAnalyzer
from .context_analyzer import ContextAnalyzer

logger = logging.getLogger(__name__)

class AdvancedAudioAnalysisService:
    """
    Refactored service for comprehensive audio analysis
    Coordinates multiple specialized analyzers
    """
    
    def __init__(self):
        """Initialize the service with component analyzers"""
        self.speaker_analyzer = SpeakerAnalyzer()
        self.context_analyzer = ContextAnalyzer()
        
        self.analysis_count = 0
        self.total_processing_time = 0.0
        
        logger.info("✅ Advanced Audio Analysis Service initialized")
    
    async def analyze_conversation(self, segments: List[TimestampedSegment], 
                                 session_id: str = None, 
                                 metadata: Dict[str, Any] = None) -> AdvancedAudioAnalysis:
        """
        Perform comprehensive analysis of conversation segments
        
        Args:
            segments: List of timestamped conversation segments
            session_id: Optional session identifier
            metadata: Optional metadata for the analysis
            
        Returns:
            Complete analysis results
        """
        start_time = datetime.now()
        
        try:
            if not segments:
                raise ValueError("No segments provided for analysis")
            
            session_id = session_id or f"session_{int(datetime.now().timestamp())}"
            metadata = metadata or {}
            
            logger.info(f"Starting analysis for session {session_id} with {len(segments)} segments")
            
            speakers = self.speaker_analyzer.analyze(segments)
            logger.info(f"Identified {len(speakers)} speakers")
            
            context_sections = self.context_analyzer.analyze(segments)
            logger.info(f"Created {len(context_sections)} context sections")
            
            roleplay_blocks = self._generate_roleplay_blocks(segments, context_sections)
            logger.info(f"Generated {len(roleplay_blocks)} role-play blocks")
            
            training_annotations = self._generate_training_annotations(segments, speakers)
            logger.info(f"Created {len(training_annotations)} training annotations")
            
            overall_score = self._calculate_overall_score(speakers, context_sections, roleplay_blocks)
            
            analysis = AdvancedAudioAnalysis(
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                speakers=speakers,
                segments=segments,
                context_sections=context_sections,
                roleplay_blocks=roleplay_blocks,
                training_annotations=training_annotations,
                overall_score=overall_score,
                metadata=metadata
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(processing_time)
            
            logger.info(f"Analysis completed in {processing_time:.2f}s with score {overall_score:.2f}")
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis failed for session {session_id}: {e}")
            raise
    
    def _generate_roleplay_blocks(self, segments: List[TimestampedSegment], 
                                context_sections: List[ContextSection]) -> List[RolePlayBlock]:
        """Generate role-play blocks from context sections (simplified implementation)"""
        blocks = []
        
        for i, section in enumerate(context_sections):
            phase_str = section.metadata.get('phase', 'unknown')
            
            from .audio_analysis_models import RolePlayPhase
            try:
                phase = RolePlayPhase(phase_str)
            except ValueError:
                phase = RolePlayPhase.DISCOVERY
            
            block = RolePlayBlock(
                id=f"block_{i}",
                phase=phase,
                start_time=section.start_time,
                end_time=section.end_time,
                segments=section.segments,
                techniques_used=[],
                effectiveness_score=section.importance_score,
                metadata={'generated_from_context_section': section.id}
            )
            
            blocks.append(block)
        
        return blocks
    
    def _generate_training_annotations(self, segments: List[TimestampedSegment], 
                                     speakers: List[Speaker]) -> List[TrainingAnnotation]:
        """Generate training annotations (simplified implementation)"""
        annotations = []
        
        salesperson_speakers = [s for s in speakers if s.role.value == 'salesperson']
        
        if not salesperson_speakers:
            return annotations
        
        salesperson_id = salesperson_speakers[0].id
        salesperson_segments = [s for s in segments if s.speaker_id == salesperson_id]
        
        for i, segment in enumerate(salesperson_segments):
            if '?' in segment.text:
                annotation = TrainingAnnotation(
                    id=f"annotation_{len(annotations)}",
                    timestamp=segment.start_time,
                    technique="questioning",
                    description="Used questioning technique to engage prospect",
                    effectiveness_rating=7,
                    improvement_suggestions=["Consider more open-ended questions"],
                    related_segment_id=f"segment_{i}",
                    metadata={'auto_generated': True}
                )
                annotations.append(annotation)
        
        return annotations
    
    def _calculate_overall_score(self, speakers: List[Speaker], 
                               context_sections: List[ContextSection],
                               roleplay_blocks: List[RolePlayBlock]) -> float:
        """Calculate overall conversation effectiveness score"""
        score = 0.5
        
        if len(speakers) >= 2:
            score += 0.1
        
        avg_section_score = sum(s.importance_score for s in context_sections) / len(context_sections) if context_sections else 0
        score += avg_section_score * 0.3
        
        if len(roleplay_blocks) >= 3:
            score += 0.1
        
        total_segments = sum(len(section.segments) for section in context_sections)
        if total_segments > 10:
            score += 0.1
        
        return min(score, 1.0)
    
    def _update_metrics(self, processing_time: float):
        """Update performance metrics"""
        self.analysis_count += 1
        self.total_processing_time += processing_time
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get service performance metrics"""
        avg_time = self.total_processing_time / self.analysis_count if self.analysis_count > 0 else 0
        
        return {
            'total_analyses': self.analysis_count,
            'total_processing_time': f"{self.total_processing_time:.2f}s",
            'average_processing_time': f"{avg_time:.2f}s",
            'service_status': 'active'
        }
    
    def get_analysis_summary(self, analysis: AdvancedAudioAnalysis) -> Dict[str, Any]:
        """Generate a summary of analysis results"""
        return {
            'session_id': analysis.session_id,
            'timestamp': analysis.timestamp,
            'overall_score': analysis.overall_score,
            'speakers': len(analysis.speakers),
            'context_sections': len(analysis.context_sections),
            'roleplay_blocks': len(analysis.roleplay_blocks),
            'training_annotations': len(analysis.training_annotations),
            'total_segments': len(analysis.segments),
            'duration': analysis.segments[-1].end_time - analysis.segments[0].start_time if analysis.segments else 0
        }

_audio_analysis_service: Optional[AdvancedAudioAnalysisService] = None

def get_audio_analysis_service() -> AdvancedAudioAnalysisService:
    """Get singleton audio analysis service instance"""
    global _audio_analysis_service
    if _audio_analysis_service is None:
        _audio_analysis_service = AdvancedAudioAnalysisService()
    return _audio_analysis_service

def reset_audio_analysis_service():
    """Reset service instance (for testing)"""
    global _audio_analysis_service
    _audio_analysis_service = None