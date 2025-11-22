"""
STT Caching System
"""

import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional

from src.config.paths import PROJECT_ROOT
from .core import STTResult

logger = logging.getLogger(__name__)


class STTCache:
    """Caching system for STT results"""
    
    def __init__(self, cache_dir: Path = None, max_cache_size_mb: int = 100):
        """Initialize STT cache"""
        if cache_dir is None:
            cache_dir = PROJECT_ROOT / "model_cache" / "stt_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024
        
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
                self.metadata["entries"][audio_hash]["last_accessed"] = time.time()
                self._save_metadata()
                
                entry = self.metadata["entries"][audio_hash]
                return STTResult(
                    text=entry["text"],
                    confidence=entry.get("confidence", 0.8),
                    language=entry.get("language", "en"),
                    duration=entry.get("duration", 0.0),
                    processing_time=0.0
                )
                
            except Exception as e:
                logger.error(f"Error reading STT cache: {e}")
        
        return None
    
    def put(self, audio_data: bytes, result: STTResult):
        """Cache STT result"""
        audio_hash = self._get_audio_hash(audio_data)
        
        try:
            entry_size = len(audio_hash) + len(result.text) + 200
            self._cleanup_if_needed(entry_size)
            
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
            
        except Exception as e:
            logger.error(f"Error caching STT result: {e}")
    
    def _cleanup_if_needed(self, new_entry_size: int):
        """Clean up cache if size limit would be exceeded"""
        current_time = time.time()
        ttl_seconds = 24 * 3600  # 24 hours

        # Remove expired entries
        expired_keys = [
            key for key, entry in self.metadata["entries"].items()
            if (current_time - entry["last_accessed"]) > ttl_seconds
        ]
        
        for key in expired_keys:
            entry = self.metadata["entries"][key]
            self.metadata["total_size"] -= entry["size"]
            del self.metadata["entries"][key]

        # Clean up by size if needed
        if self.metadata["total_size"] + new_entry_size <= self.max_cache_size:
            return
        
        entries_by_age = sorted(
            self.metadata["entries"].items(),
            key=lambda x: x[1]["last_accessed"]
        )
        
        removed_size = 0
        for audio_hash, entry in entries_by_age:
            removed_size += entry["size"]
            del self.metadata["entries"][audio_hash]
            
            if removed_size >= new_entry_size:
                break
        
        self.metadata["total_size"] -= removed_size
    
    def clear(self):
        """Clear entire cache"""
        try:
            self.metadata = {"entries": {}, "total_size": 0}
            self._save_metadata()
            logger.info("STT cache cleared")
        except Exception as e:
            logger.error(f"Error clearing STT cache: {e}")