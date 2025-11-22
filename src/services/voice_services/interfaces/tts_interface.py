"""
TTS (Text-to-Speech) Service Interface

Defines contracts and data structures specific to text-to-speech services.
Follows the Interface Segregation Principle by focusing only on TTS-related operations.
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum

from .audio_service import AudioService, ServiceResult, ServiceConfig, ServiceType, ProcessingStatus


class TTSBackend(Enum):
    """Available TTS backends"""
    COQUI = "coqui"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"
    PYTTSX3 = "pyttsx3"
    ELEVENLABS = "elevenlabs"


class OutputFormat(Enum):
    """Supported TTS output formats"""
    WAV = "wav"
    MP3 = "mp3" 
    OGG = "ogg"
    FLAC = "flac"
    AAC = "aac"


# Alias for backward compatibility
AudioFormat = OutputFormat


class VoiceEmotion(Enum):
    """Voice emotion/style options"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    ANGRY = "angry"
    PROFESSIONAL = "professional"


@dataclass
class VoiceProfile:
    """
    Voice profile configuration for persona-specific TTS
    
    Attributes:
        name: Profile name (e.g., "Mary", "Jake")
        model_name: TTS model to use
        speaker_id: Speaker ID for multi-speaker models
        language: Language code
        speed: Speaking speed multiplier (0.5-2.0)
        pitch_shift: Pitch adjustment in semitones
        emotion: Default emotion/style
    """
    name: str
    model_name: str
    speaker_id: Optional[str] = None
    language: str = "en"
    speed: float = 1.0
    pitch_shift: float = 0.0
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    
    def __post_init__(self):
        """Validate voice profile parameters"""
        if not 0.5 <= self.speed <= 2.0:
            raise ValueError("speed must be between 0.5 and 2.0")
        if not -12.0 <= self.pitch_shift <= 12.0:
            raise ValueError("pitch_shift must be between -12 and 12 semitones")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'name': self.name,
            'model_name': self.model_name,
            'speaker_id': self.speaker_id,
            'language': self.language,
            'speed': self.speed,
            'pitch_shift': self.pitch_shift,
            'emotion': self.emotion.value
        }


@dataclass
class TTSConfig(ServiceConfig):
    """
    Configuration specific to TTS services
    
    Attributes:
        backend: TTS backend to use
        voice_profile: Default voice profile name
        output_format: Default audio output format
        enable_chunking: Split long text into chunks
        max_chunk_length: Maximum characters per chunk
        enable_mos_evaluation: Calculate Mean Opinion Score metrics
        enable_ssml: Support SSML markup in input text
    """
    backend: TTSBackend = TTSBackend.COQUI
    voice_profile: str = "System"
    output_format: OutputFormat = OutputFormat.WAV
    enable_chunking: bool = True
    max_chunk_length: int = 500
    enable_mos_evaluation: bool = False
    enable_ssml: bool = False
    
    def validate(self) -> None:
        """Validate TTS-specific configuration"""
        super().validate()
        
        if self.max_chunk_length <= 0:
            raise ValueError("max_chunk_length must be positive")
        if not self.voice_profile:
            raise ValueError("voice_profile cannot be empty")


@dataclass
class TextChunk:
    """
    Text chunk for processing long inputs
    
    Attributes:
        text: Chunk text content
        index: Chunk index in sequence
        is_sentence_boundary: Whether chunk ends at sentence boundary
        processing_hints: Hints for TTS processing
    """
    text: str
    index: int
    is_sentence_boundary: bool = True
    processing_hints: Optional[Dict[str, Any]] = None


@dataclass
class QualityMetrics:
    """
    Audio quality metrics for TTS output
    
    Attributes:
        duration_seconds: Audio duration
        sample_rate: Audio sample rate
        rms_energy: RMS energy level
        peak_amplitude: Peak amplitude
        dynamic_range_db: Dynamic range in decibels
        zero_crossing_rate: Zero crossing rate
        spectral_centroid: Spectral centroid frequency
    """
    duration_seconds: float = 0.0
    sample_rate: int = 0
    rms_energy: float = 0.0
    peak_amplitude: float = 0.0
    dynamic_range_db: float = 0.0
    zero_crossing_rate: float = 0.0
    spectral_centroid: float = 0.0


@dataclass
class QualityIndicators:
    """
    User-facing quality indicators
    
    Attributes:
        audio_quality: Overall quality rating
        processing_efficiency: Processing speed rating
        format_support: Format compatibility rating
        issues: List of detected issues
        recommendations: Improvement recommendations
    """
    audio_quality: str = "good"  # "poor", "fair", "good", "excellent"
    processing_efficiency: str = "normal"  # "slow", "normal", "fast"
    format_support: str = "full"  # "limited", "partial", "full"
    issues: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.recommendations is None:
            self.recommendations = []


