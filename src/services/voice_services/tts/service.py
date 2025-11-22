"""
Main TTS Service Implementation
"""

import time
import io
import logging
from typing import Dict, List, Optional, Tuple, Any

try:
    import torch
    import numpy as np
    import soundfile as sf
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    np = None
    sf = None
    TORCH_AVAILABLE = False

try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS = None
    TTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

from .core import TTSResult, TTSVoiceProfile
from .cache import TTSCache
from .utils import TextChunker, clean_text_for_tts, AudioFormatConverter
from .evaluation import MOSEvaluator

logger = logging.getLogger(__name__)


class EnhancedTTSService:
    """Enhanced TTS service with persona-specific voices and caching"""
    
    VOICE_PROFILES = {
        "Mary": TTSVoiceProfile(
            name="Mary",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=0.9,
            pitch_shift=2.0
        ),
        "Jake": TTSVoiceProfile(
            name="Jake",
            model_name="tts_models/en/ljspeech/tacotron2-DDC", 
            speed=1.1,
            pitch_shift=-3.0
        ),
        "Sarah": TTSVoiceProfile(
            name="Sarah",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=1.0,
            pitch_shift=1.0
        ),
        "System": TTSVoiceProfile(
            name="System",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=1.0,
            pitch_shift=0.0
        )
    }
    
    def __init__(self, cache_enabled: bool = True, gpu_enabled: bool = None):
        """Initialize Enhanced TTS Service"""
        self.cache_enabled = cache_enabled
        self.cache = TTSCache() if cache_enabled else None
        self.mos_evaluator = MOSEvaluator()
        
        # Initialize pyttsx3 as fallback
        self.tts_engine = None
        if PYTTSX3_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
            except Exception as e:
                logger.warning(f"Failed to initialize pyttsx3: {e}")

        # GPU configuration
        if gpu_enabled is None:
            self.gpu_enabled = torch.cuda.is_available() if TORCH_AVAILABLE else False
        else:
            self.gpu_enabled = gpu_enabled and TORCH_AVAILABLE
        
        self.models: Dict[str, Any] = {}
        self.enable_chunking = True
        self.max_chunk_length = 500
        
        self.stats = {
            "generations": 0,
            "cache_hits": 0,
            "total_generation_time": 0.0,
            "average_generation_time": 0.0,
            "chunked_generations": 0,
            "format_conversions": 0,
            "backend_failures": {"coqui": 0, "pyttsx3": 0},
            "total_audio_duration": 0.0,
            "avg_audio_duration": 0.0
        }
        
        logger.info(f"🔊 TTS Service initialized (GPU: {self.gpu_enabled}, Cache: {cache_enabled})")
    
    def _get_or_load_model(self, model_name: str) -> Optional[Any]:
        """Get or load TTS model"""
        if not TTS_AVAILABLE:
            logger.warning("Coqui TTS not available")
            return None
        
        if model_name not in self.models:
            try:
                device = "cuda" if self.gpu_enabled else "cpu"
                model = TTS(model_name=model_name).to(device)
                self.models[model_name] = model
                logger.info(f"✅ Loaded TTS model: {model_name} on {device}")
                
            except Exception as e:
                logger.error(f"Failed to load TTS model {model_name}: {e}")
                self.stats["backend_failures"]["coqui"] += 1
                return None
        
        return self.models.get(model_name)
    
    def synthesize_speech(self, text: str, persona_name: str = "System",
                         output_format: str = "wav") -> Optional[TTSResult]:
        """Synthesize speech for given text and persona"""
        start_time = time.time()
        
        if not text or not text.strip():
            return None
        
        voice_profile = self.VOICE_PROFILES.get(persona_name, self.VOICE_PROFILES["System"])
        clean_text = clean_text_for_tts(text)
        
        # Check cache first
        if self.cache_enabled and self.cache:
            cached_audio = self.cache.get(clean_text, voice_profile)
            if cached_audio:
                self.stats["cache_hits"] += 1
                return TTSResult(
                    audio_data=cached_audio,
                    text=text,
                    persona_name=persona_name,
                    processing_time=time.time() - start_time,
                    output_format=output_format,
                    backend_used="cache"
                )
        
        # Generate audio
        audio_data = None
        backend_used = None
        
        # Try Coqui TTS first
        if TTS_AVAILABLE:
            model = self._get_or_load_model(voice_profile.model_name)
            if model:
                try:
                    audio = model.tts(text=clean_text)
                    if audio is not None:
                        audio_data = self._audio_to_bytes(audio, output_format)
                        backend_used = "coqui"
                        
                except Exception as e:
                    logger.error(f"Coqui TTS failed: {e}")
                    self.stats["backend_failures"]["coqui"] += 1
        
        # Fallback to pyttsx3
        if not audio_data and self.tts_engine:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    self.tts_engine.save_to_file(clean_text, tmp_file.name)
                    self.tts_engine.runAndWait()
                    
                    with open(tmp_file.name, 'rb') as f:
                        audio_data = f.read()
                    backend_used = "pyttsx3"
                    
            except Exception as e:
                logger.error(f"pyttsx3 TTS failed: {e}")
                self.stats["backend_failures"]["pyttsx3"] += 1
        
        if not audio_data:
            logger.error(f"❌ All TTS backends failed for {persona_name}")
            return None
        
        # Create result
        processing_time = time.time() - start_time
        result = TTSResult(
            audio_data=audio_data,
            text=text,
            persona_name=persona_name,
            processing_time=processing_time,
            output_format=output_format,
            backend_used=backend_used
        )
        
        result.calculate_duration()
        
        # Cache the result
        if self.cache_enabled and self.cache:
            self.cache.put(clean_text, voice_profile, audio_data)
        
        # Update statistics
        self.stats["generations"] += 1
        self.stats["total_generation_time"] += processing_time
        self.stats["average_generation_time"] = (
            self.stats["total_generation_time"] / self.stats["generations"]
        )
        
        if result.duration > 0:
            self.stats["total_audio_duration"] += result.duration
            self.stats["avg_audio_duration"] = (
                self.stats["total_audio_duration"] / self.stats["generations"]
            )
        
        logger.info(f"✅ TTS generated for {persona_name} ({processing_time:.2f}s, backend: {backend_used})")
        return result
    
    def _audio_to_bytes(self, audio: Any, output_format: str) -> bytes:
        """Convert audio array to bytes"""
        if not TORCH_AVAILABLE or np is None or sf is None:
            return b""
        
        try:
            if hasattr(audio, 'numpy'):
                audio = audio.numpy()
            
            if audio.dtype != np.int16:
                audio = (audio * 32767).astype(np.int16)
            
            buffer = io.BytesIO()
            sf.write(buffer, audio, samplerate=22050, format='WAV')
            buffer.seek(0)
            
            return buffer.read()
            
        except Exception as e:
            logger.error(f"Error converting audio to bytes: {e}")
            return b""
    
    def get_stats(self) -> Dict:
        """Get TTS service statistics"""
        cache_stats = {}
        if self.cache:
            cache_stats = {
                "cache_entries": len(self.cache.metadata["entries"]),
                "cache_size_mb": round(self.cache.metadata["total_size"] / 1024 / 1024, 2)
            }
        
        return {
            **self.stats,
            "cache_hit_rate": (self.stats["cache_hits"] / max(self.stats["generations"], 1)) * 100,
            "loaded_models": list(self.models.keys()),
            "gpu_enabled": self.gpu_enabled,
            "supported_formats": AudioFormatConverter.get_supported_formats(),
            **cache_stats
        }
    
    def clear_cache(self):
        """Clear TTS cache"""
        if self.cache:
            self.cache.clear()
    
    def get_available_voices(self) -> List[Dict]:
        """Get list of available voice profiles"""
        return [profile.to_dict() for profile in self.VOICE_PROFILES.values()]


# Singleton pattern
_tts_service = None

def get_tts_service() -> EnhancedTTSService:
    """Get singleton TTS service instance"""
    global _tts_service
    if _tts_service is None:
        _tts_service = EnhancedTTSService()
    return _tts_service


class TTSService:
    """Simplified TTS service wrapper for compatibility"""
    
    def __init__(self):
        self.enhanced_service = get_tts_service()
        
    async def text_to_speech(self, text: str, emotion=None, speaker_voice: str = "default", 
                           language: str = "en", output_format: str = "wav") -> Optional[bytes]:
        """Convert text to speech with async interface"""
        try:
            persona_name = speaker_voice if speaker_voice != "default" else "System"
            
            result = self.enhanced_service.synthesize_speech(
                text, persona_name=persona_name, output_format=output_format
            )
            
            return result.audio_data if result else None
            
        except Exception as e:
            logger.error(f"TTS async wrapper failed: {e}")
            return None