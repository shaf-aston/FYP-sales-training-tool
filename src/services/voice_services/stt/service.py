"""
Main STT Service Implementation
"""

import time
import logging
from typing import Dict, List, Optional, Tuple

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

from .core import STTResult
from .cache import STTCache
from .preprocessing import AudioPreprocessor
from .backends import (
    WhisperBackend, FasterWhisperBackend, 
    SpeechRecognitionBackend, GoogleCloudSTTBackend,
    WHISPER_AVAILABLE, FASTER_WHISPER_AVAILABLE,
    SPEECH_RECOGNITION_AVAILABLE, GOOGLE_STT_AVAILABLE
)

logger = logging.getLogger(__name__)


class EnhancedSTTService:
    """Enhanced Speech-to-Text service with multiple backends and caching"""
    
    def __init__(self, primary_backend: str = "whisper", cache_enabled: bool = True,
                 gpu_enabled: bool = None, model_size: str = "base",
                 enable_preprocessing: bool = True):
        """Initialize Enhanced STT Service"""
        self.primary_backend = primary_backend
        self.cache_enabled = cache_enabled
        self.enable_preprocessing = enable_preprocessing
        self.cache = STTCache() if cache_enabled else None
        
        # GPU configuration
        if gpu_enabled is None:
            self.gpu_enabled = torch.cuda.is_available() if TORCH_AVAILABLE else False
        else:
            self.gpu_enabled = gpu_enabled and TORCH_AVAILABLE
        
        self.device = "cuda" if self.gpu_enabled else "cpu"
        self.model_size = model_size
        
        # Initialize backends
        self.whisper_backend = None
        self.faster_whisper_backend = None
        self.sr_backend = None
        self.google_backend = None
        
        self.stats = {
            "transcriptions": 0,
            "cache_hits": 0,
            "total_transcription_time": 0.0,
            "average_transcription_time": 0.0,
            "preprocessing_failures": 0,
            "backend_failures": {"whisper": 0, "faster_whisper": 0, "speech_recognition": 0, "google": 0},
            "avg_confidence": 0.0,
            "wer_evaluations": 0,
            "avg_wer": 0.0
        }
        
        self._initialize_backends()
        logger.info(f"🎤 STT Service initialized (Primary: {primary_backend}, GPU: {self.gpu_enabled})")
    
    def _initialize_backends(self):
        """Initialize STT backends based on availability"""
        # Initialize primary backend
        if self.primary_backend == "whisper":
            if FASTER_WHISPER_AVAILABLE:
                try:
                    self.faster_whisper_backend = FasterWhisperBackend(self.model_size, self.device)
                    logger.info("✅ Faster Whisper backend initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize Faster Whisper: {e}")
            
            if WHISPER_AVAILABLE and not self.faster_whisper_backend:
                try:
                    self.whisper_backend = WhisperBackend(self.model_size, self.device)
                    logger.info("✅ Whisper backend initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize Whisper: {e}")
        
        # Initialize fallback backends
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.sr_backend = SpeechRecognitionBackend()
                logger.info("✅ SpeechRecognition backend initialized")
            except Exception as e:
                logger.error(f"Failed to initialize SpeechRecognition: {e}")
        
        if GOOGLE_STT_AVAILABLE:
            try:
                self.google_backend = GoogleCloudSTTBackend()
                logger.info("✅ Google Cloud STT backend initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Google Cloud STT: {e}")
    
    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000, 
                        language: str = "en", ground_truth: str = None) -> Optional[STTResult]:
        """Transcribe audio data to text with preprocessing and fallback"""
        start_time = time.time()
        
        if not audio_data:
            return None
        
        # Audio preprocessing
        processed_audio = audio_data
        if self.enable_preprocessing:
            try:
                validation = AudioPreprocessor.validate_audio_format(audio_data)
                if not validation["valid"]:
                    logger.warning(f"Audio validation issues: {validation['issues']}")
                    self.stats["preprocessing_failures"] += 1
                
                # Apply noise reduction if available
                processed_audio = AudioPreprocessor.apply_noise_reduction(audio_data, sample_rate)
                processed_audio = AudioPreprocessor.normalize_audio_level(processed_audio)
                
            except Exception as e:
                logger.error(f"Audio preprocessing failed: {e}")
                self.stats["preprocessing_failures"] += 1
        
        # Check cache
        if self.cache_enabled and self.cache:
            cached_result = self.cache.get(processed_audio)
            if cached_result:
                self.stats["cache_hits"] += 1
                logger.debug("STT cache hit")
                return cached_result
        
        # Try backends in order of preference
        result = None
        
        # Primary backend (Faster Whisper or Whisper)
        if not result and self.faster_whisper_backend:
            try:
                result = self.faster_whisper_backend.transcribe(processed_audio, language)
            except Exception as e:
                logger.error(f"Faster Whisper failed: {e}")
                self.stats["backend_failures"]["faster_whisper"] += 1
        
        if not result and self.whisper_backend:
            try:
                result = self.whisper_backend.transcribe(processed_audio, language)
            except Exception as e:
                logger.error(f"Whisper failed: {e}")
                self.stats["backend_failures"]["whisper"] += 1
        
        # Fallback to SpeechRecognition
        if not result and self.sr_backend:
            try:
                result = self.sr_backend.transcribe(processed_audio, language)
            except Exception as e:
                logger.error(f"SpeechRecognition failed: {e}")
                self.stats["backend_failures"]["speech_recognition"] += 1
        
        # Last resort: Google Cloud STT
        if not result and self.google_backend:
            try:
                result = self.google_backend.transcribe(processed_audio, f"{language}-US", sample_rate)
            except Exception as e:
                logger.error(f"Google Cloud STT failed: {e}")
                self.stats["backend_failures"]["google"] += 1
        
        if result:
            # Set processing time
            result.processing_time = time.time() - start_time
            
            # Calculate WER if ground truth provided
            if ground_truth:
                result.calculate_wer(ground_truth)
                self.stats["wer_evaluations"] += 1
                if result.wer_score is not None:
                    self.stats["avg_wer"] = (
                        (self.stats["avg_wer"] * (self.stats["wer_evaluations"] - 1) + result.wer_score)
                        / self.stats["wer_evaluations"]
                    )
            
            # Cache the result
            if self.cache_enabled and self.cache:
                self.cache.put(processed_audio, result)
            
            # Update statistics
            self.stats["transcriptions"] += 1
            self.stats["total_transcription_time"] += result.processing_time
            self.stats["average_transcription_time"] = (
                self.stats["total_transcription_time"] / self.stats["transcriptions"]
            )
            
            # Update confidence
            self.stats["avg_confidence"] = (
                (self.stats["avg_confidence"] * (self.stats["transcriptions"] - 1) + result.confidence)
                / self.stats["transcriptions"]
            )
            
            logger.info(f"✅ STT transcription successful ({result.processing_time:.2f}s, backend: {result.backend_used})")
            return result
        else:
            logger.error("❌ All STT backends failed")
            return None
    
    def get_stats(self) -> Dict:
        """Get STT service statistics"""
        cache_stats = {}
        if self.cache:
            cache_stats = {
                "cache_entries": len(self.cache.metadata["entries"]),
                "cache_size_mb": round(self.cache.metadata["total_size"] / 1024 / 1024, 2)
            }
        
        return {
            **self.stats,
            "cache_hit_rate": (self.stats["cache_hits"] / max(self.stats["transcriptions"], 1)) * 100,
            "primary_backend": self.primary_backend,
            "gpu_enabled": self.gpu_enabled,
            "available_backends": self._get_available_backends(),
            **cache_stats
        }
    
    def _get_available_backends(self) -> List[str]:
        """Get list of available backends"""
        backends = []
        if self.faster_whisper_backend:
            backends.append("faster_whisper")
        if self.whisper_backend:
            backends.append("whisper")
        if self.sr_backend:
            backends.append("speech_recognition")
        if self.google_backend:
            backends.append("google_cloud")
        return backends
    
    def clear_cache(self):
        """Clear STT cache"""
        if self.cache:
            self.cache.clear()


# Singleton pattern
_stt_service = None

def get_stt_service() -> EnhancedSTTService:
    """Get singleton STT service instance"""
    global _stt_service
    if _stt_service is None:
        _stt_service = EnhancedSTTService()
    return _stt_service