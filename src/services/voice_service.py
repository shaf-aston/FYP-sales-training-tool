"""
Enhanced voice processing service with optional Coqui AI TTS and emotion-aware synthesis
Gracefully handles missing optional packages with fallback functionality
"""
import os
import io
import json
import logging
import tempfile
import asyncio
import wave
from pathlib import Path
from typing import Optional, Union, Dict, List
from datetime import datetime
from enum import Enum

# Check for numpy availability (should be available as it's in requirements)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("NumPy not available - some features will be limited")

# Check for torch availability (should be available as it's in requirements)
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not available - falling back to CPU-only mode")

# Voice processing imports (OPTIONAL) - Using transformers for Whisper
try:
    from transformers import pipeline, AutoProcessor, AutoModelForSpeechSeq2Seq
    WHISPER_AVAILABLE = True
    logging.info("✅ Transformers loaded successfully for Whisper")
except ImportError:
    WHISPER_AVAILABLE = False
    logging.info("ℹ️  Transformers not available - speech-to-text features will use fallback")
    logging.info("   To enable: pip install transformers")

# Coqui TTS imports (OPTIONAL)
try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
    logging.info("✅ Coqui TTS loaded successfully")
except ImportError:
    COQUI_AVAILABLE = False
    logging.info("ℹ️  Coqui TTS not available - text-to-speech will use simple fallback")
    logging.info("   To enable: pip install coqui-tts")

# Audio processing libraries (OPTIONAL)
try:
    import librosa
    LIBROSA_AVAILABLE = True
    logging.info("✅ Librosa loaded successfully")
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.info("ℹ️  Librosa not available - advanced audio processing disabled")
    logging.info("   To enable: pip install librosa")

try:
    import scipy.io.wavfile as wavfile
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.info("ℹ️  SciPy not available - some audio features limited")

# Local TTS providers only (no API keys needed)
ELEVENLABS_AVAILABLE = False  # Disabled for local-only operation
logging.info("ℹ️  Using local TTS only - no API keys required")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
    logging.info("✅ pyttsx3 available for offline TTS")
except Exception:
    PYTTSX3_AVAILABLE = False

# Google TTS disabled (requires internet)
GTTS_AVAILABLE = False
logging.info("ℹ️  gTTS disabled for offline operation")

# Hugging Face disabled (no API tokens)  
HUGGINGFACE_AVAILABLE = False
logging.info("ℹ️  Hugging Face API disabled - using local models only")
if HUGGINGFACE_AVAILABLE:
    logging.info("✅ Hugging Face API key detected - huggingface TTS available via Inference API")

logger = logging.getLogger(__name__)

class VoiceEmotion(Enum):
    """Voice emotion types for TTS"""
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    ENTHUSIASTIC = "enthusiastic"
    EMPATHETIC = "empathetic"
    CONFIDENT = "confident"

