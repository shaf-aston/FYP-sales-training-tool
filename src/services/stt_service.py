"""
Enhanced STT (Speech-to-Text) Layer
Provides speech recognition using OpenAI Whisper for voice input processing
"""
import os
import io
import time
import logging
import hashlib
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
import json
import tempfile

try:
    import whisper
    import torch
    import numpy as np
    import librosa
    WHISPER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Whisper not available: {e}")
    WHISPER_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)


class STTResult:
    """Speech-to-text result with metadata"""
    
    def __init__(self, text: str, confidence: float, language: str = "en",
                 duration: float = 0.0, processing_time: float = 0.0):
        """
        Initialize STT result
        
        Args:
            text: Transcribed text
            confidence: Confidence score (0.0-1.0)
            language: Detected language
            duration: Audio duration in seconds
            processing_time: Processing time in seconds
        """
        self.text = text
        self.confidence = confidence
        self.language = language
        self.duration = duration
        self.processing_time = processing_time
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp
        }


class STTCache:
    """Caching system for STT results"""
    
    def __init__(self, cache_dir: Path = None, max_cache_size_mb: int = 100):
        """Initialize STT cache"""
        if cache_dir is None:
            cache_dir = PROJECT_ROOT / "model_cache" / "stt_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024
        
        # Cache metadata
        self.metadata_file = self.cache_dir / "stt_cache_metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading STT cache metadata: {e}")
        
        return {"entries": {}, "total_size": 0}
    
    def _save_metadata(self):
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving STT cache metadata: {e}")
    
    def _get_audio_hash(self, audio_data: bytes) -> str:
        """Generate hash for audio data"""
        return hashlib.md5(audio_data).hexdigest()
    
    def get(self, audio_data: bytes) -> Optional[STTResult]:
        """Get cached STT result"""
        audio_hash = self._get_audio_hash(audio_data)
        
        if audio_hash in self.metadata["entries"]:
            try:
                # Update access time
                self.metadata["entries"][audio_hash]["last_accessed"] = time.time()
                self._save_metadata()
                
                # Return cached result
                entry = self.metadata["entries"][audio_hash]
                return STTResult(
                    text=entry["text"],
                    confidence=entry["confidence"],
                    language=entry["language"],
                    duration=entry["duration"],
                    processing_time=0.0  # Cache hit, no processing time
                )
                
            except Exception as e:
                logger.error(f"Error reading STT cache: {e}")
        
        return None
    
    def put(self, audio_data: bytes, result: STTResult):
        """Cache STT result"""
        audio_hash = self._get_audio_hash(audio_data)
        
        try:
            # Estimate entry size
            entry_size = len(audio_hash) + len(result.text) + 200  # Rough estimate
            
            # Check if we need to clean up
            self._cleanup_if_needed(entry_size)
            
            # Store result
            self.metadata["entries"][audio_hash] = {
                "text": result.text,
                "confidence": result.confidence,
                "language": result.language,
                "duration": result.duration,
                "created": result.timestamp,
                "last_accessed": result.timestamp,
                "size": entry_size
            }
            
            self.metadata["total_size"] += entry_size
            self._save_metadata()
            
            logger.debug(f"Cached STT result for audio hash: {audio_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"Error caching STT result: {e}")
    
    def _cleanup_if_needed(self, new_entry_size: int):
        """Clean up cache if size limit would be exceeded"""
        if self.metadata["total_size"] + new_entry_size <= self.max_cache_size:
            return
        
        logger.info("STT cache size limit reached, cleaning up...")
        
        # Sort by last accessed time
        entries_by_age = sorted(
            self.metadata["entries"].items(),
            key=lambda x: x[1]["last_accessed"]
        )
        
        # Remove oldest entries
        removed_size = 0
        for audio_hash, entry in entries_by_age:
            removed_size += entry["size"]
            del self.metadata["entries"][audio_hash]
            
            if removed_size >= new_entry_size:
                break
        
        self.metadata["total_size"] -= removed_size
        logger.info(f"Cleaned up {removed_size} bytes from STT cache")


class EnhancedSTTService:
    """Enhanced Speech-to-Text service with multiple backends"""
    
    def __init__(self, primary_backend: str = "whisper", cache_enabled: bool = True,
                 gpu_enabled: bool = None):
        """
        Initialize Enhanced STT Service
        
        Args:
            primary_backend: Primary STT backend ("whisper", "speech_recognition")
            cache_enabled: Enable result caching
            gpu_enabled: Use GPU acceleration if available
        """
        self.primary_backend = primary_backend
        self.cache_enabled = cache_enabled
        self.cache = STTCache() if cache_enabled else None
        
        # Auto-detect GPU availability
        if gpu_enabled is None:
            self.gpu_enabled = torch.cuda.is_available() if WHISPER_AVAILABLE else False
        else:
            self.gpu_enabled = gpu_enabled and WHISPER_AVAILABLE
        
        # Backend models
        self.whisper_model = None
        self.speech_recognizer = None
        
        # Performance tracking
        self.stats = {
            "transcriptions": 0,
            "cache_hits": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "backend_usage": {
                "whisper": 0,
                "speech_recognition": 0,
                "fallback": 0
            }
        }
        
        # Initialize backends
        self._initialize_backends()
        
        logger.info(f"🎤 Enhanced STT Service initialized (Backend: {primary_backend}, GPU: {self.gpu_enabled})")
    
    def _initialize_backends(self):
        """Initialize available STT backends"""
        # Initialize Whisper
        if WHISPER_AVAILABLE and self.primary_backend == "whisper":
            try:
                model_name = "base"  # Good balance of speed and accuracy
                logger.info(f"Loading Whisper model: {model_name}")
                
                self.whisper_model = whisper.load_model(
                    model_name,
                    device="cuda" if self.gpu_enabled else "cpu"
                )
                
                logger.info("✅ Whisper model loaded successfully")
                
            except Exception as e:
                logger.error(f"❌ Error loading Whisper model: {e}")
                self.whisper_model = None
        
        # Initialize SpeechRecognition as fallback
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.speech_recognizer = sr.Recognizer()
                
                # Adjust for ambient noise (optional)
                # This would require a microphone input in practice
                
                logger.info("✅ SpeechRecognition initialized")
                
            except Exception as e:
                logger.error(f"❌ Error initializing SpeechRecognition: {e}")
                self.speech_recognizer = None
    
    def transcribe_audio(self, audio_data: Union[bytes, np.ndarray, str], 
                        language: str = None) -> Optional[STTResult]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio data (bytes, numpy array, or file path)
            language: Expected language code (e.g., "en", "es")
        
        Returns:
            STTResult with transcription and metadata
        """
        start_time = time.time()
        
        # Convert input to bytes if needed
        if isinstance(audio_data, str):
            # File path
            try:
                with open(audio_data, 'rb') as f:
                    audio_bytes = f.read()
            except Exception as e:
                logger.error(f"Error reading audio file {audio_data}: {e}")
                return None
        elif isinstance(audio_data, np.ndarray):
            # Convert numpy array to bytes
            audio_bytes = self._numpy_to_wav_bytes(audio_data)
        else:
            # Assume bytes
            audio_bytes = audio_data
        
        # Check cache first
        if self.cache_enabled and self.cache:
            cached_result = self.cache.get(audio_bytes)
            if cached_result:
                self.stats["cache_hits"] += 1
                logger.debug("🎯 STT cache hit")
                return cached_result
        
        # Try primary backend first
        result = None
        
        if self.primary_backend == "whisper" and self.whisper_model:
            result = self._transcribe_with_whisper(audio_bytes, language)
            if result:
                self.stats["backend_usage"]["whisper"] += 1
        
        # Fallback to speech_recognition
        if not result and self.speech_recognizer:
            result = self._transcribe_with_speech_recognition(audio_bytes, language)
            if result:
                self.stats["backend_usage"]["speech_recognition"] += 1
        
        # Final fallback
        if not result:
            result = STTResult(
                text="[Audio transcription failed]",
                confidence=0.0,
                language=language or "en",
                processing_time=time.time() - start_time
            )
            self.stats["backend_usage"]["fallback"] += 1
        
        # Update processing time
        if result:
            result.processing_time = time.time() - start_time
        
        # Cache the result
        if self.cache_enabled and self.cache and result and result.confidence > 0.5:
            self.cache.put(audio_bytes, result)
        
        # Update statistics
        self.stats["transcriptions"] += 1
        self.stats["total_processing_time"] += result.processing_time if result else 0
        self.stats["average_processing_time"] = (
            self.stats["total_processing_time"] / self.stats["transcriptions"]
        )
        
        if result:
            logger.info(f"🎤 Audio transcribed: '{result.text[:50]}...' (conf: {result.confidence:.2f})")
        
        return result
    
    def _transcribe_with_whisper(self, audio_bytes: bytes, language: str = None) -> Optional[STTResult]:
        """Transcribe using Whisper model"""
        try:
            # Save audio to temporary file (Whisper needs file input)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Transcribe with Whisper
                options = {}
                if language:
                    options["language"] = language
                
                result = self.whisper_model.transcribe(tmp_path, **options)
                
                # Extract transcription
                text = result.get("text", "").strip()
                
                # Calculate confidence (Whisper doesn't provide direct confidence)
                # Use average of segment confidence if available
                segments = result.get("segments", [])
                if segments:
                    confidences = []
                    for segment in segments:
                        if "avg_logprob" in segment:
                            # Convert log probability to confidence score
                            conf = min(1.0, max(0.0, (segment["avg_logprob"] + 1.0)))
                            confidences.append(conf)
                    
                    confidence = sum(confidences) / len(confidences) if confidences else 0.8
                else:
                    confidence = 0.8 if text else 0.0
                
                # Get detected language
                detected_language = result.get("language", language or "en")
                
                return STTResult(
                    text=text,
                    confidence=confidence,
                    language=detected_language
                )
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error in Whisper transcription: {e}")
            return None
    
    def _transcribe_with_speech_recognition(self, audio_bytes: bytes, language: str = None) -> Optional[STTResult]:
        """Transcribe using SpeechRecognition library"""
        try:
            # Convert bytes to AudioData
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Load audio file
                with sr.AudioFile(tmp_path) as source:
                    audio = self.speech_recognizer.record(source)
                
                # Try Google Web Speech API (free but requires internet)
                try:
                    text = self.speech_recognizer.recognize_google(
                        audio, 
                        language=language or "en-US"
                    )
                    confidence = 0.7  # Estimate - Google doesn't provide confidence
                    
                    return STTResult(
                        text=text,
                        confidence=confidence,
                        language=language or "en"
                    )
                    
                except sr.UnknownValueError:
                    logger.warning("Google Speech Recognition could not understand audio")
                except sr.RequestError as e:
                    logger.warning(f"Google Speech Recognition error: {e}")
                
                # Fallback to offline recognition (if available)
                try:
                    text = self.speech_recognizer.recognize_sphinx(audio)
                    confidence = 0.5  # Lower confidence for offline recognition
                    
                    return STTResult(
                        text=text,
                        confidence=confidence,
                        language=language or "en"
                    )
                    
                except sr.UnknownValueError:
                    logger.warning("Sphinx could not understand audio")
                except sr.RequestError as e:
                    logger.warning(f"Sphinx error: {e}")
                
            finally:
                # Clean up
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error in SpeechRecognition transcription: {e}")
        
        return None
    
    def _numpy_to_wav_bytes(self, audio_array: np.ndarray, sample_rate: int = 16000) -> bytes:
        """Convert numpy array to WAV bytes"""
        try:
            import soundfile as sf
            
            buffer = io.BytesIO()
            sf.write(buffer, audio_array, sample_rate, format='WAV')
            buffer.seek(0)
            
            return buffer.read()
            
        except Exception as e:
            logger.error(f"Error converting numpy to WAV: {e}")
            return b""
    
    def transcribe_stream(self, audio_stream: io.BytesIO, 
                         chunk_duration: float = 5.0) -> List[STTResult]:
        """
        Transcribe streaming audio in chunks
        
        Args:
            audio_stream: Audio stream
            chunk_duration: Duration of each chunk in seconds
        
        Returns:
            List of STTResult for each chunk
        """
        results = []
        
        try:
            # This is a simplified implementation
            # In practice, you'd need proper audio chunking
            audio_data = audio_stream.read()
            
            # For now, just transcribe the entire stream
            result = self.transcribe_audio(audio_data)
            if result:
                results.append(result)
            
        except Exception as e:
            logger.error(f"Error in stream transcription: {e}")
        
        return results
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        if self.primary_backend == "whisper":
            # Whisper supports many languages
            return [
                "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh",
                "ar", "hi", "tr", "pl", "nl", "sv", "da", "no", "fi"
            ]
        else:
            # SpeechRecognition with Google supports many languages
            return ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
    
    def validate_audio(self, audio_data: bytes) -> Dict[str, Union[bool, str]]:
        """
        Validate audio data for STT processing
        
        Returns:
            Dict with validation results
        """
        validation = {
            "valid": True,
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check file size
            if len(audio_data) < 1000:  # Less than 1KB
                validation["valid"] = False
                validation["issues"].append("Audio file too small")
            
            if len(audio_data) > 25 * 1024 * 1024:  # Larger than 25MB
                validation["valid"] = False
                validation["issues"].append("Audio file too large")
                validation["recommendations"].append("Consider splitting into smaller chunks")
            
            # Try to load audio to check format
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    tmp_file.write(audio_data)
                    tmp_path = tmp_file.name
                
                # Use librosa to validate
                if WHISPER_AVAILABLE:
                    audio, sr = librosa.load(tmp_path, sr=None)
                    
                    # Check duration
                    duration = len(audio) / sr
                    if duration < 0.1:
                        validation["issues"].append("Audio too short (< 0.1s)")
                    elif duration > 300:  # 5 minutes
                        validation["recommendations"].append("Consider splitting long audio")
                    
                    # Check sample rate
                    if sr < 8000:
                        validation["recommendations"].append("Low sample rate may affect quality")
                
                # Clean up
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
            except Exception as e:
                validation["valid"] = False
                validation["issues"].append(f"Cannot process audio format: {e}")
        
        except Exception as e:
            validation["valid"] = False
            validation["issues"].append(f"Audio validation error: {e}")
        
        return validation
    
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
            "whisper_available": WHISPER_AVAILABLE and self.whisper_model is not None,
            "speech_recognition_available": SPEECH_RECOGNITION_AVAILABLE and self.speech_recognizer is not None,
            **cache_stats
        }
    
    def clear_cache(self):
        """Clear STT cache"""
        if self.cache:
            self.cache.clear()


# Global STT service instance
_stt_service = None

def get_stt_service() -> EnhancedSTTService:
    """Get singleton STT service instance"""
    global _stt_service
    if _stt_service is None:
        _stt_service = EnhancedSTTService()
    return _stt_service

def initialize_stt_service(backend: str = "whisper", cache_enabled: bool = True,
                          gpu_enabled: bool = None) -> EnhancedSTTService:
    """Initialize STT service with specific configuration"""
    global _stt_service
    _stt_service = EnhancedSTTService(backend, cache_enabled, gpu_enabled)
    return _stt_service