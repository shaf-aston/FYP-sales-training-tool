"""
Enhanced STT (Speech-to-Text) Layer
Provides speech recognition using OpenAI Whisper for voice input processing
"""
import os
import io
import time
import logging
import hashlib
from typing import Dict, List, Optional, Union, Tuple, Any
from pathlib import Path
import json
import tempfile

try:
    import whisper
    import torch
    try:
        import numpy as np
        NUMPY_AVAILABLE = True
    except ImportError:
        NUMPY_AVAILABLE = False
        logging.warning("NumPy not available - some features will be limited")
    import librosa
    WHISPER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Whisper not available: {e}")
    WHISPER_AVAILABLE = False
    NUMPY_AVAILABLE = False

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



    

    
    def transcribe_audio(self, audio_data: Union[bytes, Any, str], 
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
        elif NUMPY_AVAILABLE and hasattr(audio_data, 'dtype'):  # Check if it's array-like
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
    

    

    
    def _numpy_to_wav_bytes(self, audio_array: Any, sample_rate: int = 16000) -> bytes:
        """Convert numpy array to WAV bytes"""
        if not NUMPY_AVAILABLE:
            logger.error("NumPy not available for audio conversion")
            return b""
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