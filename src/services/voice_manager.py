"""
Voice Processing Manager
Orchestrates STT and TTS services with confidence scoring
"""
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple
from dataclasses import asdict

from src.models.core import (
    STTResult, TTSResult, VoiceProfile, ConversationTurn,
    ConfidenceLevel, QualityMetrics
)
from src.services.stt_service import STTService
from src.services.tts_service import TTSService

logger = logging.getLogger(__name__)

class VoiceManager:
    """Manages voice processing with confidence scoring"""
    
    def __init__(self, 
                 stt_provider: str = "faster_whisper",
                 tts_provider: str = "coqui",
                 voice_profile: Optional[VoiceProfile] = None,
                 confidence_thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize voice manager
        
        Args:
            stt_provider: STT service provider
            tts_provider: TTS service provider  
            voice_profile: Voice configuration
            confidence_thresholds: Custom confidence thresholds
        """
        self.stt_service = STTService(provider=stt_provider)
        self.tts_service = TTSService(
            provider=tts_provider,
            voice_profile=voice_profile
        )
        
        # Default confidence thresholds
        self.confidence_thresholds = confidence_thresholds or {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.3
        }
        
        self.conversation_history = []
        self.session_metrics = {
            "total_turns": 0,
            "high_confidence_turns": 0,
            "processing_time_total": 0.0,
            "quality_average": 0.0
        }
    
    def process_audio_input(self, audio_data: Any, 
                            language: Optional[str] = None) -> STTResult:
        """Process audio input with confidence scoring"""
        logger.info("Processing audio input")
        
        result = self.stt_service.transcribe(audio_data, language)
        
        # Update session metrics
        self._update_session_metrics(result)
        
        # Log confidence level
        confidence_level = result.get_confidence_level(
            self.confidence_thresholds["high"],
            self.confidence_thresholds["medium"]
        )
        logger.info(f"Transcription confidence: {confidence_level.value}")
        
        return result
    
    def generate_speech_response(self, text: str, 
                                output_path: Optional[str] = None) -> TTSResult:
        """Generate speech response"""
        logger.info(f"Generating speech for: {text[:50]}...")
        
        result = self.tts_service.speak(text, output_path)
        
        if result.success:
            logger.info(f"Speech generated successfully: {result.duration:.2f}s")
        else:
            logger.error(f"Speech generation failed: {result.error}")
        
        return result
    
    def create_conversation_turn(self, stt_result: STTResult, 
                                ai_response: str,
                                tts_result: Optional[TTSResult] = None) -> ConversationTurn:
        """Create a complete conversation turn"""
        turn = ConversationTurn(
            user_input=stt_result,
            ai_response=ai_response,
            voice_output=tts_result,
            confidence_thresholds=self.confidence_thresholds
        )
        
        self.conversation_history.append(turn)
        self.session_metrics["total_turns"] += 1
        
        if stt_result.get_confidence_level(
            self.confidence_thresholds["high"],
            self.confidence_thresholds["medium"]
        ) == ConfidenceLevel.HIGH:
            self.session_metrics["high_confidence_turns"] += 1
        
        logger.info(f"Created conversation turn with quality: {turn.overall_quality:.2f}")
        
        return turn
    
    def get_conversation_feedback(self, turn_index: int = -1) -> Dict[str, Any]:
        """Get feedback for a conversation turn"""
        if not self.conversation_history:
            return {"error": "No conversation history"}
        
        try:
            turn = self.conversation_history[turn_index]
            return turn.generate_feedback()
        except IndexError:
            return {"error": f"Turn {turn_index} not found"}
    
    def analyze_session_quality(self) -> Dict[str, Any]:
        """Analyze overall session quality"""
        if not self.conversation_history:
            return {"error": "No conversation data"}
        
        # Calculate averages
        total_turns = len(self.conversation_history)
        high_confidence = sum(
            1 for turn in self.conversation_history
            if turn.user_input.get_confidence_level(
                self.confidence_thresholds["high"],
                self.confidence_thresholds["medium"]
            ) == ConfidenceLevel.HIGH
        )
        
        avg_quality = sum(
            turn.overall_quality for turn in self.conversation_history
        ) / total_turns
        
        avg_processing_time = sum(
            turn.user_input.processing_time for turn in self.conversation_history
        ) / total_turns
        
        # Quality distribution
        quality_distribution = {
            "high": 0,
            "medium": 0, 
            "low": 0
        }
        
        for turn in self.conversation_history:
            confidence_level = turn.user_input.get_confidence_level(
                self.confidence_thresholds["high"],
                self.confidence_thresholds["medium"]
            )
            quality_distribution[confidence_level.value] += 1
        
        return {
            "session_summary": {
                "total_turns": total_turns,
                "high_confidence_percentage": (high_confidence / total_turns) * 100,
                "average_quality": avg_quality,
                "average_processing_time": avg_processing_time
            },
            "quality_distribution": quality_distribution,
            "recommendations": self._generate_recommendations(
                high_confidence / total_turns, avg_quality, avg_processing_time
            )
        }
    
    def _update_session_metrics(self, stt_result: STTResult):
        """Update session-level metrics"""
        self.session_metrics["processing_time_total"] += stt_result.processing_time
        
        # Update quality average
        current_quality = stt_result.quality_score()
        total_turns = self.session_metrics["total_turns"]
        current_avg = self.session_metrics["quality_average"]
        
        # Incremental average calculation
        new_avg = (current_avg * total_turns + current_quality) / (total_turns + 1)
        self.session_metrics["quality_average"] = new_avg
    
    def _generate_recommendations(self, confidence_ratio: float, 
                                 avg_quality: float, 
                                 avg_processing_time: float) -> Dict[str, str]:
        """Generate recommendations based on session metrics"""
        recommendations = {}
        
        if confidence_ratio < 0.6:
            recommendations["audio_quality"] = (
                "Consider improving microphone setup or reducing background noise. "
                f"Only {confidence_ratio*100:.1f}% of transcriptions were high confidence."
            )
        
        if avg_quality < 0.7:
            recommendations["processing"] = (
                "Audio processing quality could be improved. "
                "Consider upgrading STT model or adjusting audio preprocessing."
            )
        
        if avg_processing_time > 3.0:
            recommendations["performance"] = (
                f"Processing time averaging {avg_processing_time:.1f}s is slow. "
                "Consider using faster models or upgrading hardware."
            )
        
        if not recommendations:
            recommendations["overall"] = "Voice processing quality is excellent!"
        
        return recommendations
    
    def update_confidence_thresholds(self, thresholds: Dict[str, float]):
        """Update confidence thresholds"""
        self.confidence_thresholds.update(thresholds)
        logger.info(f"Updated confidence thresholds: {self.confidence_thresholds}")
    
    def switch_stt_provider(self, provider: str, model_name: str = "base"):
        """Switch STT provider"""
        logger.info(f"Switching STT to {provider}")
        self.stt_service = STTService(provider=provider, model_name=model_name)
    
    def switch_tts_provider(self, provider: str, 
                           voice_profile: Optional[VoiceProfile] = None):
        """Switch TTS provider"""
        logger.info(f"Switching TTS to {provider}")
        self.tts_service = TTSService(
            provider=provider,
            voice_profile=voice_profile or self.tts_service.voice_profile
        )
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about current services"""
        return {
            "stt": self.stt_service.get_model_info(),
            "tts": self.tts_service.get_model_info(),
            "confidence_thresholds": self.confidence_thresholds,
            "session_metrics": self.session_metrics
        }
    
    def export_session_data(self) -> Dict[str, Any]:
        """Export session data for analysis"""
        return {
            "conversation_history": [
                {
                    "turn_id": i,
                    "timestamp": turn.timestamp.isoformat(),
                    "stt_result": asdict(turn.user_input),
                    "ai_response": turn.ai_response,
                    "tts_result": asdict(turn.voice_output) if turn.voice_output else None,
                    "overall_quality": turn.overall_quality,
                    "feedback": turn.generate_feedback()
                }
                for i, turn in enumerate(self.conversation_history)
            ],
            "session_metrics": self.session_metrics,
            "service_info": self.get_service_info()
        }