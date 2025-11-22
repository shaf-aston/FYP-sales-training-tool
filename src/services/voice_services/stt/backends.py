"""
STT Backend Implementations
"""

import io
import os
import tempfile
import logging
from typing import Optional, Dict, Any

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    whisper = None
    WHISPER_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    sr = None
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    from google.cloud import speech
    GOOGLE_STT_AVAILABLE = True
except ImportError:
    speech = None
    GOOGLE_STT_AVAILABLE = False

from .core import STTResult

logger = logging.getLogger(__name__)


class WhisperBackend:
    """OpenAI Whisper backend"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model = None
    
    def load_model(self):
        """Load Whisper model"""
        if not WHISPER_AVAILABLE:
            raise ImportError("OpenAI Whisper not available")
        
        try:
            self.model = whisper.load_model(self.model_size, device=self.device)
            logger.info(f"✅ Loaded Whisper model: {self.model_size}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe(self, audio_data: bytes, language: str = None) -> Optional[STTResult]:
        """Transcribe audio using Whisper"""
        if not self.model:
            self.load_model()
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
            
            try:
                result = self.model.transcribe(tmp_file.name, language=language)
                
                return STTResult(
                    text=result["text"].strip(),
                    confidence=0.8,  # Whisper doesn't provide confidence
                    language=result.get("language", language or "en"),
                    backend_used="whisper"
                )
                
            finally:
                os.unlink(tmp_file.name)
                
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return None


class FasterWhisperBackend:
    """Faster Whisper backend"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model = None
    
    def load_model(self):
        """Load Faster Whisper model"""
        if not FASTER_WHISPER_AVAILABLE:
            raise ImportError("Faster Whisper not available")
        
        try:
            self.model = WhisperModel(self.model_size, device=self.device)
            logger.info(f"✅ Loaded Faster Whisper model: {self.model_size}")
        except Exception as e:
            logger.error(f"Failed to load Faster Whisper model: {e}")
            raise
    
    def transcribe(self, audio_data: bytes, language: str = None) -> Optional[STTResult]:
        """Transcribe audio using Faster Whisper"""
        if not self.model:
            self.load_model()
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
            
            try:
                segments, info = self.model.transcribe(tmp_file.name, language=language)
                
                text = ""
                total_confidence = 0.0
                segment_count = 0
                
                for segment in segments:
                    text += segment.text + " "
                    total_confidence += getattr(segment, 'avg_logprob', -1.0)
                    segment_count += 1
                
                confidence = max(0.0, min(1.0, (total_confidence / segment_count + 1.0) / 2.0)) if segment_count > 0 else 0.8
                
                return STTResult(
                    text=text.strip(),
                    confidence=confidence,
                    language=info.language,
                    backend_used="faster_whisper"
                )
                
            finally:
                os.unlink(tmp_file.name)
                
        except Exception as e:
            logger.error(f"Faster Whisper transcription failed: {e}")
            return None


class SpeechRecognitionBackend:
    """SpeechRecognition backend"""
    
    def __init__(self):
        if not SPEECH_RECOGNITION_AVAILABLE:
            raise ImportError("SpeechRecognition not available")
        
        self.recognizer = sr.Recognizer()
    
    def transcribe(self, audio_data: bytes, language: str = "en") -> Optional[STTResult]:
        """Transcribe audio using SpeechRecognition"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
            
            try:
                with sr.AudioFile(tmp_file.name) as source:
                    audio = self.recognizer.record(source)
                
                # Try Google first, then other services
                text = None
                confidence = 0.8
                
                try:
                    text = self.recognizer.recognize_google(audio, language=language)
                except (sr.UnknownValueError, sr.RequestError):
                    try:
                        text = self.recognizer.recognize_sphinx(audio)
                    except (sr.UnknownValueError, sr.RequestError):
                        pass
                
                if text:
                    return STTResult(
                        text=text,
                        confidence=confidence,
                        language=language,
                        backend_used="speech_recognition"
                    )
                
                return None
                
            finally:
                os.unlink(tmp_file.name)
                
        except Exception as e:
            logger.error(f"SpeechRecognition transcription failed: {e}")
            return None


class GoogleCloudSTTBackend:
    """Google Cloud STT backend"""
    
    def __init__(self):
        if not GOOGLE_STT_AVAILABLE:
            raise ImportError("Google Cloud STT not available")
        
        self.client = speech.SpeechClient()
    
    def transcribe(self, audio_data: bytes, language: str = "en-US", 
                  sample_rate: int = 16000) -> Optional[STTResult]:
        """Transcribe audio using Google Cloud STT"""
        try:
            audio = speech.RecognitionAudio(content=audio_data)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code=language,
            )
            
            response = self.client.recognize(config=config, audio=audio)
            
            if response.results:
                result = response.results[0].alternatives[0]
                return STTResult(
                    text=result.transcript,
                    confidence=result.confidence,
                    language=language,
                    backend_used="google_cloud"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Google Cloud STT transcription failed: {e}")
            return None