"""
STT (Speech-to-Text) Service Interface

Defines contracts and data structures specific to speech recognition services.
Follows the Interface Segregation Principle by focusing only on STT-related operations.
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
import io

from .audio_service import AudioService, ServiceResult, ServiceConfig, ServiceType, ProcessingStatus


class STTBackend(Enum):
    """Available STT backends"""
    WHISPER = "whisper"
    FASTER_WHISPER = "faster_whisper"
    GOOGLE_CLOUD = "google_cloud"
    SPEECH_RECOGNITION = "speech_recognition"
    AZURE = "azure"


class ConfidenceLevel(Enum):
    """Confidence level classifications for STT results"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LanguageCode(Enum):
    """Supported language codes"""
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    IT = "it"
    PT = "pt"
    RU = "ru"
    ZH = "zh"
    JA = "ja"
    KO = "ko"


class AudioFormat(Enum):
    """Supported audio formats"""
    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    FLAC = "flac"
    M4A = "m4a"


@dataclass
class STTConfig(ServiceConfig):
    """
    Configuration specific to STT services
    
    Attributes:
        backend: STT backend to use
        language: Language code for recognition
        sample_rate: Expected audio sample rate
        enable_preprocessing: Apply audio preprocessing
        confidence_threshold: Minimum confidence score to accept
        enable_wer_evaluation: Calculate Word Error Rate if ground truth available
        streaming_enabled: Enable streaming recognition for long audio
        chunk_duration: Duration of audio chunks for streaming (seconds)
    """
    backend: STTBackend = STTBackend.WHISPER
    language: str = "en"
    sample_rate: int = 16000
    enable_preprocessing: bool = True
    confidence_threshold: float = 0.7
    enable_wer_evaluation: bool = False
    streaming_enabled: bool = False
    chunk_duration: float = 5.0
    
    def validate(self) -> None:
        """Validate STT-specific configuration"""
        super().validate()
        
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if self.chunk_duration <= 0:
            raise ValueError("chunk_duration must be positive")


@dataclass 
class AudioValidation:
    """
    Audio validation results
    
    Attributes:
        is_valid: Whether audio is valid for processing
        format_detected: Detected audio format
        duration_seconds: Audio duration
        sample_rate: Detected sample rate
        issues: List of validation issues found
        recommendations: Suggested fixes for issues
    """
    is_valid: bool
    format_detected: Optional[AudioFormat] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    issues: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.recommendations is None:
            self.recommendations = []


@dataclass
class ConfidenceFeedback:
    """
    User-facing confidence feedback
    
    Attributes:
        confidence_level: High/Medium/Low confidence classification
        confidence_score: Numerical confidence (0-1)
        user_message: Message to show to user
        suggested_actions: Recommended user actions
        needs_clarification: Whether user should be asked to repeat
    """
    confidence_level: str  # "high", "medium", "low"
    confidence_score: float
    user_message: str
    suggested_actions: List[str]
    needs_clarification: bool = False


