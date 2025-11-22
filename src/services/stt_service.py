"""
STT (Speech-to-Text) Service
Clean implementation with confidence scoring
"""
import logging
import tempfile
import os
from typing import Optional, Dict, Any
from pathlib import Path

from src.models.core import STTResult, ConfidenceLevel, QualityMetrics
from src.utils.dependencies import (
    whisper, WhisperModel, sr, torch,
    DEPENDENCIES, validate_provider
)

logger = logging.getLogger(__name__)

class STTService:
    """Speech-to-Text service with multiple providers"""
    
    def __init__(self, provider: str = "faster_whisper", 
                 model_name: str = "base", device: str = "auto"):
        self.provider = provider
        self.model_name = model_name
        self.device = self._get_device(device)
        self.model = None
        self.engine = None
        self._initialize_engine()
    
    def _get_device(self, device: str) -> str:
        """Determine best device"""
        if device == "auto":
            if DEPENDENCIES["torch"] and torch.cuda.is_available():
                return "cuda"
            return "cpu"
        return device
    
    def _initialize_engine(self):
        """Initialize the STT engine"""
        if not validate_provider("stt", self.provider):
            logger.error(f"STT provider {self.provider} not available")
            self._fallback_provider()
            return
        
        try:
            if self.provider == "faster_whisper":
                self._init_faster_whisper()
            elif self.provider == "whisper":
                self._init_whisper()
            elif self.provider == "speech_recognition":
                self._init_speech_recognition()
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
                
            logger.info(f"STT initialized with {self.provider}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider}: {e}")
            self._fallback_provider()
    
    def _init_faster_whisper(self):
        """Initialize Faster Whisper"""
        self.model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type="float16" if self.device == "cuda" else "int8"
        )
    
    def _init_whisper(self):
        """Initialize OpenAI Whisper"""
        self.model = whisper.load_model(self.model_name)
    
    def _init_speech_recognition(self):
        """Initialize SpeechRecognition"""
        self.engine = sr.Recognizer()
    
    def _fallback_provider(self):
        """Try fallback providers"""
        fallbacks = ["faster_whisper", "whisper", "speech_recognition"]
        for fallback in fallbacks:
            if fallback != self.provider and validate_provider("stt", fallback):
                logger.warning(f"Falling back to {fallback}")
                self.provider = fallback
                self._initialize_engine()
                return
        
        logger.error("No STT providers available")
        self.provider = None
    
    def transcribe(self, audio_data: Any, 
                   language: Optional[str] = None) -> STTResult:
        """Transcribe audio with confidence scoring"""
        if not self.provider:
            return STTResult(
                text="",
                confidence=0.0,
                language="en",
                processing_time=0.0,
                model_used=self.provider or "none",
                quality_metrics=QualityMetrics()
            )
        
        import time
        start_time = time.time()
        
        try:
            if self.provider == "faster_whisper":
                return self._transcribe_faster_whisper(audio_data, language, start_time)
            elif self.provider == "whisper":
                return self._transcribe_whisper(audio_data, language, start_time)
            elif self.provider == "speech_recognition":
                return self._transcribe_speech_recognition(audio_data, language, start_time)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            processing_time = time.time() - start_time
            return STTResult(
                text="",
                confidence=0.0,
                language=language or "en",
                processing_time=processing_time,
                model_used=self.provider,
                quality_metrics=QualityMetrics(),
                error=str(e)
            )
    
    def _transcribe_faster_whisper(self, audio_data: Any, 
                                   language: Optional[str], 
                                   start_time: float) -> STTResult:
        """Transcribe with Faster Whisper"""
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            # Save audio_data to temp_path (implementation depends on audio format)
        
        try:
            segments, info = self.model.transcribe(
                temp_path,
                language=language,
                word_timestamps=True
            )
            
            text_parts = []
            confidences = []
            
            for segment in segments:
                text_parts.append(segment.text)
                # Faster Whisper provides avg_logprob
                confidence = self._logprob_to_confidence(segment.avg_logprob)
                confidences.append(confidence)
            
            text = " ".join(text_parts).strip()
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            processing_time = time.time() - start_time
            
            return STTResult(
                text=text,
                confidence=avg_confidence,
                language=info.language,
                processing_time=processing_time,
                model_used=f"faster_whisper_{self.model_name}",
                quality_metrics=self._calculate_quality_metrics(text, avg_confidence)
            )
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def _transcribe_whisper(self, audio_data: Any, 
                            language: Optional[str], 
                            start_time: float) -> STTResult:
        """Transcribe with OpenAI Whisper"""
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = self.model.transcribe(
                temp_path,
                language=language,
                word_timestamps=True
            )
            
            text = result["text"].strip()
            # OpenAI Whisper doesn't provide direct confidence
            # Estimate from segment probabilities or use default
            confidence = 0.8  # Default reasonable confidence
            
            processing_time = time.time() - start_time
            
            return STTResult(
                text=text,
                confidence=confidence,
                language=result.get("language", "en"),
                processing_time=processing_time,
                model_used=f"whisper_{self.model_name}",
                quality_metrics=self._calculate_quality_metrics(text, confidence)
            )
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def _transcribe_speech_recognition(self, audio_data: Any, 
                                       language: Optional[str], 
                                       start_time: float) -> STTResult:
        """Transcribe with SpeechRecognition"""
        try:
            # Convert audio_data to AudioData if needed
            text = self.engine.recognize_google(audio_data, language=language)
            confidence = 0.7  # Default confidence for Google API
            
            processing_time = time.time() - start_time
            
            return STTResult(
                text=text,
                confidence=confidence,
                language=language or "en",
                processing_time=processing_time,
                model_used="speech_recognition_google",
                quality_metrics=self._calculate_quality_metrics(text, confidence)
            )
        except sr.UnknownValueError:
            processing_time = time.time() - start_time
            return STTResult(
                text="",
                confidence=0.0,
                language=language or "en",
                processing_time=processing_time,
                model_used="speech_recognition_google",
                quality_metrics=QualityMetrics(),
                error="Could not understand audio"
            )
    
    def _logprob_to_confidence(self, avg_logprob: float) -> float:
        """Convert log probability to confidence score"""
        # Transform log probability to 0-1 range
        # Typical range is -1.0 to 0.0 for good transcriptions
        confidence = max(0.0, min(1.0, (avg_logprob + 2.0) / 2.0))
        return confidence
    
    def _calculate_quality_metrics(self, text: str, confidence: float) -> QualityMetrics:
        """Calculate quality metrics for transcription"""
        word_count = len(text.split()) if text else 0
        char_count = len(text)
        
        # Estimate clarity based on text characteristics
        clarity_score = confidence
        if word_count > 0:
            avg_word_length = char_count / word_count
            # Adjust clarity based on reasonable word length
            if 3 <= avg_word_length <= 7:
                clarity_score *= 1.1
            else:
                clarity_score *= 0.9
        
        return QualityMetrics(
            clarity=min(1.0, clarity_score),
            noise_level=max(0.0, 1.0 - confidence),
            volume=0.8  # Default reasonable volume
        )
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "device": self.device,
            "available": self.provider is not None
        }