"""
TTS Core Models and Results
"""

import time
import io
import logging
from typing import Dict, Optional

try:
    import soundfile as sf
    import numpy as np
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    sf = None
    np = None
    AUDIO_PROCESSING_AVAILABLE = False

logger = logging.getLogger(__name__)


class TTSResult:
    """TTS result with comprehensive metadata"""
    
    def __init__(self, audio_data: bytes, text: str, persona_name: str,
                 duration: float = 0.0, processing_time: float = 0.0,
                 output_format: str = "wav", file_size_bytes: int = 0,
                 mos_score: float = None, backend_used: str = None):
        """
        Initialize TTS result
        
        Args:
            audio_data: Generated audio bytes
            text: Original text
            persona_name: Persona used for generation
            duration: Audio duration in seconds
            processing_time: Generation time in seconds
            output_format: Audio format (wav, mp3, ogg)
            file_size_bytes: Audio file size
            mos_score: Mean Opinion Score if evaluated
            backend_used: TTS backend that generated this result
        """
        self.audio_data = audio_data
        self.text = text
        self.persona_name = persona_name
        self.duration = duration
        self.processing_time = processing_time
        self.output_format = output_format
        self.file_size_bytes = file_size_bytes or len(audio_data)
        self.mos_score = mos_score
        self.backend_used = backend_used
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "persona_name": self.persona_name,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "output_format": self.output_format,
            "file_size_bytes": self.file_size_bytes,
            "mos_score": self.mos_score,
            "backend_used": self.backend_used,
            "timestamp": self.timestamp
        }
    
    def calculate_duration(self, sample_rate: int = 22050) -> float:
        """Calculate audio duration from audio data"""
        if not AUDIO_PROCESSING_AVAILABLE or not self.audio_data:
            return 0.0
        
        try:
            with io.BytesIO(self.audio_data) as audio_buffer:
                info = sf.info(audio_buffer)
                self.duration = info.duration
                return self.duration
        except Exception as e:
            logger.error(f"Error calculating audio duration: {e}")
            return 0.0


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