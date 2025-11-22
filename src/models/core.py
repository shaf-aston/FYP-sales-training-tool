"""
Core Data Models with Confidence Scoring
Comprehensive data structures for STT, TTS, and conversation management
"""
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class ConfidenceLevel(Enum):
    """Confidence level classification"""
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"

class ServiceProvider(Enum):
    """Available service providers"""
    FASTER_WHISPER = "faster_whisper"
    WHISPER = "whisper"
    SPEECH_RECOGNITION = "speech_recognition"
    COQUI = "coqui"
    PYTTSX3 = "pyttsx3"

@dataclass
class QualityMetrics:
    """Quality metrics for audio processing"""
    clarity: float = 0.0
    noise_level: float = 0.0
    volume: float = 0.0

@dataclass
class STTResult:
    """Speech-to-Text result with comprehensive confidence scoring"""
    text: str
    confidence: float
    language: str
    processing_time: float
    model_used: str
    quality_metrics: QualityMetrics
    error: Optional[str] = None
    
    def __post_init__(self):
        """Ensure confidence is in valid range"""
        self.confidence = max(0.0, min(1.0, self.confidence))
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if result meets high confidence threshold"""
        return self.confidence >= threshold
    
    def is_acceptable(self, threshold: float = 0.6) -> bool:
        """Check if result meets minimum confidence threshold"""
        return self.confidence >= threshold
    
    def get_confidence_level(self, high_threshold: float = 0.8, 
                           medium_threshold: float = 0.6) -> ConfidenceLevel:
        """Get confidence level classification"""
        if self.confidence >= high_threshold:
            return ConfidenceLevel.HIGH
        elif self.confidence >= medium_threshold:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def quality_score(self) -> float:
        """Calculate overall quality score"""
        # Combine confidence with quality metrics
        confidence_weight = 0.4
        clarity_weight = 0.3
        noise_weight = 0.2
        processing_weight = 0.1
        
        # Processing speed factor (faster is better, up to reasonable limit)
        processing_factor = min(1.0, 2.0 / max(0.1, self.processing_time))
        
        quality = (
            self.confidence * confidence_weight +
            self.quality_metrics.clarity * clarity_weight +
            (1.0 - self.quality_metrics.noise_level) * noise_weight +
            processing_factor * processing_weight
        )
        
        return max(0.0, min(1.0, quality))

@dataclass
class VoiceProfile:
    """Voice profile configuration for TTS"""
    model_name: Optional[str] = None
    speaker_name: Optional[str] = None
    gender: str = "female"
    speed: float = 1.0
    volume: float = 0.8
    language: str = "en"
    
    def __str__(self) -> str:
        """String representation of voice profile"""
        return f"Voice(model={self.model_name}, speaker={self.speaker_name}, gender={self.gender})"

@dataclass 
class TTSResult:
    """Text-to-Speech result with quality metrics"""
    success: bool
    audio_path: Optional[str]
    duration: float
    processing_time: float
    voice_used: str
    quality_metrics: QualityMetrics
    error: Optional[str] = None

@dataclass
class ConversationTurn:
    """Complete conversation turn with confidence tracking"""
    user_input: STTResult
    ai_response: str
    voice_output: Optional[TTSResult] = None
    timestamp: datetime = field(default_factory=datetime.now)
    confidence_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "high": 0.8, "medium": 0.6, "low": 0.3
    })
    
    @property
    def overall_quality(self) -> float:
        """Calculate overall conversation quality"""
        stt_quality = self.user_input.quality_score()
        
        if self.voice_output and self.voice_output.success:
            # Factor in TTS quality if available
            tts_quality_estimate = (
                self.voice_output.quality_metrics.clarity * 0.5 +
                (1.0 - self.voice_output.quality_metrics.noise_level) * 0.3 +
                self.voice_output.quality_metrics.volume * 0.2
            )
            return (stt_quality * 0.7 + tts_quality_estimate * 0.3)
        else:
            return stt_quality
    
    def generate_feedback(self) -> Dict[str, Any]:
        """Generate detailed feedback for the conversation turn"""
        confidence_level = self.user_input.get_confidence_level(
            self.confidence_thresholds.get("high", 0.8),
            self.confidence_thresholds.get("medium", 0.6)
        )
        
        suggestions = []
        
        # Generate suggestions based on confidence and quality
        if confidence_level == ConfidenceLevel.LOW:
            suggestions.extend([
                "Consider improving microphone quality or positioning",
                "Reduce background noise if possible",
                "Speak more clearly and at a moderate pace"
            ])
            
            if self.user_input.quality_metrics.volume < 0.5:
                suggestions.append("Increase speaking volume")
            
            if self.user_input.quality_metrics.noise_level > 0.6:
                suggestions.append("Find a quieter environment")
        
        elif confidence_level == ConfidenceLevel.MEDIUM:
            suggestions.extend([
                "Good clarity overall",
                "Small improvements in audio quality could help"
            ])
            
            if self.user_input.processing_time > 3.0:
                suggestions.append("Consider using faster speech recognition model")
        
        else:  # HIGH confidence
            suggestions.append("Excellent audio quality and recognition")
        
        return {
            "confidence_level": confidence_level.value,
            "confidence_score": self.user_input.confidence,
            "quality_score": self.overall_quality,
            "processing_time": self.user_input.processing_time,
            "suggestions": suggestions,
            "metrics": {
                "clarity": self.user_input.quality_metrics.clarity,
                "noise_level": self.user_input.quality_metrics.noise_level,
                "volume": self.user_input.quality_metrics.volume
            }
        }