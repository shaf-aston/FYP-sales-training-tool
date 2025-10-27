"""
Enhanced TTS (Text-to-Speech) Layer
Provides high-quality voice synthesis using Coqui TTS with persona-specific voices
"""
import os
import io
import time
import logging
import hashlib
from typing import Dict, List, Optional, Union
from pathlib import Path
import json

try:
    from TTS.api import TTS
    import torch
    import soundfile as sf
    import numpy as np
    TTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Coqui TTS not available: {e}")
    TTS_AVAILABLE = False

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)


class TTSVoiceProfile:
    """Voice profile for different personas"""
    
    def __init__(self, name: str, model_name: str, speaker_id: Optional[str] = None,
                 language: str = "en", speed: float = 1.0, pitch_shift: float = 0.0):
        """
        Initialize voice profile
        
        Args:
            name: Profile name (e.g., "Mary", "Jake")
            model_name: TTS model name
            speaker_id: Speaker ID if multi-speaker model
            language: Language code
            speed: Speaking speed multiplier (0.5-2.0)
            pitch_shift: Pitch shift in semitones (-12 to 12)
        """
        self.name = name
        self.model_name = model_name
        self.speaker_id = speaker_id
        self.language = language
        self.speed = speed
        self.pitch_shift = pitch_shift
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "model_name": self.model_name,
            "speaker_id": self.speaker_id,
            "language": self.language,
            "speed": self.speed,
            "pitch_shift": self.pitch_shift
        }


class TTSCache:
    """Caching system for TTS outputs"""
    
    def __init__(self, cache_dir: Path = None, max_cache_size_mb: int = 500):
        """Initialize TTS cache"""
        if cache_dir is None:
            cache_dir = PROJECT_ROOT / "model_cache" / "tts_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        
        # Cache metadata file
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading cache metadata: {e}")
        
        return {"entries": {}, "total_size": 0}
    
    def _save_metadata(self):
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache metadata: {e}")
    
    def _get_cache_key(self, text: str, voice_profile: TTSVoiceProfile) -> str:
        """Generate cache key for text and voice profile"""
        # Create unique hash based on text and voice settings
        content = f"{text}_{voice_profile.model_name}_{voice_profile.speaker_id}_{voice_profile.speed}_{voice_profile.pitch_shift}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, text: str, voice_profile: TTSVoiceProfile) -> Optional[bytes]:
        """Get cached audio data"""
        cache_key = self._get_cache_key(text, voice_profile)
        cache_file = self.cache_dir / f"{cache_key}.wav"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    audio_data = f.read()
                
                # Update access time in metadata
                if cache_key in self.metadata["entries"]:
                    self.metadata["entries"][cache_key]["last_accessed"] = time.time()
                    self._save_metadata()
                
                logger.debug(f"TTS cache hit for key: {cache_key[:8]}...")
                return audio_data
                
            except Exception as e:
                logger.error(f"Error reading cached TTS: {e}")
        
        return None
    
    def put(self, text: str, voice_profile: TTSVoiceProfile, audio_data: bytes):
        """Cache audio data"""
        cache_key = self._get_cache_key(text, voice_profile)
        cache_file = self.cache_dir / f"{cache_key}.wav"
        
        try:
            # Check cache size limits
            self._cleanup_if_needed(len(audio_data))
            
            # Write audio data
            with open(cache_file, 'wb') as f:
                f.write(audio_data)
            
            # Update metadata
            self.metadata["entries"][cache_key] = {
                "text": text[:100],  # Store first 100 chars for reference
                "voice_profile": voice_profile.name,
                "file_size": len(audio_data),
                "created": time.time(),
                "last_accessed": time.time()
            }
            self.metadata["total_size"] += len(audio_data)
            self._save_metadata()
            
            logger.debug(f"Cached TTS audio for key: {cache_key[:8]}...")
            
        except Exception as e:
            logger.error(f"Error caching TTS audio: {e}")
    
    def _cleanup_if_needed(self, new_entry_size: int):
        """Clean up cache if size limit would be exceeded"""
        if self.metadata["total_size"] + new_entry_size <= self.max_cache_size:
            return
        
        logger.info("TTS cache size limit reached, cleaning up...")
        
        # Sort entries by last accessed time (oldest first)
        entries_by_age = sorted(
            self.metadata["entries"].items(),
            key=lambda x: x[1]["last_accessed"]
        )
        
        # Remove oldest entries until we have enough space
        removed_size = 0
        for cache_key, entry in entries_by_age:
            cache_file = self.cache_dir / f"{cache_key}.wav"
            
            if cache_file.exists():
                cache_file.unlink()
            
            removed_size += entry["file_size"]
            del self.metadata["entries"][cache_key]
            
            if removed_size >= new_entry_size:
                break
        
        self.metadata["total_size"] -= removed_size
        logger.info(f"Cleaned up {removed_size} bytes from TTS cache")
    
    def clear(self):
        """Clear entire cache"""
        try:
            for cache_file in self.cache_dir.glob("*.wav"):
                cache_file.unlink()
            
            self.metadata = {"entries": {}, "total_size": 0}
            self._save_metadata()
            logger.info("TTS cache cleared")
            
        except Exception as e:
            logger.error(f"Error clearing TTS cache: {e}")


