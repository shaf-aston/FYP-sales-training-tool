"""
TTS (Text-to-Speech) models and result classes
"""
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

class TTSProvider(Enum):
    COQUI = "coqui"
    PYTTSX3 = "pyttsx3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"

class VoiceEmotion(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"

@dataclass
class VoiceProfile:
    """Voice profile configuration"""
    name: str
    provider: TTSProvider
    voice_id: Optional[str] = None
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    gender: Optional[str] = None
    age_range: Optional[str] = None
    accent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'provider': self.provider.value,
            'voice_id': self.voice_id,
            'language': self.language,
            'speed': self.speed,
            'pitch': self.pitch,
            'volume': self.volume,
            'emotion': self.emotion.value,
            'gender': self.gender,
            'age_range': self.age_range,
            'accent': self.accent,
            'metadata': self.metadata
        }

@dataclass
class TTSResult:
    """TTS result with comprehensive metadata"""
    audio_data: bytes
    text: str
    voice_profile: Optional[VoiceProfile] = None
    duration: float = 0.0
    processing_time: float = 0.0
    sample_rate: int = 22050
    format: str = "wav"
    file_size: int = 0
    provider: Optional[TTSProvider] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.file_size:
            self.file_size = len(self.audio_data)
    
    @property
    def chars_per_second(self) -> float:
        if self.duration > 0:
            return len(self.text) / self.duration
        return 0.0
    
    @property
    def compression_ratio(self) -> float:
        if len(self.text) > 0:
            return self.file_size / len(self.text.encode('utf-8'))
        return 0.0
    
    @property
    def is_high_quality(self) -> bool:
        return (self.duration > 0 and 
                self.chars_per_second > 5 and 
                self.compression_ratio < 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'voice_profile': self.voice_profile.name if self.voice_profile else None,
            'duration': self.duration,
            'processing_time': self.processing_time,
            'sample_rate': self.sample_rate,
            'format': self.format,
            'file_size': self.file_size,
            'provider': self.provider.value if self.provider else None,
            'metadata': self.metadata,
            'chars_per_second': self.chars_per_second,
            'compression_ratio': self.compression_ratio,
            'is_high_quality': self.is_high_quality
        }

@dataclass
class TTSConfig:
    """Configuration for TTS services"""
    provider: TTSProvider = TTSProvider.COQUI
    model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    voice_profile: Optional[VoiceProfile] = None
    sample_rate: int = 22050
    format: str = "wav"
    chunk_size: int = 1000
    enable_streaming: bool = False
    quality: str = "medium"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 0.8
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    language: str = "en"
    use_gpu: bool = False
    cache_enabled: bool = True
    normalize_text: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider.value,
            'model_name': self.model_name,
            'voice_profile': self.voice_profile.to_dict() if self.voice_profile else None,
            'sample_rate': self.sample_rate,
            'format': self.format,
            'chunk_size': self.chunk_size,
            'enable_streaming': self.enable_streaming,
            'quality': self.quality,
            'speed': self.speed,
            'pitch': self.pitch,
            'volume': self.volume,
            'emotion': self.emotion.value,
            'language': self.language,
            'use_gpu': self.use_gpu,
            'cache_enabled': self.cache_enabled,
            'normalize_text': self.normalize_text
        }

class TTSMetrics:
    """Performance metrics for TTS operations"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.total_processing_time = 0.0
        self.total_text_length = 0
        self.total_audio_duration = 0.0
        self.total_file_size = 0
        self.error_count = 0
        self.provider_usage = {}
        self.voice_profile_usage = {}
    
    def add_result(self, result: TTSResult, text_length: int):
        self.total_requests += 1
        if result.audio_data:
            self.successful_requests += 1
            self.total_audio_duration += result.duration
            self.total_file_size += result.file_size
        else:
            self.error_count += 1
        
        self.total_processing_time += result.processing_time
        self.total_text_length += text_length
        
        provider = result.provider.value if result.provider else 'unknown'
        self.provider_usage[provider] = self.provider_usage.get(provider, 0) + 1
        
        voice_name = result.voice_profile.name if result.voice_profile else 'default'
        self.voice_profile_usage[voice_name] = self.voice_profile_usage.get(voice_name, 0) + 1
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_processing_time(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_processing_time / self.total_requests
    
    @property
    def real_time_factor(self) -> float:
        """Processing time vs audio duration ratio"""
        if self.total_audio_duration == 0:
            return 0.0
        return self.total_processing_time / self.total_audio_duration
    
    @property
    def average_chars_per_second(self) -> float:
        if self.total_audio_duration == 0:
            return 0.0
        return self.total_text_length / self.total_audio_duration
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'error_count': self.error_count,
            'success_rate': self.success_rate,
            'average_processing_time': self.average_processing_time,
            'total_text_length': self.total_text_length,
            'total_audio_duration': self.total_audio_duration,
            'total_file_size': self.total_file_size,
            'real_time_factor': self.real_time_factor,
            'average_chars_per_second': self.average_chars_per_second,
            'provider_usage': self.provider_usage,
            'voice_profile_usage': self.voice_profile_usage
        }