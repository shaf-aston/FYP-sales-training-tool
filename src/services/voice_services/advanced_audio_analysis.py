"""
Advanced Audio Analysis Service - Refactored Orchestration Layer
Coordinates modular audio analysis components for comprehensive sales training insights

This refactored version uses modular components for improved maintainability:
- SpeakerAnalyzer: Speaker identification and diarization
- ContextAnalyzer: Context section analysis
- RolePlayAnalyzer: Sales phase and technique identification  
- TrainingAnnotator: Feedback and improvement suggestions
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import asyncio

from .audio_analysis_models import (
    AdvancedAudioAnalysis, TimestampedSegment, Speaker, ContextSection,
    RolePlayBlock, TrainingAnnotation, SpeakerRole, RolePlayPhase
)
from .speaker_analyzer import SpeakerAnalyzer
from .context_analyzer import ContextAnalyzer
from .roleplay_analyzer import RolePlayAnalyzer
from .training_annotator import TrainingAnnotator

logger = logging.getLogger(__name__)

class AdvancedAudioAnalysisService:
    """
    Refactored comprehensive audio analysis service
    Orchestrates multiple specialized analyzers for sales training insights
    """
    
    def __init__(self):
        """Initialize the service with all component analyzers"""
        self.speaker_analyzer = SpeakerAnalyzer()
        self.context_analyzer = ContextAnalyzer()
        self.roleplay_analyzer = RolePlayAnalyzer()
        self.training_annotator = TrainingAnnotator()
        
        self.analysis_count = 0
        self.total_processing_time = 0.0
        
        logger.info("✅ Advanced Audio Analysis Service initialized with modular components")
    
    async def analyze_conversation(self, segments: List[TimestampedSegment], 
                                 session_id: str = None, 
                                 metadata: Dict[str, Any] = None) -> AdvancedAudioAnalysis:
        """
        Perform comprehensive analysis using all modular components
        
        Args:
            segments: List of timestamped conversation segments
            session_id: Optional session identifier
            metadata: Optional analysis metadata
            
        Returns:
            Complete analysis with all component results
        """
        start_time = datetime.now(UTC)
        
        try:
            if not segments:
                raise ValueError("No segments provided for analysis")
            
            session_id = session_id or f"session_{int(datetime.now(UTC).timestamp())}"
            metadata = metadata or {}
            
            logger.info(f"Starting comprehensive analysis for session {session_id}")
            logger.info(f"Processing {len(segments)} segments with {len(self._get_component_list())} analyzers")
            
            results = await self._run_parallel_analysis(segments)
            
            speakers = results['speakers']
            context_sections = results['context_sections']
            roleplay_blocks = results['roleplay_blocks']
            training_annotations = results['training_annotations']
            
            overall_score = self._calculate_comprehensive_score(
                speakers, context_sections, roleplay_blocks, training_annotations
            )
            
            analysis = AdvancedAudioAnalysis(
                session_id=session_id,
                timestamp=datetime.now(UTC).isoformat(),
                speakers=speakers,
                segments=segments,
                context_sections=context_sections,
                roleplay_blocks=roleplay_blocks,
                training_annotations=training_annotations,
                overall_score=overall_score,
                metadata={
                    **metadata,
                    'analysis_version': '2.0_modular',
                    'component_count': len(self._get_component_list()),
                    'processing_pipeline': 'parallel'
                }
            )
            
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            self._update_performance_metrics(processing_time)
            
            logger.info(f"✅ Comprehensive analysis completed in {processing_time:.2f}s")
            logger.info(f"Results: {len(speakers)} speakers, {len(context_sections)} contexts, "
                       f"{len(roleplay_blocks)} roleplay blocks, {len(training_annotations)} annotations")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Comprehensive analysis failed for session {session_id}: {e}")
            raise
    
    async def _run_parallel_analysis(self, segments: List[TimestampedSegment]) -> Dict[str, Any]:
        """Run all analysis components in parallel for efficiency"""
        
        speakers = self.speaker_analyzer.analyze(segments)
        
        async def run_context_analysis():
            return self.context_analyzer.analyze(segments)
        
        async def run_roleplay_analysis():
            return self.roleplay_analyzer.analyze(segments, speakers, [])
        
        context_task = asyncio.create_task(run_context_analysis())
        roleplay_task = asyncio.create_task(run_roleplay_analysis())
        
        context_sections = await context_task
        roleplay_blocks = await roleplay_task
        
        training_annotations = self.training_annotator.generate_annotations(
            segments, speakers, roleplay_blocks
        )
        
        return {
            'speakers': speakers,
            'context_sections': context_sections,
            'roleplay_blocks': roleplay_blocks,
            'training_annotations': training_annotations
        }
    
    def _calculate_comprehensive_score(self, speakers: List[Speaker], 
                                     context_sections: List[ContextSection],
                                     roleplay_blocks: List[RolePlayBlock],
                                     training_annotations: List[TrainingAnnotation]) -> float:
        """Calculate overall conversation effectiveness score using all components"""
        score = 0.5
        
        if len(speakers) >= 2:
            speaker_score = sum(s.confidence for s in speakers) / len(speakers)
            score += speaker_score * 0.15
        
        if context_sections:
            avg_context_importance = sum(cs.importance_score for cs in context_sections) / len(context_sections)
            score += avg_context_importance * 0.25
        
        if roleplay_blocks:
            avg_roleplay_effectiveness = sum(rb.effectiveness_score for rb in roleplay_blocks) / len(roleplay_blocks)
            score += avg_roleplay_effectiveness * 0.35
            
            unique_phases = len(set(block.phase for block in roleplay_blocks))
            if unique_phases >= 3:
                score += 0.05
        
        if training_annotations:
            positive_annotations = [a for a in training_annotations 
                                  if a.metadata.get('annotation_type') == 'positive']
            positive_ratio = len(positive_annotations) / len(training_annotations)
            score += positive_ratio * 0.25
        
        return min(score, 1.0)
    
    def _get_component_list(self) -> List[str]:
        """Get list of active analysis components"""
        return ['SpeakerAnalyzer', 'ContextAnalyzer', 'RolePlayAnalyzer', 'TrainingAnnotator']
    
    def _update_performance_metrics(self, processing_time: float):
        """Update service performance metrics"""
        self.analysis_count += 1
        self.total_processing_time += processing_time
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service performance metrics"""
        avg_time = self.total_processing_time / self.analysis_count if self.analysis_count > 0 else 0
        
        return {
            'service_info': {
                'version': '2.0_modular',
                'components': self._get_component_list(),
                'architecture': 'modular_orchestration'
            },
            'performance': {
                'total_analyses': self.analysis_count,
                'total_processing_time': f"{self.total_processing_time:.2f}s",
                'average_processing_time': f"{avg_time:.2f}s",
                'analyses_per_minute': round(60 / avg_time, 1) if avg_time > 0 else 0
            },
            'status': 'active'
        }
    
    def get_detailed_analysis_summary(self, analysis: AdvancedAudioAnalysis) -> Dict[str, Any]:
        """Generate comprehensive analysis summary with component breakdowns"""
        speaker_summary = self.speaker_analyzer.get_speaker_summary(analysis.speakers)
        context_summary = self.context_analyzer.get_context_summary(analysis.context_sections)
        roleplay_summary = self.roleplay_analyzer.get_phase_statistics(analysis.roleplay_blocks)
        training_summary = self.training_annotator.get_annotation_summary(analysis.training_annotations)
        
        return {
            'overview': {
                'session_id': analysis.session_id,
                'timestamp': analysis.timestamp,
                'overall_score': analysis.overall_score,
                'total_duration': analysis.segments[-1].end_time - analysis.segments[0].start_time if analysis.segments else 0
            },
            'component_results': {
                'speakers': speaker_summary,
                'contexts': context_summary,
                'roleplay': roleplay_summary,
                'training': training_summary
            },
            'key_insights': self._extract_key_insights(analysis),
            'recommendations': self._generate_recommendations(analysis)
        }
    
    def _extract_key_insights(self, analysis: AdvancedAudioAnalysis) -> List[str]:
        """Extract key insights from the comprehensive analysis"""
        insights = []
        
        if len(analysis.speakers) == 1:
            insights.append("⚠️ Only one speaker identified - consider improving interaction")
        elif len(analysis.speakers) > 2:
            insights.append("✅ Multi-party conversation detected")
        
        phases_covered = set(block.phase for block in analysis.roleplay_blocks)
        if len(phases_covered) >= 4:
            insights.append("✅ Comprehensive role-play covering multiple sales phases")
        elif len(phases_covered) <= 2:
            insights.append("⚠️ Limited phase coverage - practice more diverse scenarios")
        
        positive_annotations = [a for a in analysis.training_annotations 
                              if a.metadata.get('annotation_type') == 'positive']
        if len(positive_annotations) >= len(analysis.training_annotations) * 0.6:
            insights.append("✅ Strong demonstration of sales techniques")
        else:
            insights.append("📈 Multiple improvement opportunities identified")
        
        return insights
    
    def _generate_recommendations(self, analysis: AdvancedAudioAnalysis) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        if analysis.overall_score >= 0.8:
            recommendations.append("🎯 Excellent performance - focus on advanced techniques")
        elif analysis.overall_score >= 0.6:
            recommendations.append("📊 Good foundation - work on consistency and refinement")
        else:
            recommendations.append("🔧 Significant improvement needed - focus on basic techniques")
        
        phases_covered = set(block.phase.value for block in analysis.roleplay_blocks)
        missing_phases = {'opening', 'discovery', 'presentation', 'handling_objections', 'closing'} - phases_covered
        
        if missing_phases:
            phase_names = ', '.join(missing_phases)
            recommendations.append(f"📝 Practice these phases: {phase_names}")
        
        improvement_annotations = [a for a in analysis.training_annotations 
                                 if a.metadata.get('annotation_type') == 'improvement']
        if improvement_annotations:
            top_improvements = list(set(a.technique for a in improvement_annotations[:3]))
            recommendations.append(f"🎯 Focus on: {', '.join(top_improvements)}")
        
        return recommendations


_advanced_audio_service: Optional[AdvancedAudioAnalysisService] = None

def get_advanced_audio_service() -> AdvancedAudioAnalysisService:
    """Get singleton advanced audio analysis service instance"""
    global _advanced_audio_service
    if _advanced_audio_service is None:
        _advanced_audio_service = AdvancedAudioAnalysisService()
    return _advanced_audio_service

def reset_advanced_audio_service():
    """Reset service instance (for testing purposes)"""
    global _advanced_audio_service
    _advanced_audio_service = None

def analyze_advanced_audio(segments: List[TimestampedSegment], **kwargs) -> AdvancedAudioAnalysis:
    """Legacy function for backward compatibility"""
    import asyncio
    service = get_advanced_audio_service()
    return asyncio.run(service.analyze_conversation(segments, **kwargs))