class EnhancedTTSService:
    """Enhanced TTS service with persona-specific voices and caching"""
    
    # Predefined voice profiles for different personas
    VOICE_PROFILES = {
        "Mary": TTSVoiceProfile(
            name="Mary",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=0.9,  # Slightly slower for older character
            pitch_shift=2.0  # Slightly higher pitch for female voice
        ),
        "Jake": TTSVoiceProfile(
            name="Jake",
            model_name="tts_models/en/ljspeech/tacotron2-DDC", 
            speed=1.1,  # Faster for busy executive
            pitch_shift=-3.0  # Lower pitch for male voice
        ),
        "Sarah": TTSVoiceProfile(
            name="Sarah",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=1.0,  # Normal speed
            pitch_shift=1.0  # Slightly higher for young female
        ),
        "David": TTSVoiceProfile(
            name="David",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=0.95,  # Slightly slower, more thoughtful
            pitch_shift=-1.0  # Slightly lower for mature male
        ),
        "System": TTSVoiceProfile(
            name="System",
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            speed=1.0,
            pitch_shift=0.0  # Neutral voice for system messages
        )
    }
    
    def __init__(self, cache_enabled: bool = True, gpu_enabled: bool = None):
        """Initialize Enhanced TTS Service"""
        self.cache_enabled = cache_enabled
        self.cache = TTSCache() if cache_enabled else None
        
        # Auto-detect GPU availability
        if gpu_enabled is None:
            self.gpu_enabled = torch.cuda.is_available() if TTS_AVAILABLE else False
        else:
            self.gpu_enabled = gpu_enabled and TTS_AVAILABLE
        
        # TTS models cache
        self.models: Dict[str, TTS] = {}
        
        # Performance tracking
        self.stats = {
            "generations": 0,
            "cache_hits": 0,
            "total_generation_time": 0.0,
            "average_generation_time": 0.0
        }
        
        logger.info(f"🔊 Enhanced TTS Service initialized (GPU: {self.gpu_enabled}, Cache: {cache_enabled})")
    
    def _get_or_load_model(self, model_name: str) -> Optional[TTS]:
        """Get or load TTS model"""
        if not TTS_AVAILABLE:
            logger.warning("Coqui TTS not available")
            return None
        
        if model_name not in self.models:
            try:
                logger.info(f"Loading TTS model: {model_name}")
                
                # Initialize TTS model
                tts = TTS(model_name=model_name, progress_bar=False)
                
                # Move to GPU if available
                if self.gpu_enabled and hasattr(tts, 'to'):
                    tts.to("cuda")
                
                self.models[model_name] = tts
                logger.info(f"✅ TTS model loaded: {model_name}")
                
            except Exception as e:
                logger.error(f"❌ Error loading TTS model {model_name}: {e}")
                return None
        
        return self.models.get(model_name)
    
    def synthesize_speech(self, text: str, persona_name: str = "System",
                         output_format: str = "wav") -> Optional[bytes]:
        """
        Synthesize speech for given text and persona
        
        Args:
            text: Text to synthesize
            persona_name: Persona name (Mary, Jake, Sarah, David, System)
            output_format: Output audio format (wav, mp3)
        
        Returns:
            Audio data as bytes or None if failed
        """
        start_time = time.time()
        
        if not text or not text.strip():
            return None
        
        # Get voice profile
        voice_profile = self.VOICE_PROFILES.get(persona_name, self.VOICE_PROFILES["System"])
        
        # Check cache first
        if self.cache_enabled and self.cache:
            cached_audio = self.cache.get(text, voice_profile)
            if cached_audio:
                self.stats["cache_hits"] += 1
                logger.debug(f"🎯 TTS cache hit for {persona_name}: {text[:30]}...")
                return cached_audio
        
        # Generate speech
        try:
            # Get TTS model
            model = self._get_or_load_model(voice_profile.model_name)
            if not model:
                logger.error(f"TTS model not available: {voice_profile.model_name}")
                return None
            
            logger.info(f"🔊 Generating TTS for {persona_name}: {text[:50]}...")
            
            # Clean text for TTS
            clean_text = self._clean_text_for_tts(text)
            
            # Generate audio
            if hasattr(model, 'tts'):
                # Standard TTS generation
                audio = model.tts(text=clean_text, speaker=voice_profile.speaker_id)
            else:
                # Fallback method
                audio = model.synthesize(clean_text)
            
            # Convert to numpy array if needed
            if not isinstance(audio, np.ndarray):
                audio = np.array(audio)
            
            # Apply voice modifications
            audio = self._apply_voice_modifications(audio, voice_profile)
            
            # Convert to bytes
            audio_bytes = self._audio_to_bytes(audio, output_format)
            
            # Cache the result
            if self.cache_enabled and self.cache and audio_bytes:
                self.cache.put(text, voice_profile, audio_bytes)
            
            # Update statistics
            generation_time = time.time() - start_time
            self.stats["generations"] += 1
            self.stats["total_generation_time"] += generation_time
            self.stats["average_generation_time"] = (
                self.stats["total_generation_time"] / self.stats["generations"]
            )
            
            logger.info(f"✅ TTS generated for {persona_name} ({generation_time:.2f}s)")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"❌ TTS generation error for {persona_name}: {e}")
            return None
    
    def _clean_text_for_tts(self, text: str) -> str:
        """Clean and prepare text for TTS synthesis"""
        # Remove or replace problematic characters
        text = text.strip()
        
        # Replace common markdown/formatting
        text = text.replace("**", "")  # Bold
        text = text.replace("*", "")   # Italic
        text = text.replace("_", "")   # Underscore
        text = text.replace("`", "")   # Code blocks
        
        # Handle abbreviations
        abbreviations = {
            " vs ": " versus ",
            " etc.": " etcetera",
            " i.e.": " that is",
            " e.g.": " for example",
            " Mr.": " Mister",
            " Mrs.": " Missis",
            " Dr.": " Doctor"
        }
        
        for abbr, expansion in abbreviations.items():
            text = text.replace(abbr, expansion)
        
        # Limit length (TTS models have token limits)
        if len(text) > 500:
            text = text[:497] + "..."
            logger.warning("Text truncated for TTS generation")
        
        return text
    
    def _apply_voice_modifications(self, audio: np.ndarray, voice_profile: TTSVoiceProfile) -> np.ndarray:
        """Apply voice modifications like speed and pitch"""
        try:
            # Speed modification
            if voice_profile.speed != 1.0:
                # Simple time stretching (in production, use librosa for better quality)
                target_length = int(len(audio) / voice_profile.speed)
                if target_length > 0:
                    indices = np.linspace(0, len(audio) - 1, target_length)
                    audio = np.interp(indices, np.arange(len(audio)), audio)
            
            # Pitch modification (simplified - in production use proper pitch shifting)
            if voice_profile.pitch_shift != 0.0:
                # Simple pitch shift approximation
                shift_factor = 2 ** (voice_profile.pitch_shift / 12.0)
                if shift_factor != 1.0:
                    target_length = int(len(audio) * shift_factor)
                    if target_length > 0:
                        indices = np.linspace(0, len(audio) - 1, target_length)
                        audio = np.interp(indices, np.arange(len(audio)), audio)
            
            return audio
            
        except Exception as e:
            logger.warning(f"Error applying voice modifications: {e}")
            return audio
    
    def _audio_to_bytes(self, audio: np.ndarray, output_format: str) -> bytes:
        """Convert audio array to bytes"""
        try:
            # Normalize audio to 16-bit range
            if audio.dtype != np.int16:
                # Ensure audio is in [-1, 1] range
                if audio.max() > 1.0 or audio.min() < -1.0:
                    audio = audio / max(abs(audio.max()), abs(audio.min()))
                
                # Convert to 16-bit integers
                audio = (audio * 32767).astype(np.int16)
            
            # Use BytesIO to create in-memory file
            buffer = io.BytesIO()
            
            # Write audio to buffer
            sf.write(buffer, audio, samplerate=22050, format='WAV')
            
            # Get bytes
            buffer.seek(0)
            audio_bytes = buffer.read()
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Error converting audio to bytes: {e}")
            return b""
    
    def synthesize_for_session(self, messages: List[Dict[str, str]], persona_name: str) -> Dict[str, bytes]:
        """
        Synthesize speech for multiple messages in a session
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            persona_name: Persona name for voice selection
        
        Returns:
            Dict mapping message index to audio bytes
        """
        results = {}
        
        for i, message in enumerate(messages):
            if message.get('role') == 'assistant':  # Only synthesize assistant messages
                content = message.get('content', '')
                if content:
                    audio_bytes = self.synthesize_speech(content, persona_name)
                    if audio_bytes:
                        results[str(i)] = audio_bytes
        
        return results
    
    def get_available_voices(self) -> List[Dict]:
        """Get list of available voice profiles"""
        return [profile.to_dict() for profile in self.VOICE_PROFILES.values()]
    
    def add_voice_profile(self, profile: TTSVoiceProfile):
        """Add custom voice profile"""
        self.VOICE_PROFILES[profile.name] = profile
        logger.info(f"Added voice profile: {profile.name}")
    
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
            **cache_stats
        }
    
    def clear_cache(self):
        """Clear TTS cache"""
        if self.cache:
            self.cache.clear()
    
    def preload_models(self, model_names: List[str] = None):
        """Preload TTS models for better performance"""
        if not TTS_AVAILABLE:
            logger.warning("Cannot preload models - TTS not available")
            return
        
        if model_names is None:
            model_names = list(set(profile.model_name for profile in self.VOICE_PROFILES.values()))
        
        logger.info(f"Preloading {len(model_names)} TTS models...")
        
        for model_name in model_names:
            self._get_or_load_model(model_name)
        
        logger.info("✅ TTS models preloaded")


# Global TTS service instance
_tts_service = None

def get_tts_service() -> EnhancedTTSService:
    """Get singleton TTS service instance"""
    global _tts_service
    if _tts_service is None:
        _tts_service = EnhancedTTSService()
    return _tts_service

def initialize_tts_service(cache_enabled: bool = True, gpu_enabled: bool = None, 
                          preload_models: bool = False) -> EnhancedTTSService:
    """Initialize TTS service with specific configuration"""
    global _tts_service
    _tts_service = EnhancedTTSService(cache_enabled, gpu_enabled)
    
    if preload_models:
        _tts_service.preload_models()
    
    return _tts_service