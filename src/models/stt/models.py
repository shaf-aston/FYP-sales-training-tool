"""
STT (Speech-to-Text) models and result classes
"""
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

class STTProvider(Enum):
    WHISPER = "whisper"
    FASTER_WHISPER = "faster_whisper"
    SPEECH_RECOGNITION = "speech_recognition"
    GOOGLE_CLOUD = "google_cloud"

@dataclass
class STTResult:
    """STT result with comprehensive metadata"""
    text: str
    confidence: float
    language: str = "unknown"
    duration: float = 0.0
    processing_time: float = 0.0
    word_timestamps: Optional[List[Dict]] = None
    segments: Optional[List[Dict]] = None
    provider: Optional[STTProvider] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, self.confidence))
    
    @property
    def words_per_minute(self) -> float:
        if self.duration > 0:
            return len(self.text.split()) / (self.duration / 60)
        return 0.0
    
    @property
    def is_high_quality(self) -> bool:
        return self.confidence > 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'confidence': self.confidence,
            'language': self.language,
            'duration': self.duration,
            'processing_time': self.processing_time,
            'word_timestamps': self.word_timestamps,
            'segments': self.segments,
            'provider': self.provider.value if self.provider else None,
            'metadata': self.metadata,
            'words_per_minute': self.words_per_minute,
            'is_high_quality': self.is_high_quality
        }

@dataclass
class STTConfig:
    """Configuration for STT services"""
    provider: STTProvider = STTProvider.WHISPER
    model_name: str = "base"
    language: Optional[str] = None
    enable_timestamps: bool = False
    enable_word_timestamps: bool = False
    chunk_duration: float = 30.0
    temperature: float = 0.0
    beam_size: int = 5
    patience: float = 1.0
    length_penalty: float = 1.0
    suppress_tokens: List[int] = field(default_factory=list)
    initial_prompt: Optional[str] = None
    condition_on_previous_text: bool = True
    fp16: bool = True
    compression_ratio_threshold: float = 2.4
    logprob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    vad_filter: bool = False
    vad_parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider.value,
            'model_name': self.model_name,
            'language': self.language,
            'enable_timestamps': self.enable_timestamps,
            'enable_word_timestamps': self.enable_word_timestamps,
            'chunk_duration': self.chunk_duration,
            'temperature': self.temperature,
            'beam_size': self.beam_size,
            'patience': self.patience,
            'length_penalty': self.length_penalty,
            'suppress_tokens': self.suppress_tokens,
            'initial_prompt': self.initial_prompt,
            'condition_on_previous_text': self.condition_on_previous_text,
            'fp16': self.fp16,
            'compression_ratio_threshold': self.compression_ratio_threshold,
            'logprob_threshold': self.logprob_threshold,
            'no_speech_threshold': self.no_speech_threshold,
            'vad_filter': self.vad_filter,
            'vad_parameters': self.vad_parameters
        }

class STTMetrics:
    """Performance metrics for STT operations"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.total_processing_time = 0.0
        self.total_audio_duration = 0.0
        self.confidence_scores = []
        self.error_count = 0
        self.provider_usage = {}
    
    def add_result(self, result: STTResult, audio_duration: float):
        self.total_requests += 1
        if result.text.strip():
            self.successful_requests += 1
            self.confidence_scores.append(result.confidence)
        else:
            self.error_count += 1
        
        self.total_processing_time += result.processing_time
        self.total_audio_duration += audio_duration
        
        provider = result.provider.value if result.provider else 'unknown'
        self.provider_usage[provider] = self.provider_usage.get(provider, 0) + 1
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_confidence(self) -> float:
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)
    
    @property
    def real_time_factor(self) -> float:
        """Processing time vs audio duration ratio"""
        if self.total_audio_duration == 0:
            return 0.0
        return self.total_processing_time / self.total_audio_duration
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'error_count': self.error_count,
            'success_rate': self.success_rate,
            'average_confidence': self.average_confidence,
            'total_processing_time': self.total_processing_time,
            'total_audio_duration': self.total_audio_duration,
            'real_time_factor': self.real_time_factor,
            'provider_usage': self.provider_usage
        }