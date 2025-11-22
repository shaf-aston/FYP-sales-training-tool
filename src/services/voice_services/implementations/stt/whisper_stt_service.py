import os
import io
import time
import logging
import hashlib
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import numpy as np
import soundfile as sf
from threading import RLock

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    try:
        import whisper
        FASTER_WHISPER_AVAILABLE = False
        WHISPER_AVAILABLE = True
    except ImportError:
        FASTER_WHISPER_AVAILABLE = False
        WHISPER_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from ...interfaces import STTService, STTConfig, STTResult, LanguageCode, ConfidenceLevel

logger = logging.getLogger(__name__)


class WhisperSTTService(STTService):
    
    def __init__(self, config: STTConfig):
        super().__init__(config)
        self.model = None
        self.model_size = config.model_config.get("model_size", "base")
        self.device = "cuda" if config.model_config.get("gpu_enabled", False) else "cpu"
        self.language = config.language.value if config.language else "en"
        self._lock = RLock()
        self._load_model()
        
    def _load_model(self):
        with self._lock:
            if self.model is None:
                try:
                    if FASTER_WHISPER_AVAILABLE:
                        self.model = WhisperModel(self.model_size, device=self.device, compute_type="int8")
                        logger.info(f"Loaded Faster Whisper model: {self.model_size}")
                    elif WHISPER_AVAILABLE:
                        self.model = whisper.load_model(self.model_size)
                        logger.info(f"Loaded OpenAI Whisper model: {self.model_size}")
                except Exception as e:
                    logger.error(f"Failed to load Whisper model: {e}")
                    raise
    
    def transcribe(self, audio_data: bytes, language: LanguageCode = None) -> STTResult:
        if not audio_data:
            raise ValueError("Audio data is empty")
        
        start_time = time.time()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_data)
            tmp_path = tmp_file.name
        
        try:
            if FASTER_WHISPER_AVAILABLE:
                segments, info = self.model.transcribe(
                    tmp_path, 
                    beam_size=5,
                    language=language.value if language else self.language
                )
                text = " ".join([segment.text for segment in segments])
                detected_language = LanguageCode(info.language)
                confidence = self._calculate_confidence_faster_whisper(segments)
            else:
                result = self.model.transcribe(
                    tmp_path,
                    language=language.value if language else self.language
                )
                text = result["text"].strip()
                detected_language = LanguageCode(result.get("language", self.language))
                confidence = self._calculate_confidence_openai_whisper(result)
            
            processing_time = time.time() - start_time
            
            return STTResult(
                text=text,
                confidence=confidence,
                language=detected_language,
                processing_time=processing_time,
                metadata={
                    "model_size": self.model_size,
                    "device": self.device,
                    "backend": "faster_whisper" if FASTER_WHISPER_AVAILABLE else "openai_whisper"
                }
            )
            
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def transcribe_stream(self, audio_stream: Any, chunk_size: int = 1024) -> List[STTResult]:
        results = []
        buffer = b""
        
        for chunk in audio_stream:
            buffer += chunk
            if len(buffer) >= chunk_size:
                try:
                    result = self.transcribe(buffer)
                    results.append(result)
                    buffer = b""
                except Exception as e:
                    logger.warning(f"Stream transcription chunk failed: {e}")
        
        if buffer:
            try:
                result = self.transcribe(buffer)
                results.append(result)
            except Exception as e:
                logger.warning(f"Final stream chunk failed: {e}")
        
        return results
    
    def validate_audio(self, audio_data: bytes) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name
            
            try:
                info = sf.info(tmp_path)
                return (
                    info.duration >= 0.1 and 
                    info.duration <= 300 and
                    info.samplerate >= 8000
                )
            finally:
                os.unlink(tmp_path)
                
        except Exception:
            return False
    
    def get_supported_languages(self) -> List[LanguageCode]:
        return [
            LanguageCode.EN, LanguageCode.ES, LanguageCode.FR, 
            LanguageCode.DE, LanguageCode.IT, LanguageCode.PT,
            LanguageCode.RU, LanguageCode.JA, LanguageCode.KO,
            LanguageCode.ZH, LanguageCode.AR
        ]
    
    def _calculate_confidence_faster_whisper(self, segments) -> ConfidenceLevel:
        if not segments:
            return ConfidenceLevel.LOW
        
        total_logprob = 0
        count = 0
        
        for segment in segments:
            if hasattr(segment, 'avg_logprob'):
                total_logprob += segment.avg_logprob
                count += 1
        
        if count == 0:
            return ConfidenceLevel.MEDIUM
        
        avg_logprob = total_logprob / count
        confidence_score = min(1.0, max(0.0, avg_logprob + 1.0))
        
        if confidence_score >= 0.8:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.6:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def _calculate_confidence_openai_whisper(self, result) -> ConfidenceLevel:
        segments = result.get("segments", [])
        if not segments:
            return ConfidenceLevel.MEDIUM
        
        total_logprob = 0
        count = 0
        
        for segment in segments:
            if "avg_logprob" in segment:
                total_logprob += segment["avg_logprob"]
                count += 1
        
        if count == 0:
            return ConfidenceLevel.MEDIUM
        
        avg_logprob = total_logprob / count
        confidence_score = min(1.0, max(0.0, avg_logprob + 1.0))
        
        if confidence_score >= 0.8:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.6:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW


