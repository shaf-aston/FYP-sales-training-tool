"""
TTS (Text-to-Speech) Service
Clean implementation with quality metrics
"""
import logging
import tempfile
import os
import time
from typing import Optional, Dict, Any, Union
from pathlib import Path

from src.models.core import TTSResult, VoiceProfile, QualityMetrics
from src.utils.dependencies import (
    TTS, pyttsx3, torch,
    DEPENDENCIES, validate_provider
)

logger = logging.getLogger(__name__)

class TTSService:
    """Text-to-Speech service with multiple providers"""
    
    def __init__(self, provider: str = "coqui", 
                 voice_profile: Optional[VoiceProfile] = None):
        self.provider = provider
        self.voice_profile = voice_profile or VoiceProfile()
        self.model = None
        self.engine = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize the TTS engine"""
        if not validate_provider("tts", self.provider):
            logger.error(f"TTS provider {self.provider} not available")
            self._fallback_provider()
            return
        
        try:
            if self.provider == "coqui":
                self._init_coqui()
            elif self.provider == "pyttsx3":
                self._init_pyttsx3()
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
                
            logger.info(f"TTS initialized with {self.provider}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider}: {e}")
            self._fallback_provider()
    
    def _init_coqui(self):
        """Initialize Coqui TTS"""
        model_name = self.voice_profile.model_name or "tts_models/en/ljspeech/tacotron2-DDC"
        self.model = TTS(model_name=model_name)
        
        # Configure voice settings
        if hasattr(self.model, 'set_speaker'):
            if self.voice_profile.speaker_name:
                self.model.set_speaker(self.voice_profile.speaker_name)
    
    def _init_pyttsx3(self):
        """Initialize pyttsx3"""
        self.engine = pyttsx3.init()
        
        # Configure voice settings
        voices = self.engine.getProperty('voices')
        
        # Set voice by gender or name
        if self.voice_profile.gender and voices:
            for voice in voices:
                if self.voice_profile.gender.lower() in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
        
        # Set speech rate and volume
        self.engine.setProperty('rate', int(self.voice_profile.speed * 200))  # Base rate ~200
        self.engine.setProperty('volume', self.voice_profile.volume)
    
    def _fallback_provider(self):
        """Try fallback providers"""
        fallbacks = ["pyttsx3", "coqui"]
        for fallback in fallbacks:
            if fallback != self.provider and validate_provider("tts", fallback):
                logger.warning(f"Falling back to {fallback}")
                self.provider = fallback
                self._initialize_engine()
                return
        
        logger.error("No TTS providers available")
        self.provider = None
    
    def speak(self, text: str, output_path: Optional[str] = None) -> TTSResult:
        """Convert text to speech"""
        if not self.provider or not text.strip():
            return TTSResult(
                success=False,
                audio_path=None,
                duration=0.0,
                processing_time=0.0,
                voice_used=str(self.voice_profile),
                quality_metrics=QualityMetrics(),
                error="No provider available or empty text"
            )
        
        start_time = time.time()
        
        try:
            if self.provider == "coqui":
                return self._speak_coqui(text, output_path, start_time)
            elif self.provider == "pyttsx3":
                return self._speak_pyttsx3(text, output_path, start_time)
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            processing_time = time.time() - start_time
            return TTSResult(
                success=False,
                audio_path=None,
                duration=0.0,
                processing_time=processing_time,
                voice_used=str(self.voice_profile),
                quality_metrics=QualityMetrics(),
                error=str(e)
            )
    
    def _speak_coqui(self, text: str, output_path: Optional[str], 
                     start_time: float) -> TTSResult:
        """Generate speech with Coqui TTS"""
        if not output_path:
            output_path = tempfile.mktemp(suffix=".wav")
        
        # Generate speech
        self.model.tts_to_file(
            text=text,
            file_path=output_path,
            speaker=self.voice_profile.speaker_name,
            speed=self.voice_profile.speed
        )
        
        processing_time = time.time() - start_time
        
        # Calculate duration and quality metrics
        duration = self._get_audio_duration(output_path)
        quality_metrics = self._calculate_quality_metrics(text, duration, processing_time)
        
        return TTSResult(
            success=True,
            audio_path=output_path,
            duration=duration,
            processing_time=processing_time,
            voice_used=f"coqui_{self.voice_profile.model_name}",
            quality_metrics=quality_metrics
        )
    
    def _speak_pyttsx3(self, text: str, output_path: Optional[str], 
                       start_time: float) -> TTSResult:
        """Generate speech with pyttsx3"""
        if not output_path:
            output_path = tempfile.mktemp(suffix=".wav")
        
        # Save to file
        self.engine.save_to_file(text, output_path)
        self.engine.runAndWait()
        
        processing_time = time.time() - start_time
        
        # Calculate duration and quality metrics
        duration = self._get_audio_duration(output_path)
        quality_metrics = self._calculate_quality_metrics(text, duration, processing_time)
        
        return TTSResult(
            success=True,
            audio_path=output_path,
            duration=duration,
            processing_time=processing_time,
            voice_used=f"pyttsx3_{self.voice_profile.gender}",
            quality_metrics=quality_metrics
        )
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration"""
        try:
            # Try with librosa if available
            if DEPENDENCIES["librosa"]:
                from src.utils.dependencies import librosa
                y, sr = librosa.load(audio_path)
                return len(y) / sr
            
            # Try with soundfile if available
            if DEPENDENCIES["soundfile"]:
                from src.utils.dependencies import sf
                frames = sf.info(audio_path).frames
                samplerate = sf.info(audio_path).samplerate
                return frames / samplerate
            
            # Fallback: estimate from file size (very rough)
            file_size = os.path.getsize(audio_path)
            estimated_duration = file_size / 32000  # Rough estimate
            return estimated_duration
        except Exception as e:
            logger.warning(f"Could not determine audio duration: {e}")
            # Estimate from text length
            words = len(text.split()) if hasattr(self, 'text') else 10
            return words * 0.5  # ~0.5 seconds per word
    
    def _calculate_quality_metrics(self, text: str, duration: float, 
                                   processing_time: float) -> QualityMetrics:
        """Calculate quality metrics for TTS"""
        words = len(text.split())
        
        # Calculate speaking rate (words per minute)
        if duration > 0:
            wpm = (words / duration) * 60
            # Ideal speaking rate is 150-160 WPM
            rate_quality = max(0.0, min(1.0, 1.0 - abs(wpm - 155) / 100))
        else:
            rate_quality = 0.5
        
        # Processing efficiency
        if words > 0 and processing_time > 0:
            efficiency = min(1.0, words / processing_time)
        else:
            efficiency = 0.5
        
        # Overall quality based on provider
        base_quality = 0.9 if self.provider == "coqui" else 0.7
        
        return QualityMetrics(
            clarity=base_quality * rate_quality,
            noise_level=0.1 if self.provider == "coqui" else 0.2,
            volume=self.voice_profile.volume
        )
    
    def update_voice_profile(self, voice_profile: VoiceProfile):
        """Update voice profile and reinitialize if needed"""
        if voice_profile != self.voice_profile:
            self.voice_profile = voice_profile
            self._initialize_engine()
    
    def list_voices(self) -> Dict[str, Any]:
        """List available voices"""
        if self.provider == "pyttsx3" and self.engine:
            voices = self.engine.getProperty('voices')
            return {
                "provider": self.provider,
                "voices": [
                    {
                        "id": voice.id,
                        "name": voice.name,
                        "languages": getattr(voice, 'languages', [])
                    }
                    for voice in voices
                ]
            }
        elif self.provider == "coqui" and self.model:
            return {
                "provider": self.provider,
                "model": self.voice_profile.model_name,
                "speakers": getattr(self.model, 'speakers', [])
            }
        
        return {"provider": self.provider, "voices": []}
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "provider": self.provider,
            "voice_profile": self.voice_profile.__dict__,
            "available": self.provider is not None
        }