import os
import io
import time
import logging
import hashlib
import tempfile
import re
import gzip
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from threading import RLock
import numpy as np

try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import soundfile as sf
    from pydub import AudioSegment
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False

from ...interfaces import TTSService, TTSConfig, TTSResult, VoiceProfile, QualityMetrics, AudioFormat

logger = logging.getLogger(__name__)


class CoquiTTSService(TTSService):
    
    def __init__(self, config: TTSConfig):
        super().__init__(config)
        if not COQUI_AVAILABLE:
            raise ImportError("TTS library not available")
        
        self.model = None
        self.model_name = config.model_config.get("model_name", "tts_models/en/ljspeech/tacotron2-DDC")
        self.device = "cuda" if config.model_config.get("gpu_enabled", False) else "cpu"
        self.sample_rate = config.sample_rate
        self.enable_chunking = config.enable_chunking
        self.max_chunk_length = config.max_chunk_length
        self._lock = RLock()
        self.voice_profiles = {}
        self._load_model()
        
    def _load_model(self):
        with self._lock:
            if self.model is None:
                try:
                    self.model = TTS(model_name=self.model_name, progress_bar=False)
                    if hasattr(self.model, 'to') and self.device == "cuda":
                        self.model.to("cuda")
                    logger.info(f"Loaded Coqui TTS model: {self.model_name}")
                except Exception as e:
                    logger.error(f"Failed to load Coqui TTS model: {e}")
                    raise
    
    def synthesize(self, text: str, voice_profile: VoiceProfile = None,
                  output_format: AudioFormat = None) -> TTSResult:
        if not text or not text.strip():
            raise ValueError("Text is empty")
        
        start_time = time.time()
        clean_text = self._clean_text(text)
        
        if self.enable_chunking and len(clean_text) > self.max_chunk_length:
            return self._synthesize_chunked(clean_text, voice_profile, output_format)
        
        try:
            audio_array = self.model.tts(text=clean_text)
            
            if voice_profile:
                audio_array = self._apply_voice_modifications(audio_array, voice_profile)
            
            audio_data = self._array_to_bytes(audio_array, output_format or self.config.output_format)
            processing_time = time.time() - start_time
            
            return TTSResult(
                audio_data=audio_data,
                text=text,
                voice_profile_name=voice_profile.name if voice_profile else "default",
                duration=len(audio_array) / self.sample_rate,
                processing_time=processing_time,
                output_format=output_format or self.config.output_format,
                metadata={
                    "model_name": self.model_name,
                    "device": self.device,
                    "sample_rate": self.sample_rate,
                    "backend": "coqui_tts"
                }
            )
            
        except Exception as e:
            logger.error(f"Coqui TTS synthesis failed: {e}")
            raise
    
    def _synthesize_chunked(self, text: str, voice_profile: VoiceProfile = None,
                           output_format: AudioFormat = None) -> TTSResult:
        chunks = self._chunk_text(text)
        audio_chunks = []
        total_processing_time = 0
        
        for chunk in chunks:
            start_time = time.time()
            audio_array = self.model.tts(text=chunk)
            
            if voice_profile:
                audio_array = self._apply_voice_modifications(audio_array, voice_profile)
            
            audio_chunks.append(audio_array)
            total_processing_time += time.time() - start_time
        
        combined_audio = np.concatenate(audio_chunks)
        audio_data = self._array_to_bytes(combined_audio, output_format or self.config.output_format)
        
        return TTSResult(
            audio_data=audio_data,
            text=text,
            voice_profile_name=voice_profile.name if voice_profile else "default",
            duration=len(combined_audio) / self.sample_rate,
            processing_time=total_processing_time,
            output_format=output_format or self.config.output_format,
            metadata={
                "model_name": self.model_name,
                "chunks_count": len(chunks),
                "backend": "coqui_tts"
            }
        )
    
    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= self.max_chunk_length:
            return [text]
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.max_chunk_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    words = sentence.split()
                    temp_chunk = ""
                    for word in words:
                        if len(temp_chunk) + len(word) + 1 > self.max_chunk_length:
                            if temp_chunk:
                                chunks.append(temp_chunk.strip())
                            temp_chunk = word
                        else:
                            temp_chunk += (" " if temp_chunk else "") + word
                    current_chunk = temp_chunk
            else:
                current_chunk += (" " if current_chunk else "") + sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'_+', '', text)
        text = re.sub(r'`+', '', text)
        
        abbreviations = {
            " vs ": " versus ",
            " etc.": " etcetera",
            " i.e.": " that is",
            " e.g.": " for example",
            " Mr.": " Mister",
            " Mrs.": " Missis",
            " Dr.": " Doctor"
        }
        
        for abbr, expansion in abbreviations.items():
            text = text.replace(abbr, expansion)
        
        return text
    
    def _apply_voice_modifications(self, audio_array: np.ndarray, voice_profile: VoiceProfile) -> np.ndarray:
        if voice_profile.speed != 1.0:
            target_length = int(len(audio_array) / voice_profile.speed)
            if target_length > 0:
                indices = np.linspace(0, len(audio_array) - 1, target_length)
                audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array)
        
        if voice_profile.pitch_shift != 0.0:
            shift_factor = 2 ** (voice_profile.pitch_shift / 12.0)
            if shift_factor != 1.0:
                target_length = int(len(audio_array) * shift_factor)
                if target_length > 0:
                    indices = np.linspace(0, len(audio_array) - 1, target_length)
                    audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array)
        
        return audio_array
    
    def _array_to_bytes(self, audio_array: np.ndarray, output_format: AudioFormat) -> bytes:
        if not AUDIO_PROCESSING_AVAILABLE:
            raise RuntimeError("Audio processing libraries not available")
        
        if audio_array.dtype != np.int16:
            if audio_array.max() > 1.0 or audio_array.min() < -1.0:
                audio_array = audio_array / max(abs(audio_array.max()), abs(audio_array.min()))
            audio_array = (audio_array * 32767).astype(np.int16)
        
        buffer = io.BytesIO()
        sf.write(buffer, audio_array, self.sample_rate, format='WAV')
        buffer.seek(0)
        wav_data = buffer.read()
        
        if output_format != AudioFormat.WAV:
            return self._convert_format(wav_data, output_format)
        
        return wav_data
    
    def _convert_format(self, wav_data: bytes, target_format: AudioFormat) -> bytes:
        if not AUDIO_PROCESSING_AVAILABLE:
            return wav_data
        
        try:
            audio_segment = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
            output_buffer = io.BytesIO()
            
            format_str = target_format.value.lower()
            export_params = {}
            
            if format_str == "mp3":
                export_params["bitrate"] = "128k"
            elif format_str == "ogg":
                export_params["codec"] = "libvorbis"
            
            audio_segment.export(output_buffer, format=format_str, **export_params)
            output_buffer.seek(0)
            return output_buffer.read()
            
        except Exception as e:
            logger.error(f"Format conversion failed: {e}")
            return wav_data
    
    def chunk_text(self, text: str, max_length: int = None) -> List[str]:
        max_len = max_length or self.max_chunk_length
        return self._chunk_text_with_length(text, max_len)
    
    def _chunk_text_with_length(self, text: str, max_length: int) -> List[str]:
        if len(text) <= max_length:
            return [text]
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += (" " if current_chunk else "") + sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def get_supported_formats(self) -> List[AudioFormat]:
        if AUDIO_PROCESSING_AVAILABLE:
            return [AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OGG]
        else:
            return [AudioFormat.WAV]
    
    def validate_text(self, text: str) -> bool:
        return bool(text and text.strip() and len(text.strip()) > 0)
    
    def set_voice_profiles(self, profiles: Dict[str, Any]):
        for name, profile_data in profiles.items():
            voice_profile = VoiceProfile(
                name=name,
                model_name=profile_data.get("model_name", "default"),
                language=profile_data.get("language", "en"),
                speed=profile_data.get("speed", 1.0),
                pitch_shift=profile_data.get("pitch_shift", 0.0),
                metadata=profile_data
            )
            self.voice_profiles[name] = voice_profile