@dataclass
class TTSResult(ServiceResult):
    """
    Result from TTS processing
    
    Attributes:
        audio_data: Generated audio as bytes
        text: Original input text
        voice_profile: Voice profile used
        output_format: Audio format
        audio_duration: Duration in seconds
        file_size_bytes: Size of audio data
        backend_used: TTS backend that generated this result
        quality_metrics: Objective quality measurements
        quality_indicators: User-facing quality indicators
        chunks_processed: Number of text chunks processed
        mos_score: Mean Opinion Score if evaluated
    """
    audio_data: bytes = b""
    text: str = ""
    voice_profile: str = ""
    output_format: str = "wav"
    audio_duration: float = 0.0
    file_size_bytes: int = 0
    backend_used: Optional[str] = None
    quality_metrics: Optional[QualityMetrics] = None
    quality_indicators: Optional[QualityIndicators] = None
    chunks_processed: int = 1
    mos_score: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.audio_data and not self.file_size_bytes:
            self.file_size_bytes = len(self.audio_data)
    
    def calculate_duration(self, sample_rate: int = 22050) -> float:
        """
        Calculate audio duration from audio data
        
        Args:
            sample_rate: Sample rate for calculation
            
        Returns:
            Duration in seconds
        """
        try:
            import soundfile as sf
            import io
            
            with io.BytesIO(self.audio_data) as audio_buffer:
                info = sf.info(audio_buffer)
                self.audio_duration = info.duration
                return self.audio_duration
        except Exception:
            # Fallback estimation
            if self.file_size_bytes > 0:
                # Rough estimation: 2 bytes per sample, 1 channel
                estimated_samples = self.file_size_bytes // 2
                self.audio_duration = estimated_samples / sample_rate
                return self.audio_duration
            return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with all TTS-specific fields"""
        base_dict = super().to_dict()
        base_dict.update({
            'text': self.text[:100] + "..." if len(self.text) > 100 else self.text,
            'voice_profile': self.voice_profile,
            'output_format': self.output_format,
            'audio_duration': self.audio_duration,
            'file_size_bytes': self.file_size_bytes,
            'backend_used': self.backend_used,
            'chunks_processed': self.chunks_processed,
            'has_quality_metrics': self.quality_metrics is not None,
            'has_quality_indicators': self.quality_indicators is not None,
            'has_mos_score': self.mos_score is not None
        })
        return base_dict


class TTSService(AudioService):
    """
    Abstract interface for Text-to-Speech services
    
    Defines the contract that all TTS implementations must follow,
    ensuring consistent behavior across different backends.
    """
    
    def _get_service_type(self) -> ServiceType:
        """Return TTS service type"""
        return ServiceType.TTS
    
    @abstractmethod
    async def synthesize(self, text: str,
                        voice_profile: Optional[str] = None,
                        emotion: Optional[VoiceEmotion] = None,
                        output_format: Optional[OutputFormat] = None) -> TTSResult:
        """
        Synthesize speech from text
        
        Args:
            text: Text to synthesize
            voice_profile: Voice profile to use (overrides config)
            emotion: Emotion/style (overrides profile default)
            output_format: Output format (overrides config)
            
        Returns:
            TTS result with audio data and metadata
            
        Raises:
            TTSError: If synthesis fails
            TextValidationError: If text format is invalid
        """
        pass
    
    @abstractmethod
    def chunk_text(self, text: str, preserve_sentences: bool = True) -> List[TextChunk]:
        """
        Split long text into chunks for processing
        
        Args:
            text: Text to chunk
            preserve_sentences: Try to keep sentences intact
            
        Returns:
            List of text chunks ready for processing
        """
        pass
    
    @abstractmethod
    async def synthesize_chunks(self, chunks: List[TextChunk],
                               voice_profile: Optional[str] = None,
                               output_format: Optional[OutputFormat] = None) -> TTSResult:
        """
        Synthesize multiple text chunks and merge results
        
        Args:
            chunks: Text chunks to synthesize
            voice_profile: Voice profile to use
            output_format: Output format
            
        Returns:
            Combined TTS result
        """
        pass
    
    @abstractmethod
    def get_voice_profiles(self) -> List[VoiceProfile]:
        """
        Get available voice profiles
        
        Returns:
            List of available voice profiles
        """
        pass
    
    @abstractmethod
    def add_voice_profile(self, profile: VoiceProfile) -> None:
        """
        Add a new voice profile
        
        Args:
            profile: Voice profile to add
            
        Raises:
            VoiceProfileError: If profile is invalid or conflicts
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[OutputFormat]:
        """
        Get supported output formats
        
        Returns:
            List of supported output formats
        """
        pass
    
    @abstractmethod
    def convert_format(self, audio_data: bytes, 
                      from_format: OutputFormat,
                      to_format: OutputFormat) -> bytes:
        """
        Convert audio between formats
        
        Args:
            audio_data: Audio data to convert
            from_format: Source format
            to_format: Target format
            
        Returns:
            Converted audio data
            
        Raises:
            FormatConversionError: If conversion fails
        """
        pass
    
    @abstractmethod
    async def evaluate_mos_on_dataset(self, 
                                     test_dataset: List[tuple[str, str]]) -> Dict[str, Any]:
        """
        Evaluate Mean Opinion Score on a test dataset
        
        Args:
            test_dataset: List of (text, voice_profile) tuples
            
        Returns:
            MOS evaluation metrics
        """
        pass
    
    def validate_text(self, text: str) -> bool:
        """
        Validate input text for TTS processing
        
        Args:
            text: Text to validate
            
        Returns:
            True if text is valid
            
        Raises:
            ValueError: If text is invalid
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Check for extremely long text
        max_length = 10000  # Reasonable limit
        if len(text) > max_length:
            raise ValueError(f"Text too long ({len(text)} > {max_length} characters)")
        
        return True
    
    def clean_text(self, text: str) -> str:
        """
        Clean and prepare text for TTS synthesis
        
        Args:
            text: Raw text input
            
        Returns:
            Cleaned text ready for synthesis
        """
        text = text.strip()
        
        # Remove markdown formatting
        text = text.replace("**", "")
        text = text.replace("*", "")
        text = text.replace("_", "")
        text = text.replace("`", "")
        
        # Expand common abbreviations
        abbreviations = {
            " vs ": " versus ",
            " etc.": " etcetera",
            " i.e.": " that is",
            " e.g.": " for example",
            " Mr.": " Mister",
            " Mrs.": " Missis",
            " Ms.": " Miss",
            " Dr.": " Doctor"
        }
        
        for abbr, expansion in abbreviations.items():
            text = text.replace(abbr, expansion)
        
        return text
    
    def generate_quality_indicators(self, tts_result: TTSResult) -> QualityIndicators:
        """
        Generate user-facing quality indicators
        
        Args:
            tts_result: TTS result to analyze
            
        Returns:
            Quality indicators for user feedback
        """
        indicators = QualityIndicators()
        
        # Analyze processing time
        if tts_result.processing_time > 5.0:
            indicators.processing_efficiency = "slow"
            indicators.issues.append("long_processing_time")
        elif tts_result.processing_time < 0.5:
            indicators.processing_efficiency = "fast"
        
        # Analyze audio quality based on metrics
        if tts_result.quality_metrics:
            metrics = tts_result.quality_metrics
            if metrics.dynamic_range_db < 10:
                indicators.audio_quality = "poor"
                indicators.issues.append("low_dynamic_range")
            elif metrics.dynamic_range_db > 30:
                indicators.audio_quality = "excellent"
        
        # Check backend used
        if tts_result.backend_used == "pyttsx3":
            indicators.audio_quality = "basic"
            indicators.issues.append("fallback_engine_used")
        
        # Add recommendations based on issues
        if "long_processing_time" in indicators.issues:
            indicators.recommendations.append("Consider reducing text length")
        if "low_dynamic_range" in indicators.issues:
            indicators.recommendations.append("Audio quality may be affected by compression")
        
        return indicators
    
    async def process(self, input_data: str, **kwargs) -> TTSResult:
        """
        Process text input (implements AudioService.process)
        
        Args:
            input_data: Text to synthesize
            **kwargs: Additional parameters (voice_profile, emotion, output_format)
            
        Returns:
            TTS processing result
        """
        voice_profile = kwargs.get('voice_profile')
        emotion = kwargs.get('emotion')
        output_format = kwargs.get('output_format')
        
        return await self.synthesize(input_data, voice_profile, emotion, output_format)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get TTS service capabilities"""
        return {
            'service_type': self.service_type.value,
            'backend': self.config.backend.value,
            'voice_profiles': [profile.to_dict() for profile in self.get_voice_profiles()],
            'supported_formats': [fmt.value for fmt in self.get_supported_formats()],
            'features': {
                'chunking': self.config.enable_chunking,
                'mos_evaluation': self.config.enable_mos_evaluation,
                'ssml_support': self.config.enable_ssml,
                'format_conversion': True,
                'quality_indicators': True
            },
            'configuration': {
                'max_chunk_length': self.config.max_chunk_length,
                'default_voice_profile': self.config.voice_profile,
                'default_output_format': self.config.output_format.value
            }
        }