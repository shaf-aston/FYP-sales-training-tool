"""
Simplified TTS Service
Core text-to-speech functionality without redundancy
"""
import io
import logging
import tempfile
import time
import re
from typing import Optional, List, Dict, Any

from src.utils.audio import (
    AudioProcessor, COQUI_AVAILABLE, PYTTSX3_AVAILABLE, 
    TTS, pyttsx3, AudioSegment
)
from src.models.tts.models import TTSResult, TTSConfig, TTSProvider, VoiceProfile, TTSMetrics

logger = logging.getLogger(__name__)

class TTSService:
    """Unified Text-to-Speech service"""
    
    def __init__(self, config: TTSConfig):
        self.config = config
        self.metrics = TTSMetrics()
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the appropriate TTS model based on config"""
        try:
            if self.config.provider == TTSProvider.COQUI and COQUI_AVAILABLE:
                self.model = TTS(model_name=self.config.model_name)
                if self.config.use_gpu and hasattr(self.model, 'to'):
                    self.model.to("cuda")
                logger.info(f"Initialized Coqui TTS model: {self.config.model_name}")
            
            elif self.config.provider == TTSProvider.PYTTSX3 and PYTTSX3_AVAILABLE:
                self.model = pyttsx3.init()
                self._configure_pyttsx3()
                logger.info("Initialized pyttsx3 TTS")
            
            else:
                logger.error(f"No available TTS provider for: {self.config.provider}")
                raise RuntimeError(f"TTS provider {self.config.provider} not available")
        
        except Exception as e:
            logger.error(f"Failed to initialize TTS model: {e}")
            raise
    
    def _configure_pyttsx3(self):
        """Configure pyttsx3 settings"""
        if self.model:
            self.model.setProperty('rate', int(150 * self.config.speed))
            self.model.setProperty('volume', self.config.volume)
            
            voices = self.model.getProperty('voices')
            if voices and self.config.voice_profile:
                for voice in voices:
                    if self.config.voice_profile.voice_id in voice.id:
                        self.model.setProperty('voice', voice.id)
                        break
    
    def synthesize(self, text: str, voice_profile: Optional[VoiceProfile] = None) -> TTSResult:
        """Synthesize text to speech"""
        start_time = time.time()
        
        if not text or not text.strip():
            raise ValueError("Text is empty")
        
        text = self._normalize_text(text)
        profile = voice_profile or self.config.voice_profile
        
        try:
            if self.config.provider == TTSProvider.COQUI:
                result = self._synthesize_coqui(text, profile)
            elif self.config.provider == TTSProvider.PYTTSX3:
                result = self._synthesize_pyttsx3(text, profile)
            else:
                raise RuntimeError(f"Unsupported provider: {self.config.provider}")
            
            result.processing_time = time.time() - start_time
            result.provider = self.config.provider
            result.voice_profile = profile
            
            self.metrics.add_result(result, len(text))
            return result
        
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            error_result = TTSResult(
                audio_data=b"",
                text=text,
                voice_profile=profile,
                processing_time=time.time() - start_time,
                provider=self.config.provider,
                metadata={"error": str(e)}
            )
            self.metrics.add_result(error_result, len(text))
            raise
    
    def _synthesize_coqui(self, text: str, voice_profile: Optional[VoiceProfile]) -> TTSResult:
        """Synthesize using Coqui TTS"""
        try:
            # Generate audio
            wav = self.model.tts(text=text)
            
            # Convert to bytes
            audio_buffer = io.BytesIO()
            import soundfile as sf
            sf.write(audio_buffer, wav, self.config.sample_rate, format='WAV')
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()
            
            # Calculate duration
            duration = len(wav) / self.config.sample_rate
            
            # Apply voice modifications if profile specified
            if voice_profile and (voice_profile.speed != 1.0 or voice_profile.pitch != 1.0):
                audio_data = self._apply_voice_modifications(audio_data, voice_profile)
            
            return TTSResult(
                audio_data=audio_data,
                text=text,
                duration=duration,
                sample_rate=self.config.sample_rate,
                format=self.config.format,
                metadata={
                    'model_name': self.config.model_name,
                    'backend': 'coqui'
                }
            )
        
        except Exception as e:
            logger.error(f"Coqui TTS synthesis failed: {e}")
            raise
    
    def _synthesize_pyttsx3(self, text: str, voice_profile: Optional[VoiceProfile]) -> TTSResult:
        """Synthesize using pyttsx3"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Configure for this synthesis
            if voice_profile:
                if voice_profile.speed != 1.0:
                    self.model.setProperty('rate', int(150 * voice_profile.speed))
                if voice_profile.volume != 1.0:
                    self.model.setProperty('volume', voice_profile.volume)
            
            # Generate audio
            self.model.save_to_file(text, tmp_path)
            self.model.runAndWait()
            
            # Read generated file
            with open(tmp_path, 'rb') as f:
                audio_data = f.read()
            
            # Estimate duration (rough calculation)
            words = len(text.split())
            rate = self.model.getProperty('rate')
            duration = (words / (rate / 60)) if rate > 0 else 1.0
            
            return TTSResult(
                audio_data=audio_data,
                text=text,
                duration=duration,
                sample_rate=22050,  # pyttsx3 default
                format="wav",
                metadata={'backend': 'pyttsx3'}
            )
        
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except:
                pass
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better synthesis"""
        if not self.config.normalize_text:
            return text
        
        # Remove markdown formatting
        text = re.sub(r'[*_`]', '', text)
        
        # Expand common abbreviations
        abbreviations = {
            ' vs ': ' versus ',
            ' etc.': ' etcetera',
            ' i.e.': ' that is',
            ' e.g.': ' for example',
            ' Mr.': ' Mister',
            ' Mrs.': ' Missis',
            ' Dr.': ' Doctor'
        }
        
        for abbr, expansion in abbreviations.items():
            text = text.replace(abbr, expansion)
        
        return text.strip()
    
    def _apply_voice_modifications(self, audio_data: bytes, voice_profile: VoiceProfile) -> bytes:
        """Apply voice profile modifications to audio"""
        try:
            if not AudioSegment:
                return audio_data
            
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Apply speed modification
            if voice_profile.speed != 1.0:
                # Approximate speed change by playback rate
                new_sample_rate = int(audio.frame_rate * voice_profile.speed)
                audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
                audio = audio.set_frame_rate(22050)  # Normalize back
            
            # Apply volume modification
            if voice_profile.volume != 1.0:
                volume_change = 20 * (voice_profile.volume - 1.0)  # Convert to dB
                audio = audio + volume_change
            
            # Export back to bytes
            output_buffer = io.BytesIO()
            audio.export(output_buffer, format="wav")
            output_buffer.seek(0)
            return output_buffer.read()
        
        except Exception as e:
            logger.warning(f"Voice modification failed: {e}")
            return audio_data
    
    def batch_synthesize(self, texts: List[str], voice_profile: Optional[VoiceProfile] = None) -> List[TTSResult]:
        """Synthesize multiple texts"""
        results = []
        for text in texts:
            try:
                result = self.synthesize(text, voice_profile)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch synthesis failed for text: {e}")
                error_result = TTSResult(
                    audio_data=b"",
                    text=text,
                    voice_profile=voice_profile,
                    metadata={"error": str(e)}
                )
                results.append(error_result)
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service performance metrics"""
        return self.metrics.get_summary()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.metrics = TTSMetrics()

# Factory function for backwards compatibility
def create_tts_service(model_name: str = "tts_models/en/ljspeech/tacotron2-DDC",
                      provider: str = "coqui",
                      **kwargs) -> TTSService:
    """Create TTS service with simplified configuration"""
    config = TTSConfig(
        provider=TTSProvider(provider),
        model_name=model_name,
        **kwargs
    )
    return TTSService(config)