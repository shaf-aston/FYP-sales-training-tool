"""
Simplified STT Service
Core speech-to-text functionality without redundancy
"""
import logging
import tempfile
import time
from typing import Optional, List, Dict, Any

from src.utils.audio import (
    AudioProcessor, WHISPER_AVAILABLE, FASTER_WHISPER_AVAILABLE, 
    SPEECH_RECOGNITION_AVAILABLE, whisper, WhisperModel, sr
)
from src.models.stt.models import STTResult, STTConfig, STTProvider, STTMetrics

logger = logging.getLogger(__name__)

class STTService:
    """Unified Speech-to-Text service"""
    
    def __init__(self, config: STTConfig):
        self.config = config
        self.metrics = STTMetrics()
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the appropriate STT model based on config"""
        try:
            if self.config.provider == STTProvider.FASTER_WHISPER and FASTER_WHISPER_AVAILABLE:
                self.model = WhisperModel(
                    self.config.model_name,
                    device="auto",
                    compute_type="float16" if self.config.fp16 else "float32"
                )
                logger.info(f"Initialized Faster Whisper model: {self.config.model_name}")
            
            elif self.config.provider == STTProvider.WHISPER and WHISPER_AVAILABLE:
                self.model = whisper.load_model(self.config.model_name)
                logger.info(f"Initialized Whisper model: {self.config.model_name}")
            
            elif self.config.provider == STTProvider.SPEECH_RECOGNITION and SPEECH_RECOGNITION_AVAILABLE:
                self.model = sr.Recognizer()
                logger.info("Initialized SpeechRecognition")
            
            else:
                logger.error(f"No available STT provider for: {self.config.provider}")
                raise RuntimeError(f"STT provider {self.config.provider} not available")
        
        except Exception as e:
            logger.error(f"Failed to initialize STT model: {e}")
            raise
    
    def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> STTResult:
        """Transcribe audio to text"""
        start_time = time.time()
        
        if not AudioProcessor.validate_audio(audio_data):
            raise ValueError("Invalid audio data")
        
        audio_info = AudioProcessor.get_audio_info(audio_data) or {}
        audio_duration = audio_info.get('duration', 0.0)
        
        try:
            if self.config.provider == STTProvider.FASTER_WHISPER:
                result = self._transcribe_faster_whisper(audio_data, language)
            elif self.config.provider == STTProvider.WHISPER:
                result = self._transcribe_whisper(audio_data, language)
            elif self.config.provider == STTProvider.SPEECH_RECOGNITION:
                result = self._transcribe_speech_recognition(audio_data)
            else:
                raise RuntimeError(f"Unsupported provider: {self.config.provider}")
            
            result.duration = audio_duration
            result.processing_time = time.time() - start_time
            result.provider = self.config.provider
            
            self.metrics.add_result(result, audio_duration)
            return result
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            error_result = STTResult(
                text="",
                confidence=0.0,
                language=language or "unknown",
                duration=audio_duration,
                processing_time=time.time() - start_time,
                provider=self.config.provider,
                metadata={"error": str(e)}
            )
            self.metrics.add_result(error_result, audio_duration)
            raise
    
    def _transcribe_faster_whisper(self, audio_data: bytes, language: Optional[str]) -> STTResult:
        """Transcribe using Faster Whisper"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
            tmp.write(audio_data)
            tmp.flush()
            
            segments, info = self.model.transcribe(
                tmp.name,
                language=language or self.config.language,
                beam_size=self.config.beam_size,
                temperature=self.config.temperature,
                condition_on_previous_text=self.config.condition_on_previous_text,
                vad_filter=self.config.vad_filter,
                word_timestamps=self.config.enable_word_timestamps
            )
            
            text_segments = list(segments)
            full_text = " ".join([segment.text for segment in text_segments])
            
            # Calculate average confidence
            confidences = [getattr(segment, 'avg_logprob', 0.0) for segment in text_segments]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            confidence = max(0.0, min(1.0, (avg_confidence + 5) / 5))  # Normalize to 0-1
            
            segments_data = []
            word_timestamps = []
            
            for segment in text_segments:
                segment_data = {
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text
                }
                segments_data.append(segment_data)
                
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        word_timestamps.append({
                            'word': word.word,
                            'start': word.start,
                            'end': word.end,
                            'probability': getattr(word, 'probability', 1.0)
                        })
            
            return STTResult(
                text=full_text.strip(),
                confidence=confidence,
                language=info.language,
                word_timestamps=word_timestamps if self.config.enable_word_timestamps else None,
                segments=segments_data if self.config.enable_timestamps else None,
                metadata={
                    'language_probability': info.language_probability,
                    'model_name': self.config.model_name
                }
            )
    
    def _transcribe_whisper(self, audio_data: bytes, language: Optional[str]) -> STTResult:
        """Transcribe using OpenAI Whisper"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
            tmp.write(audio_data)
            tmp.flush()
            
            result = self.model.transcribe(
                tmp.name,
                language=language or self.config.language,
                temperature=self.config.temperature,
                word_timestamps=self.config.enable_word_timestamps
            )
            
            confidence = 0.9  # Whisper doesn't provide confidence scores
            
            word_timestamps = None
            if self.config.enable_word_timestamps and 'segments' in result:
                word_timestamps = []
                for segment in result['segments']:
                    if 'words' in segment:
                        word_timestamps.extend(segment['words'])
            
            segments_data = None
            if self.config.enable_timestamps and 'segments' in result:
                segments_data = result['segments']
            
            return STTResult(
                text=result['text'].strip(),
                confidence=confidence,
                language=result.get('language', 'unknown'),
                word_timestamps=word_timestamps,
                segments=segments_data,
                metadata={'model_name': self.config.model_name}
            )
    
    def _transcribe_speech_recognition(self, audio_data: bytes) -> STTResult:
        """Transcribe using SpeechRecognition library"""
        with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
            tmp.write(audio_data)
            tmp.flush()
            
            with sr.AudioFile(tmp.name) as source:
                audio = self.model.record(source)
            
            try:
                text = self.model.recognize_google(audio)
                confidence = 0.8  # Estimated confidence
            except sr.UnknownValueError:
                text = ""
                confidence = 0.0
            except sr.RequestError as e:
                raise RuntimeError(f"Speech recognition service error: {e}")
            
            return STTResult(
                text=text,
                confidence=confidence,
                language="en",
                metadata={'provider': 'google'}
            )
    
    def batch_transcribe(self, audio_files: List[bytes], language: Optional[str] = None) -> List[STTResult]:
        """Transcribe multiple audio files"""
        results = []
        for audio_data in audio_files:
            try:
                result = self.transcribe(audio_data, language)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch transcription failed for one file: {e}")
                error_result = STTResult(
                    text="",
                    confidence=0.0,
                    language=language or "unknown",
                    metadata={"error": str(e)}
                )
                results.append(error_result)
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service performance metrics"""
        return self.metrics.get_summary()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.metrics = STTMetrics()

# Factory function for backwards compatibility
def create_stt_service(model_name: str = "base", 
                      provider: str = "faster_whisper",
                      **kwargs) -> STTService:
    """Create STT service with simplified configuration"""
    config = STTConfig(
        provider=STTProvider(provider),
        model_name=model_name,
        **kwargs
    )
    return STTService(config)