class EnhancedVoiceService:
    """Enhanced service for voice processing with emotion-aware TTS"""

    def __init__(self):
        self.whisper_model = None
        self.coqui_tts = None
        
        # Handle torch availability gracefully
        if TORCH_AVAILABLE:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
            
        self.voice_cache = {}
        self.emotion_profiles = self._initialize_emotion_profiles()
        
        # Initialize available services
        self.available_services = {
            'whisper': False,
            'coqui_tts': False,
            'librosa': LIBROSA_AVAILABLE,
            'scipy': SCIPY_AVAILABLE,
            'numpy': NUMPY_AVAILABLE,
            'torch': TORCH_AVAILABLE,
            'elevenlabs': ELEVENLABS_AVAILABLE,
            'pyttsx3': PYTTSX3_AVAILABLE,
            'gtts': GTTS_AVAILABLE
        }
        # include huggingface availability
        self.available_services['huggingface'] = HUGGINGFACE_AVAILABLE
        
        # Try to load optional services
        self._load_whisper()
        self._setup_coqui_tts()
        
        # Log service availability
        self._log_service_status()

    def _initialize_emotion_profiles(self) -> Dict:
        """Initialize emotion profiles for different voice styles"""
        return {
            VoiceEmotion.NEUTRAL: {
                "speed": 1.0,
                "pitch_shift": 0.0,
                "energy": 0.5,
                "pause_duration": 0.3
            },
            VoiceEmotion.FRIENDLY: {
                "speed": 0.95,
                "pitch_shift": 0.1,
                "energy": 0.7,
                "pause_duration": 0.2
            },
            VoiceEmotion.PROFESSIONAL: {
                "speed": 1.05,
                "pitch_shift": -0.05,
                "energy": 0.6,
                "pause_duration": 0.4
            },
            VoiceEmotion.ENTHUSIASTIC: {
                "speed": 1.1,
                "pitch_shift": 0.15,
                "energy": 0.9,
                "pause_duration": 0.1
            },
            VoiceEmotion.EMPATHETIC: {
                "speed": 0.9,
                "pitch_shift": -0.1,
                "energy": 0.4,
                "pause_duration": 0.5
            },
            VoiceEmotion.CONFIDENT: {
                "speed": 1.0,
                "pitch_shift": -0.05,
                "energy": 0.8,
                "pause_duration": 0.2
            }
        }

    def _log_service_status(self):
        """Log the status of all voice services"""
        logger.info("🎤 Voice Service Status:")
        logger.info(f"   Speech-to-Text (Whisper): {'✅ Available' if self.available_services['whisper'] else '❌ Not available'}")
        logger.info(f"   Text-to-Speech (Coqui): {'✅ Available' if self.available_services['coqui_tts'] else '❌ Not available'}")
        logger.info(f"   Audio Processing (Librosa): {'✅ Available' if self.available_services['librosa'] else '❌ Not available'}")
        logger.info(f"   Scientific Computing (SciPy): {'✅ Available' if self.available_services['scipy'] else '❌ Not available'}")
        logger.info(f"   Device: {self.device}")
        
        if not any([self.available_services['whisper'], self.available_services['coqui_tts']]):
            logger.warning("⚠️  No voice services available - running in text-only mode")
            logger.info("   To enable voice features:")
            logger.info("   • Speech-to-Text: pip install openai-whisper")
            logger.info("   • Text-to-Speech: pip install coqui-tts")

    def _load_whisper(self):
        """Load Whisper model for speech-to-text (lazy loading)"""
        if not WHISPER_AVAILABLE:
            logger.debug("Transformers not available - Whisper disabled")
            self.available_services['whisper'] = False
            return

        # Mark as available but don't load yet (lazy loading)
        self.available_services['whisper'] = True
        logger.info("✅ Whisper (transformers) marked as available - will load on first use")

    def _ensure_whisper_loaded(self):
        """Ensure Whisper model is loaded (lazy loading)"""
        if self.whisper_model is not None:
            return True
            
        if not WHISPER_AVAILABLE:
            return False
            
        try:
            logger.info("Loading Whisper model from transformers (first use)...")
            # Use environment variable or default to Large-v3 Turbo
            model_name = os.environ.get("WHISPER_MODEL", "openai/whisper-large-v3-turbo")
            
            self.whisper_model = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                return_timestamps=True
            )
            logger.info(f"✅ Whisper model '{model_name}' loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.whisper_model = None
            self.available_services['whisper'] = False
            return False

    def _setup_coqui_tts(self):
        """Setup Coqui TTS model (lazy loading)"""
        if not COQUI_AVAILABLE:
            logger.debug("Coqui TTS not available - skipping")
            return

        # Don't load the model immediately - do it lazily when first needed
        # This avoids hanging on initialization and license prompts
        self.coqui_tts = None
        self.available_services['coqui_tts'] = True  # Mark as available for lazy loading
        logger.info("✅ Coqui TTS available for lazy loading")
    
    def _ensure_coqui_loaded(self):
        """Ensure Coqui TTS model is loaded (lazy loading)"""
        if not COQUI_AVAILABLE or not self.available_services['coqui_tts']:
            return False
            
        if self.coqui_tts is not None:
            return True
            
        try:
            logger.info("Loading Coqui TTS model (lazy)...")
            
            # Use a smaller, faster model for better user experience
            model_name = "tts_models/en/ljspeech/tacotron2-DDC"
            
            if TORCH_AVAILABLE:
                self.coqui_tts = TTS(
                    model_name=model_name,
                    progress_bar=False
                ).to(self.device)
            else:
                # Fallback for systems without torch
                self.coqui_tts = TTS(
                    model_name=model_name,
                    progress_bar=False
                )
            
            logger.info("✅ Coqui TTS model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Coqui TTS model: {e}")
            logger.info("   Falling back to alternative TTS backends")
            self.available_services['coqui_tts'] = False
            return False

    async def speech_to_text(self, audio_file: Union[str, bytes], 
                           language: str = "en") -> Optional[Dict]:
        """Convert speech audio to text using Whisper with enhanced analysis

        Args:
            audio_file: Path to audio file or audio bytes
            language: Language code for transcription

        Returns:
            Dict with transcribed text and analysis or None if failed
        """
        # Ensure Whisper model is loaded (lazy loading)
        if not self._ensure_whisper_loaded():
            logger.warning("Whisper model not available - using fallback")
            return self._fallback_speech_to_text(audio_file, language)

        try:
            # Handle bytes input by saving to temporary file
            if isinstance(audio_file, bytes):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                    temp_file.write(audio_file)
                    audio_path = temp_file.name
            else:
                audio_path = audio_file

            logger.info(f"Transcribing audio: {audio_path}")

            # Run Whisper transcription with transformers pipeline
            result = self.whisper_model(audio_path)
            
            # Extract text from pipeline result
            if isinstance(result, dict) and "text" in result:
                text = result["text"].strip()
            elif isinstance(result, list) and len(result) > 0:
                text = result[0]["text"].strip()
            else:
                text = str(result).strip()
            
            # Extract additional information
            analysis = {
                "text": text,
                "language": result.get("language", language),
                "segments": result.get("segments", []),
                "confidence": self._calculate_confidence(result),
                "speaking_rate": self._calculate_speaking_rate(result),
                "pause_analysis": self._analyze_pauses(result),
                "emotion_indicators": self._detect_emotion_from_speech(result),
                "method": "whisper"
            }

            # Clean up temporary file
            if isinstance(audio_file, bytes):
                os.unlink(audio_path)

            logger.info(f"Transcription successful: {text[:50]}...")
            return analysis

        except Exception as e:
            logger.error(f"Speech-to-text failed: {e}")
            return self._fallback_speech_to_text(audio_file, language)

    def _fallback_speech_to_text(self, audio_file: Union[str, bytes], 
                                language: str = "en") -> Optional[Dict]:
        """Fallback speech-to-text when Whisper is not available"""
        logger.info("Using fallback speech-to-text (placeholder)")
        
        # In a real implementation, this could use other services like:
        # - Google Speech-to-Text API
        # - Azure Cognitive Services
        # - AWS Transcribe
        # - Or simply return a default message
        
        return {
            "text": "[Speech-to-text not available - please type your message]",
            "language": language,
            "segments": [],
            "confidence": 0.0,
            "speaking_rate": 150.0,
            "pause_analysis": {"average_pause": 0, "max_pause": 0, "total_pauses": 0, "pause_rate": 0},
            "emotion_indicators": {},
            "method": "fallback",
            "note": "Install openai-whisper for speech recognition: pip install openai-whisper"
        }

    async def text_to_speech(self, text: str, 
                           emotion: VoiceEmotion = VoiceEmotion.PROFESSIONAL,
                           speaker_voice: str = "female_1") -> Optional[bytes]:
        """Convert text to speech using Coqui TTS with emotion

        Args:
            text: Text to convert to speech
            emotion: Desired emotion for the voice
            speaker_voice: Voice identifier

        Returns:
            Audio bytes or None if failed
        """
        # Try to ensure Coqui TTS is loaded
        if not self._ensure_coqui_loaded():
            logger.warning("Coqui TTS model not available - using fallback")
            return self._fallback_text_to_speech(text, emotion, speaker_voice)

        try:
            logger.info(f"Converting text to speech with {emotion.value} emotion: {text[:50]}...")

            # Get emotion profile
            emotion_profile = self.emotion_profiles.get(emotion, self.emotion_profiles[VoiceEmotion.NEUTRAL])
            
            # Process text for better speech synthesis
            processed_text = self._preprocess_text_for_tts(text, emotion_profile)

            # Generate speech with Coqui TTS
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                self.coqui_tts.tts_to_file(
                    text=processed_text,
                    file_path=temp_file.name,
                    speaker_wav=self._get_speaker_reference(speaker_voice),
                    language="en",
                    split_sentences=True
                )
                
                # Read the generated audio
                with open(temp_file.name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                
                # Clean up
                os.unlink(temp_file.name)

            # Apply emotion-based post-processing
            processed_audio = self._apply_emotion_processing(audio_data, emotion_profile)

            logger.info("✅ Text-to-speech conversion successful")
            return processed_audio

        except Exception as e:
            logger.error(f"Text-to-speech failed: {e}")
            return self._fallback_text_to_speech(text, emotion, speaker_voice)

    def _fallback_text_to_speech(self, text: str, 
                                emotion: VoiceEmotion = VoiceEmotion.PROFESSIONAL,
                                speaker_voice: str = "female_1") -> Optional[bytes]:
        """Fallback text-to-speech when Coqui TTS is not available"""
        logger.info("Using fallback text-to-speech (attempting alternative backends)")

        # Local-only TTS backends (no API keys required)
        
        # Try pyttsx3 first (offline, reliable on Windows)
        if self.available_services.get('pyttsx3'):
            try:
                audio = self._tts_pyttsx3(text, emotion, speaker_voice)
                if audio:
                    logger.info("Using pyttsx3 for TTS")
                    return audio
            except Exception as e:
                logger.warning(f"pyttsx3 TTS failed: {e}")

        # Cloud services disabled for local-only operation
        logger.warning("ElevenLabs and cloud TTS disabled - using local backends only")

        # Try gTTS (Google TTS) as a lightweight network fallback
        if self.available_services.get('gtts'):
            try:
                audio = self._tts_gtts(text, emotion, speaker_voice)
                if audio:
                    return audio
            except Exception:
                logger.warning("gTTS failed, all fallbacks exhausted")

        logger.info(f"All TTS fallbacks failed for: '{text[:50]}...'")
        return None

    def _tts_elevenlabs(self, text: str, emotion: VoiceEmotion, speaker_voice: str) -> Optional[bytes]:
        """Use ElevenLabs API/SDK to synthesize speech and return bytes"""
        # Minimal safe implementation: user must configure API key via env var
        try:
            # ElevenLabs has multiple SDK variations; this keeps it defensive
            api_key = os.environ.get('ELEVENLABS_API_KEY') or os.environ.get('ELEVENLABS_KEY')
            if not api_key:
                raise RuntimeError("ElevenLabs API key not configured")

            # Most ElevenLabs SDKs provide a tts.synthesize or similar; use requests fallback
            try:
                # Try official SDK usage
                from elevenlabs import generate, set_api_key, voices
                set_api_key(api_key)
                voice_id = speaker_voice if speaker_voice else None
                audio = generate(text=text, voice=voice_id, model='eleven_multilingual_v1')
                if isinstance(audio, bytes):
                    return audio
                # Some SDKs return a file-like object
                if hasattr(audio, 'read'):
                    return audio.read()
            except Exception:
                # Try simple HTTP fallback (not implemented here)
                raise
        except Exception as e:
            logger.debug(f"ElevenLabs TTS unavailable: {e}")
            return None

    def _tts_pyttsx3(self, text: str, emotion: VoiceEmotion, speaker_voice: str) -> Optional[bytes]:
        """Use pyttsx3 to synthesize speech offline and return WAV bytes"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Configure voice rate and volume from emotion profile
            profile = self.emotion_profiles.get(emotion, {})
            rate = int(200 * profile.get('speed', 1.0))
            engine.setProperty('rate', rate)

            # Save to a temporary file
            fd, path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)

            def _save():
                engine.save_to_file(text, path)
                engine.runAndWait()

            # Run in separate thread to avoid blocking
            import threading
            t = threading.Thread(target=_save)
            t.start()
            t.join(timeout=10)
            if t.is_alive():
                engine.stop()
                raise RuntimeError('pyttsx3 synthesis timed out')

            with open(path, 'rb') as f:
                data = f.read()
            try:
                os.unlink(path)
            except Exception:
                pass
            return data
        except Exception as e:
            logger.debug(f"pyttsx3 TTS failed: {e}")
            return None

    def _tts_gtts(self, text: str, emotion: VoiceEmotion, speaker_voice: str) -> Optional[bytes]:
        """Use gTTS to synthesize speech (network) and return MP3 or WAV bytes"""
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang='en')
            fd, path = tempfile.mkstemp(suffix='.mp3')
            os.close(fd)
            tts.save(path)
            # Convert MP3 to WAV bytes if scipy available, otherwise return MP3 bytes
            with open(path, 'rb') as f:
                data = f.read()
            try:
                os.unlink(path)
            except Exception:
                pass
            return data
        except Exception as e:
            logger.debug(f"gTTS failed: {e}")
            return None

    def _tts_huggingface(self, text: str, emotion: VoiceEmotion, speaker_voice: str) -> Optional[bytes]:
        """Use Hugging Face Inference API to synthesize speech and return bytes"""
        try:
            if not HUGGINGFACE_API_KEY:
                raise RuntimeError('Hugging Face API key not configured')

            # Use requests to call the Inference API TTS model
            import requests
            hf_model = os.environ.get('HF_TTS_MODEL', 'facebook/fastspeech2-en-ljspeech')
            headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
            api_url = f"https://api-inference.huggingface.co/models/{hf_model}"
            payload = {"inputs": text}
            resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.content
            else:
                logger.debug(f"HuggingFace TTS failed: {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            logger.debug(f"HuggingFace TTS failed: {e}")
            return None

    async def generate_voice_with_context(self, text: str, context: Dict, 
                                        persona_attributes: Dict) -> Optional[bytes]:
        """Generate voice with contextual emotion and style

        Args:
            text: Text to convert
            context: Conversation context
            persona_attributes: Persona information

        Returns:
            Audio bytes or None if failed
        """
        # Determine appropriate emotion based on context
        emotion = self._determine_contextual_emotion(context, persona_attributes)
        
        # Select appropriate voice
        speaker_voice = self._select_voice_for_persona(persona_attributes)
        
        return await self.text_to_speech(text, emotion, speaker_voice)

    def _preprocess_text_for_tts(self, text: str, emotion_profile: Dict) -> str:
        """Preprocess text for better TTS output"""
        # Add pauses for emotion
        pause_duration = emotion_profile.get("pause_duration", 0.3)
        
        # Replace punctuation with appropriate pauses
        text = text.replace(".", f". <break time='{pause_duration}s'/>")
        text = text.replace(",", f", <break time='{pause_duration/2}s'/>")
        text = text.replace("?", f"? <break time='{pause_duration}s'/>")
        text = text.replace("!", f"! <break time='{pause_duration}s'/>")
        
        # Emphasize important words based on emotion
        if emotion_profile.get("energy", 0.5) > 0.7:
            # Add emphasis for enthusiastic speech
            text = text.replace("great", "<emphasis>great</emphasis>")
            text = text.replace("excellent", "<emphasis>excellent</emphasis>")
            text = text.replace("amazing", "<emphasis>amazing</emphasis>")
        
        return text

    def _get_speaker_reference(self, speaker_voice: str) -> Optional[str]:
        """Get reference audio for speaker voice cloning"""
        # In production, this would return path to reference audio files
        # For now, we'll use default Coqui speakers
        return None

    def _apply_emotion_processing(self, audio_data: bytes, emotion_profile: Dict) -> bytes:
        """Apply emotion-based audio processing"""
        try:
            # Simple processing - in production, use proper audio manipulation
            # This is a placeholder for emotion-based audio modifications
            return audio_data
        except Exception as e:
            logger.error(f"Emotion processing failed: {e}")
            return audio_data

    def _determine_contextual_emotion(self, context: Dict, persona_attributes: Dict) -> VoiceEmotion:
        """Determine appropriate emotion based on context"""
        emotional_tone = context.get("emotional_tone", "neutral")
        conversation_stage = context.get("conversation_stage", "discovery")
        
        # Map context to emotions
        if emotional_tone == "negative":
            return VoiceEmotion.EMPATHETIC
        elif emotional_tone == "positive":
            return VoiceEmotion.ENTHUSIASTIC
        elif conversation_stage == "closing":
            return VoiceEmotion.CONFIDENT
        elif conversation_stage == "opening":
            return VoiceEmotion.FRIENDLY
        else:
            return VoiceEmotion.PROFESSIONAL

    def _select_voice_for_persona(self, persona_attributes: Dict) -> str:
        """Select appropriate voice based on persona"""
        primary_persona = persona_attributes.get("primary_persona", "professional")
        
        voice_mapping = {
            "analytical": "professional_female",
            "driver": "confident_female",
            "expressive": "friendly_female",
            "amiable": "warm_female",
            "skeptical": "measured_female"
        }
        
        return voice_mapping.get(primary_persona, "female_1")

    def _calculate_confidence(self, whisper_result: Dict) -> float:
        """Calculate confidence score from Whisper result"""
        segments = whisper_result.get("segments", [])
        if not segments:
            return 0.5
        
        # Calculate average confidence from segments
        confidences = []
        for segment in segments:
            if "confidence" in segment:
                confidences.append(segment["confidence"])
            elif "words" in segment:
                word_confidences = [word.get("confidence", 0.5) for word in segment["words"]]
                if word_confidences:
                    confidences.append(sum(word_confidences) / len(word_confidences))
        
        if confidences:
            return sum(confidences) / len(confidences)
        return 0.5

    def _calculate_speaking_rate(self, whisper_result: Dict) -> float:
        """Calculate speaking rate (words per minute)"""
        segments = whisper_result.get("segments", [])
        if not segments:
            return 150.0  # Average speaking rate
        
        total_words = 0
        total_duration = 0
        
        for segment in segments:
            words = segment.get("text", "").split()
            total_words += len(words)
            total_duration += segment.get("end", 0) - segment.get("start", 0)
        
        if total_duration > 0:
            return (total_words / total_duration) * 60  # Words per minute
        
        return 150.0

    def _analyze_pauses(self, whisper_result: Dict) -> Dict:
        """Analyze pause patterns in speech"""
        segments = whisper_result.get("segments", [])
        pauses = []
        
        for i in range(len(segments) - 1):
            current_end = segments[i].get("end", 0)
            next_start = segments[i + 1].get("start", 0)
            pause_duration = next_start - current_end
            
            if pause_duration > 0.1:  # Significant pause
                pauses.append(pause_duration)
        
        if pauses:
            return {
                "average_pause": sum(pauses) / len(pauses),
                "max_pause": max(pauses),
                "total_pauses": len(pauses),
                "pause_rate": len(pauses) / len(segments) if segments else 0
            }
        
        return {"average_pause": 0, "max_pause": 0, "total_pauses": 0, "pause_rate": 0}

    def _detect_emotion_from_speech(self, whisper_result: Dict) -> Dict:
        """Detect emotional indicators from speech patterns"""
        # This is a simplified version - in production, use proper emotion detection
        text = whisper_result.get("text", "").lower()
        
        emotion_indicators = {
            "excitement": ["amazing", "great", "fantastic", "wonderful"],
            "concern": ["worried", "concerned", "unsure", "doubt"],
            "satisfaction": ["good", "satisfied", "happy", "pleased"],
            "frustration": ["frustrated", "annoyed", "difficult", "problem"]
        }
        
        detected_emotions = {}
        for emotion, keywords in emotion_indicators.items():
            count = sum(1 for keyword in keywords if keyword in text)
            if count > 0:
                detected_emotions[emotion] = count / len(keywords)
        
        return detected_emotions

    def get_voice_capabilities(self) -> Dict:
        """Get available voice processing capabilities"""
        return {
            "speech_to_text": {
                "available": self.available_services['whisper'],
                "fallback_available": True,
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "zh"] if self.available_services['whisper'] else ["en"],
                "features": ["transcription", "timestamps", "confidence_scores", "emotion_detection"] if self.available_services['whisper'] else ["basic_transcription"]
            },
            "text_to_speech": {
                "available": self.available_services['coqui_tts'] or any([
                    self.available_services.get('elevenlabs'),
                    self.available_services.get('pyttsx3'),
                    self.available_services.get('gtts')
                ]),
                "backends": {
                    "coqui": self.available_services['coqui_tts'],
                    "elevenlabs": self.available_services.get('elevenlabs'),
                    "pyttsx3": self.available_services.get('pyttsx3'),
                    "gtts": self.available_services.get('gtts')
                },
                "supported_emotions": [emotion.value for emotion in VoiceEmotion],
                "features": ["emotion_synthesis", "voice_cloning", "multilingual", "contextual_adaptation"]
            },
            "processing": {
                "device": str(self.device),
                "dependencies": self.available_services,
                "recommendations": self._get_installation_recommendations()
            }
        }

    def _get_installation_recommendations(self) -> List[str]:
        """Get recommendations for missing dependencies"""
        recommendations = []
        
        if not self.available_services['whisper']:
            recommendations.append("For speech recognition: pip install openai-whisper")
        
        if not self.available_services['coqui_tts']:
            recommendations.append("For text-to-speech: pip install coqui-tts")
        
        if not self.available_services['librosa']:
            recommendations.append("For advanced audio processing: pip install librosa")
        
        if not self.available_services['scipy']:
            recommendations.append("For scientific computing: pip install scipy")
        
        if not self.available_services['torch']:
            recommendations.append("For GPU acceleration: pip install torch")
        
        return recommendations

    def is_available(self) -> Dict:
        """Check which voice services are available"""
        return {
            "whisper": self.available_services['whisper'],
            "coqui_tts": self.available_services['coqui_tts'],
            "emotion_synthesis": self.available_services['coqui_tts'],
            "voice_cloning": self.available_services['coqui_tts'],
            "advanced_audio_processing": self.available_services['librosa'] and self.available_services['scipy'],
            "gpu_acceleration": self.available_services['torch'] and str(self.device) != "cpu",
            "fallback_mode": not any([self.available_services['whisper'], self.available_services['coqui_tts']])
        }

# Global enhanced voice service instance (lazy loaded)
voice_service = None

def get_voice_service():
    """Get or create the global voice service instance (lazy loading)"""
    global voice_service
    if voice_service is None:
        voice_service = EnhancedVoiceService()
    return voice_service