class SpeechRecognitionSTTService(STTService):
    
    def __init__(self, config: STTConfig):
        super().__init__(config)
        if not SPEECH_RECOGNITION_AVAILABLE:
            raise ImportError("speech_recognition library not available")
        
        self.recognizer = sr.Recognizer()
        self.engine = config.model_config.get("engine", "google")
        
    def transcribe(self, audio_data: bytes, language: LanguageCode = None) -> STTResult:
        if not audio_data:
            raise ValueError("Audio data is empty")
        
        start_time = time.time()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_data)
            tmp_path = tmp_file.name
        
        try:
            with sr.AudioFile(tmp_path) as source:
                audio = self.recognizer.record(source)
            
            lang_code = language.value if language else "en-US"
            
            try:
                if self.engine == "google":
                    text = self.recognizer.recognize_google(audio, language=lang_code)
                    confidence = ConfidenceLevel.HIGH
                elif self.engine == "sphinx":
                    text = self.recognizer.recognize_sphinx(audio)
                    confidence = ConfidenceLevel.MEDIUM
                else:
                    text = self.recognizer.recognize_google(audio, language=lang_code)
                    confidence = ConfidenceLevel.HIGH
                
                processing_time = time.time() - start_time
                
                return STTResult(
                    text=text,
                    confidence=confidence,
                    language=language or LanguageCode.EN,
                    processing_time=processing_time,
                    metadata={"engine": self.engine}
                )
                
            except sr.UnknownValueError:
                return STTResult(
                    text="",
                    confidence=ConfidenceLevel.LOW,
                    language=language or LanguageCode.EN,
                    processing_time=time.time() - start_time,
                    metadata={"error": "Could not understand audio"}
                )
                
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def transcribe_stream(self, audio_stream: Any, chunk_size: int = 1024) -> List[STTResult]:
        results = []
        
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
        
        for chunk in audio_stream:
            try:
                result = self.transcribe(chunk)
                if result.text:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Stream chunk transcription failed: {e}")
        
        return results
    
    def validate_audio(self, audio_data: bytes) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name
            
            try:
                with sr.AudioFile(tmp_path) as source:
                    self.recognizer.record(source, duration=0.1)
                return True
            finally:
                os.unlink(tmp_path)
                
        except Exception:
            return False
    
    def get_supported_languages(self) -> List[LanguageCode]:
        if self.engine == "sphinx":
            return [LanguageCode.EN]
        else:
            return [
                LanguageCode.EN, LanguageCode.ES, LanguageCode.FR,
                LanguageCode.DE, LanguageCode.IT, LanguageCode.PT,
                LanguageCode.JA, LanguageCode.KO, LanguageCode.ZH
            ]