class PyttsxTTSService(TTSService):
    
    def __init__(self, config: TTSConfig):
        super().__init__(config)
        if not PYTTSX3_AVAILABLE:
            raise ImportError("pyttsx3 library not available")
        
        self.engine = pyttsx3.init()
        self.rate = config.model_config.get("rate", 200)
        self.volume = config.model_config.get("volume", 0.8)
        self._setup_engine()
        
    def _setup_engine(self):
        self.engine.setProperty('rate', self.rate)
        self.engine.setProperty('volume', self.volume)
        
        voices = self.engine.getProperty('voices')
        if voices:
            self.engine.setProperty('voice', voices[0].id)
    
    def synthesize(self, text: str, voice_profile: VoiceProfile = None,
                  output_format: AudioFormat = None) -> TTSResult:
        if not text or not text.strip():
            raise ValueError("Text is empty")
        
        start_time = time.time()
        clean_text = self._clean_text(text)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            self.engine.save_to_file(clean_text, tmp_path)
            self.engine.runAndWait()
            
            if not os.path.exists(tmp_path):
                raise RuntimeError("Failed to generate audio file")
            
            with open(tmp_path, 'rb') as f:
                audio_data = f.read()
            
            if output_format and output_format != AudioFormat.WAV:
                audio_data = self._convert_format(audio_data, output_format)
            
            processing_time = time.time() - start_time
            
            return TTSResult(
                audio_data=audio_data,
                text=text,
                voice_profile_name=voice_profile.name if voice_profile else "system",
                duration=self._estimate_duration(clean_text),
                processing_time=processing_time,
                output_format=output_format or AudioFormat.WAV,
                metadata={"backend": "pyttsx3", "rate": self.rate}
            )
            
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _estimate_duration(self, text: str) -> float:
        words = len(text.split())
        words_per_minute = self.rate / 5
        return (words / words_per_minute) * 60 if words_per_minute > 0 else 0
    
    def _clean_text(self, text: str) -> str:
        return re.sub(r'[*_`]', '', text.strip())
    
    def _convert_format(self, wav_data: bytes, target_format: AudioFormat) -> bytes:
        if not AUDIO_PROCESSING_AVAILABLE:
            return wav_data
        
        try:
            audio_segment = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
            output_buffer = io.BytesIO()
            audio_segment.export(output_buffer, format=target_format.value.lower())
            output_buffer.seek(0)
            return output_buffer.read()
        except Exception as e:
            logger.error(f"Format conversion failed: {e}")
            return wav_data
    
    def chunk_text(self, text: str, max_length: int = None) -> List[str]:
        max_len = max_length or 500
        if len(text) <= max_len:
            return [text]
        
        words = text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            if len(current_chunk) + len(word) + 1 > max_len:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk += (" " if current_chunk else "") + word
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def get_supported_formats(self) -> List[AudioFormat]:
        if AUDIO_PROCESSING_AVAILABLE:
            return [AudioFormat.WAV, AudioFormat.MP3]
        else:
            return [AudioFormat.WAV]
    
    def validate_text(self, text: str) -> bool:
        return bool(text and text.strip() and len(text.strip()) <= 1000)
    
    def set_voice_profiles(self, profiles: Dict[str, Any]):
        pass