@dataclass
class STTResult(ServiceResult):
    """
    Result from STT processing
    
    Attributes:
        text: Transcribed text
        confidence: Confidence score (0-1)
        language: Detected/used language
        audio_duration: Duration of processed audio
        backend_used: STT backend that generated this result
        wer_score: Word Error Rate if evaluated
        confidence_feedback: User-facing feedback based on confidence
        audio_validation: Validation results for input audio
        segments: Time-aligned segments for longer audio
    """
    text: str = ""
    confidence: float = 0.0
    language: str = "en"
    audio_duration: float = 0.0
    backend_used: Optional[str] = None
    wer_score: Optional[float] = None
    confidence_feedback: Optional[ConfidenceFeedback] = None
    audio_validation: Optional[AudioValidation] = None
    segments: Optional[List[Dict[str, Any]]] = None
    
    def calculate_wer(self, ground_truth: str) -> Optional[float]:
        """
        Calculate Word Error Rate against ground truth
        
        Args:
            ground_truth: Reference text
            
        Returns:
            WER score or None if calculation fails
        """
        try:
            # Import jiwer only when needed
            import jiwer
            wer = jiwer.wer(ground_truth, self.text)
            self.wer_score = wer
            return wer
        except ImportError:
            return None
        except Exception:
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with all STT-specific fields"""
        base_dict = super().to_dict()
        base_dict.update({
            'text': self.text,
            'confidence': self.confidence,
            'language': self.language,
            'audio_duration': self.audio_duration,
            'backend_used': self.backend_used,
            'wer_score': self.wer_score,
            'has_confidence_feedback': self.confidence_feedback is not None,
            'has_audio_validation': self.audio_validation is not None,
            'segment_count': len(self.segments) if self.segments else 0
        })
        return base_dict


class STTService(AudioService):
    """
    Abstract interface for Speech-to-Text services
    
    Defines the contract that all STT implementations must follow,
    ensuring consistent behavior across different backends.
    """
    
    def _get_service_type(self) -> ServiceType:
        """Return STT service type"""
        return ServiceType.STT
    
    @abstractmethod
    async def transcribe(self, audio_data: bytes, 
                        language: Optional[str] = None,
                        ground_truth: Optional[str] = None) -> STTResult:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio data as bytes
            language: Language code (overrides config if provided)
            ground_truth: Ground truth text for WER evaluation
            
        Returns:
            STT result with transcription and metadata
            
        Raises:
            STTError: If transcription fails
            AudioValidationError: If audio format is invalid
        """
        pass
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: io.BytesIO,
                               chunk_duration: Optional[float] = None) -> List[STTResult]:
        """
        Transcribe streaming audio in chunks
        
        Args:
            audio_stream: Stream of audio data
            chunk_duration: Duration of each chunk (overrides config)
            
        Returns:
            List of STT results for each chunk
        """
        pass
    
    @abstractmethod
    def validate_audio(self, audio_data: bytes) -> AudioValidation:
        """
        Validate audio data for STT processing
        
        Args:
            audio_data: Audio data to validate
            
        Returns:
            Validation result with details
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes
        
        Returns:
            List of supported language codes
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[AudioFormat]:
        """
        Get list of supported audio formats
        
        Returns:
            List of supported audio formats
        """
        pass
    
    @abstractmethod
    async def evaluate_wer_on_dataset(self, 
                                     test_dataset: List[tuple[bytes, str]]) -> Dict[str, Any]:
        """
        Evaluate Word Error Rate on a test dataset
        
        Args:
            test_dataset: List of (audio_data, ground_truth) tuples
            
        Returns:
            Evaluation metrics including average WER, backend usage stats
        """
        pass
    
    def generate_confidence_feedback(self, confidence: float) -> ConfidenceFeedback:
        """
        Generate user-facing confidence feedback
        
        Args:
            confidence: Confidence score (0-1)
            
        Returns:
            Confidence feedback for user interface
        """
        threshold = self.config.confidence_threshold
        
        if confidence >= 0.8:
            level = "high"
            message = "I understood that clearly."
            actions = []
            needs_clarification = False
        elif confidence >= threshold:
            level = "medium"
            message = "I think I understood that, but please let me know if I got it wrong."
            actions = ["confirm_understanding"]
            needs_clarification = False
        else:
            level = "low"
            message = "I had some difficulty understanding that. Could you please repeat or rephrase?"
            actions = ["try_again", "speak_more_clearly", "reduce_background_noise"]
            needs_clarification = True
        
        return ConfidenceFeedback(
            confidence_level=level,
            confidence_score=confidence,
            user_message=message,
            suggested_actions=actions,
            needs_clarification=needs_clarification
        )
    
    def preprocess_audio(self, audio_data: bytes) -> bytes:
        """
        Apply audio preprocessing if enabled
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            Preprocessed audio data
        """
        if not self.config.enable_preprocessing:
            return audio_data
        
        # Default implementation - subclasses can override
        return audio_data
    
    async def process(self, input_data: Union[bytes, str], **kwargs) -> STTResult:
        """
        Process audio input (implements AudioService.process)
        
        Args:
            input_data: Audio data as bytes or file path as string
            **kwargs: Additional parameters (language, ground_truth)
            
        Returns:
            STT processing result
        """
        # Handle file path input
        if isinstance(input_data, str):
            with open(input_data, 'rb') as f:
                audio_data = f.read()
        else:
            audio_data = input_data
        
        # Extract parameters
        language = kwargs.get('language')
        ground_truth = kwargs.get('ground_truth')
        
        # Perform transcription
        return await self.transcribe(audio_data, language, ground_truth)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get STT service capabilities"""
        return {
            'service_type': self.service_type.value,
            'backend': self.config.backend.value,
            'supported_languages': self.get_supported_languages(),
            'supported_formats': [fmt.value for fmt in self.get_supported_formats()],
            'features': {
                'streaming': self.config.streaming_enabled,
                'preprocessing': self.config.enable_preprocessing,
                'wer_evaluation': self.config.enable_wer_evaluation,
                'confidence_feedback': True
            },
            'configuration': {
                'sample_rate': self.config.sample_rate,
                'confidence_threshold': self.config.confidence_threshold,
                'chunk_duration': self.config.chunk_duration
            }
        }