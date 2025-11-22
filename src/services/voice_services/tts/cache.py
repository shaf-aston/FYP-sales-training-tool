"""
TTS Caching System
"""

import time
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Optional

from src.config.paths import PROJECT_ROOT
from .core import TTSVoiceProfile

logger = logging.getLogger(__name__)


class TTSCache:
    """Caching system for TTS outputs"""
    
    def __init__(self, cache_dir: Path = None, max_cache_size_mb: int = 500):
        """Initialize TTS cache"""
        if cache_dir is None:
            cache_dir = PROJECT_ROOT / "model_cache" / "tts_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024
        
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading TTS cache metadata: {e}")
        
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
                
                # Update last accessed time
                if cache_key in self.metadata["entries"]:
                    self.metadata["entries"][cache_key]["last_accessed"] = time.time()
                    self._save_metadata()
                
                logger.debug(f"TTS cache hit for key: {cache_key[:8]}...")
                return audio_data
                
            except Exception as e:
                logger.error(f"Error reading TTS cache: {e}")
        
        return None
    
    def put(self, text: str, voice_profile: TTSVoiceProfile, audio_data: bytes):
        """Cache audio data"""
        cache_key = self._get_cache_key(text, voice_profile)
        cache_file = self.cache_dir / f"{cache_key}.wav"
        
        try:
            self._cleanup_if_needed(len(audio_data))
            
            with open(cache_file, 'wb') as f:
                f.write(audio_data)
            
            self.metadata["entries"][cache_key] = {
                "text": text[:100],
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
        current_time = time.time()
        ttl_seconds = 24 * 3600  # 24 hours

        # Remove expired entries first
        expired_keys = [
            key for key, entry in self.metadata["entries"].items()
            if (current_time - entry["last_accessed"]) > ttl_seconds
        ]
        
        for key in expired_keys:
            entry = self.metadata["entries"][key]
            cache_file = self.cache_dir / f"{key}.wav"
            if cache_file.exists():
                cache_file.unlink()
            self.metadata["total_size"] -= entry["file_size"]
            del self.metadata["entries"][key]

        # Clean up by size if needed
        if self.metadata["total_size"] + new_entry_size <= self.max_cache_size:
            return
        
        entries_by_age = sorted(
            self.metadata["entries"].items(),
            key=lambda x: x[1]["last_accessed"]
        )
        
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