"""
Enhanced voice processing service with optional Coqui AI TTS and emotion-aware synthesis
Gracefully handles missing optional packages with fallback functionality
Optimized with async processing, caching, and batching
"""
import os
import io
import json
import logging
import tempfile
import asyncio
import wave
import hashlib
import time
from pathlib import Path
from typing import Optional, Union, Dict, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Import transcript processor
try:
    from services.transcript_processor import get_transcript_processor
    TRANSCRIPT_PROCESSOR_AVAILABLE = True
except ImportError:
    TRANSCRIPT_PROCESSOR_AVAILABLE = False
    logging.warning("Transcript processor not available")

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

# Google Cloud Speech-to-Text imports (PRIMARY STT SERVICE)
try:
    from google.cloud import speech
    GOOGLE_CLOUD_STT_AVAILABLE = True
    logging.info("✅ Google Cloud Speech-to-Text loaded successfully")
except ImportError:
    GOOGLE_CLOUD_STT_AVAILABLE = False
    logging.info("ℹ️  Google Cloud STT not available - basic fallback will be used")
    logging.info("   To enable: pip install google-cloud-speech")

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

# Google Cloud Speech-to-Text imports (OPTIONAL)
try:
    from google.cloud import speech_v1p1beta1 as speech
    from google.oauth2 import service_account
    GOOGLE_CLOUD_STT_AVAILABLE = True
    logging.info("✅ Google Cloud Speech-to-Text loaded successfully")
except ImportError:
    GOOGLE_CLOUD_STT_AVAILABLE = False
    logging.info("ℹ️  Google Cloud Speech-to-Text not available")
    logging.info("   To enable: pip install google-cloud-speech")

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
    """Enhanced service for voice processing with emotion-aware TTS and optimized STT"""

    def __init__(self):
        self.coqui_tts = None
        self.google_cloud_client = None
        
        # Handle torch availability gracefully
        if TORCH_AVAILABLE:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
            
        # Caches
        self.voice_cache = {}
        self.transcription_cache = {}  # Cache for transcription results
        self.audio_hash_cache = {}  # Cache for audio file hashes
        
        # Optimization settings
        self.cache_ttl = 3600  # Cache time-to-live in seconds (1 hour)
        self.max_cache_size = 100  # Maximum cached transcriptions
        self.enable_parallel_processing = True
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.process_pool = None  # Lazy init for CPU-intensive tasks
        
        # Performance metrics
        self.performance_metrics = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_processing_time': 0,
            'total_processing_time': 0
        }
        
        self.emotion_profiles = self._initialize_emotion_profiles()
        
        # Initialize available services
        self.available_services = {
            'coqui_tts': False,
            'librosa': LIBROSA_AVAILABLE,
            'scipy': SCIPY_AVAILABLE,
            'numpy': NUMPY_AVAILABLE,
            'torch': TORCH_AVAILABLE,
            'elevenlabs': ELEVENLABS_AVAILABLE,
            'pyttsx3': PYTTSX3_AVAILABLE,
            'gtts': GTTS_AVAILABLE,
            'google_cloud_stt': False
        }
        # include huggingface availability
        self.available_services['huggingface'] = HUGGINGFACE_AVAILABLE
        
        # Try to load optional services
        self._setup_coqui_tts()
        self._setup_google_cloud_stt()
        
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
        logger.info(f"   Speech-to-Text (Google Cloud): {'✅ Available' if self.available_services['google_cloud_stt'] else '❌ Not available'}")
        logger.info(f"   Text-to-Speech (Coqui): {'✅ Available' if self.available_services['coqui_tts'] else '❌ Not available'}")
        logger.info(f"   Audio Processing (Librosa): {'✅ Available' if self.available_services['librosa'] else '❌ Not available'}")
        logger.info(f"   Scientific Computing (SciPy): {'✅ Available' if self.available_services['scipy'] else '❌ Not available'}")
        logger.info(f"   Device: {self.device}")
        
        if not self.available_services['google_cloud_stt']:
            logger.warning("⚠️  Google Cloud STT not available - running with basic fallback")
            logger.info("   To enable Google Cloud STT:")
            logger.info("   • pip install google-cloud-speech")
            logger.info("   • Set GOOGLE_APPLICATION_CREDENTIALS environment variable")





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

    def _setup_google_cloud_stt(self):
        """Setup Google Cloud Speech-to-Text client (lazy loading)"""
        if not GOOGLE_CLOUD_STT_AVAILABLE:
            logger.debug("Google Cloud Speech-to-Text not available - skipping")
            return

        # Check for credentials file
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not creds_path or not os.path.exists(creds_path):
            logger.warning("⚠️  Google Cloud credentials not found - set GOOGLE_APPLICATION_CREDENTIALS")
            logger.info("   To enable: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json")
            self.available_services['google_cloud_stt'] = False
            return

        # Mark as available but don't load yet (lazy loading)
        self.available_services['google_cloud_stt'] = True
        logger.info("✅ Google Cloud Speech-to-Text marked as available - will load on first use")

    def _ensure_google_cloud_loaded(self):
        """Ensure Google Cloud STT client is loaded (lazy loading)"""
        if self.google_cloud_client is not None:
            return True
            
        if not GOOGLE_CLOUD_STT_AVAILABLE or not self.available_services['google_cloud_stt']:
            return False
            
        try:
            logger.info("Loading Google Cloud Speech-to-Text client (first use)...")
            
            # Load credentials if specified
            creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if creds_path and os.path.exists(creds_path):
                credentials = service_account.Credentials.from_service_account_file(creds_path)
                self.google_cloud_client = speech.SpeechClient(credentials=credentials)
            else:
                # Use default credentials
                self.google_cloud_client = speech.SpeechClient()
            
            logger.info("✅ Google Cloud Speech-to-Text client loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Google Cloud STT client: {e}")
            self.google_cloud_client = None
            self.available_services['google_cloud_stt'] = False
            return False
    
    # ==================== OPTIMIZATION METHODS ====================
    
    async def _get_audio_cache_key(self, audio_file: Union[str, bytes], 
                                   language: str, enable_preprocessing: bool) -> str:
        """Generate cache key for audio file using hash
        
        Args:
            audio_file: Path to audio file or audio bytes
            language: Language code
            enable_preprocessing: Whether preprocessing is enabled
            
        Returns:
            Cache key string
        """
        # Get audio hash
        if isinstance(audio_file, str):
            # For file paths, use async file reading
            audio_hash = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                self._compute_file_hash,
                audio_file
            )
        else:
            # For bytes, compute hash directly
            audio_hash = hashlib.sha256(audio_file).hexdigest()[:16]
        
        # Create composite key with language and preprocessing flag
        return f"{audio_hash}_{language}_{int(enable_preprocessing)}"
    
    def _compute_file_hash(self, filepath: str) -> str:
        """Compute SHA256 hash of a file (runs in thread pool)"""
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]  # Use first 16 chars
        except Exception as e:
            logger.error(f"Failed to compute file hash: {e}")
            return str(time.time())  # Fallback to timestamp
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Retrieve result from cache if valid
        
        Args:
            cache_key: Cache key to lookup
            
        Returns:
            Cached result or None if not found/expired
        """
        if cache_key not in self.transcription_cache:
            return None
        
        cached_entry = self.transcription_cache[cache_key]
        timestamp = cached_entry.get('timestamp', 0)
        
        # Check if expired
        if time.time() - timestamp > self.cache_ttl:
            del self.transcription_cache[cache_key]
            return None
        
        return cached_entry.get('result')
    
    def _add_to_cache(self, cache_key: str, result: Dict) -> None:
        """Add result to cache with timestamp
        
        Args:
            cache_key: Cache key to store under
            result: Result dictionary to cache
        """
        # Cleanup if cache is too large
        if len(self.transcription_cache) >= self.max_cache_size:
            self._cleanup_oldest_cache_entries()
        
        self.transcription_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
    
    def _cleanup_oldest_cache_entries(self) -> None:
        """Remove oldest 20% of cache entries"""
        if not self.transcription_cache:
            return
        
        # Sort by timestamp
        sorted_keys = sorted(
            self.transcription_cache.items(),
            key=lambda x: x[1].get('timestamp', 0)
        )
        
        # Remove oldest 20%
        remove_count = max(1, len(sorted_keys) // 5)
        for key, _ in sorted_keys[:remove_count]:
            del self.transcription_cache[key]
        
        logger.info(f"Cache cleanup: removed {remove_count} old entries")
    
    def _update_metrics(self, processing_time: float) -> None:
        """Update performance metrics
        
        Args:
            processing_time: Time taken for processing in seconds
        """
        self.performance_metrics['total_processing_time'] += processing_time
        
        # Update average
        total_requests = self.performance_metrics['total_requests']
        if total_requests > 0:
            self.performance_metrics['avg_processing_time'] = (
                self.performance_metrics['total_processing_time'] / total_requests
            )
    
    async def _google_cloud_stt_optimized(self, audio_file: Union[str, bytes], 
                                         language: str = "en") -> Optional[Dict]:
        """Optimized Google Cloud STT with async I/O
        
        Args:
            audio_file: Path to audio file or audio bytes
            language: Language code
            
        Returns:
            Transcription result or None
        """
        if not self._ensure_google_cloud_loaded():
            return None
        
        try:
            # Handle file input with async I/O
            if isinstance(audio_file, str):
                content = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    self._read_audio_file,
                    audio_file
                )
            else:
                content = audio_file
            
            # Run Google Cloud API call in thread pool (it's blocking)
            result = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                self._call_google_cloud_api,
                content,
                language
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Optimized Google Cloud STT failed: {e}")
            return None
    
    def _read_audio_file(self, filepath: str) -> bytes:
        """Read audio file (runs in thread pool)"""
        with open(filepath, 'rb') as f:
            return f.read()
    
    def _call_google_cloud_api(self, content: bytes, language: str) -> Optional[Dict]:
        """Call Google Cloud API synchronously (runs in thread pool)"""
        try:
            language_code = self._convert_to_google_language_code(language)
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language_code,
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
                model="latest_long",
                use_enhanced=True,
                enable_speaker_diarization=True,
                diarization_speaker_count=2,
            )
            
            audio = speech.RecognitionAudio(content=content)
            response = self.google_cloud_client.recognize(config=config, audio=audio)
            
            if not response.results:
                return None
            
            result = response.results[0]
            alternative = result.alternatives[0]
            
            segments = []
            if alternative.words:
                segments = [{
                    "text": word.word,
                    "start": word.start_time.total_seconds(),
                    "end": word.end_time.total_seconds(),
                    "confidence": word.confidence,
                    "speaker_tag": word.speaker_tag if hasattr(word, 'speaker_tag') else None
                } for word in alternative.words]
            
            transcribed_text = alternative.transcript.strip()
            
            return {
                "text": transcribed_text,
                "language": language_code,
                "segments": segments,
                "confidence": alternative.confidence,
                "speaking_rate": self._calculate_speaking_rate_from_segments(segments),
                "pause_analysis": self._analyze_pauses_from_segments(segments),
                "emotion_indicators": self._detect_emotion_from_text(transcribed_text),
                "speaker_tags": self._extract_speaker_tags(segments),
                "method": "google_cloud_stt_optimized"
            }
            
        except Exception as e:
            logger.error(f"Google Cloud API call failed: {e}")
            return None
    
    async def _apply_preprocessing_async(self, result: Dict) -> Dict:
        """Apply preprocessing in parallel thread
        
        Args:
            result: STT result dictionary
            
        Returns:
            Preprocessed result
        """
        if not self.transcript_processor:
            return result
        
        # Run preprocessing in thread pool
        result = await asyncio.get_event_loop().run_in_executor(
            self.thread_pool,
            self._apply_preprocessing,
            result
        )
        
        return result
    
    async def batch_speech_to_text(self, audio_files: List[Union[str, bytes]],
                                  language: str = "en",
                                  enable_preprocessing: bool = True,
                                  enable_caching: bool = True) -> List[Optional[Dict]]:
        """Process multiple audio files in parallel
        
        Args:
            audio_files: List of audio file paths or bytes
            language: Language code
            enable_preprocessing: Apply preprocessing
            enable_caching: Use caching
            
        Returns:
            List of transcription results (same order as input)
        """
        if not self.enable_parallel_processing:
            # Process sequentially if parallel processing disabled
            results = []
            for audio_file in audio_files:
                result = await self.speech_to_text(
                    audio_file, language, enable_preprocessing, enable_caching
                )
                results.append(result)
            return results
        
        # Process in parallel using asyncio.gather
        logger.info(f"Processing {len(audio_files)} audio files in parallel...")
        tasks = [
            self.speech_to_text(audio_file, language, enable_preprocessing, enable_caching)
            for audio_file in audio_files
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to None
        results = [
            None if isinstance(r, Exception) else r
            for r in results
        ]
        
        success_count = sum(1 for r in results if r is not None)
        logger.info(f"✅ Batch processing complete: {success_count}/{len(audio_files)} successful")
        
        return results
    
    def get_performance_metrics(self) -> Dict:
        """Get current performance metrics
        
        Returns:
            Dictionary with performance statistics
        """
        cache_total = (
            self.performance_metrics['cache_hits'] + 
            self.performance_metrics['cache_misses']
        )
        cache_hit_rate = (
            self.performance_metrics['cache_hits'] / cache_total
            if cache_total > 0 else 0.0
        )
        
        return {
            'total_requests': self.performance_metrics['total_requests'],
            'cache_hits': self.performance_metrics['cache_hits'],
            'cache_misses': self.performance_metrics['cache_misses'],
            'cache_hit_rate': f"{cache_hit_rate:.2%}",
            'avg_processing_time': f"{self.performance_metrics['avg_processing_time']:.2f}s",
            'total_processing_time': f"{self.performance_metrics['total_processing_time']:.2f}s",
            'cache_size': len(self.transcription_cache),
            'parallel_processing_enabled': self.enable_parallel_processing
        }
    
    def clear_cache(self) -> None:
        """Clear all cached transcriptions"""
        self.transcription_cache.clear()
        self.audio_hash_cache.clear()
        logger.info("Cache cleared")
    
    # ==================== END OPTIMIZATION METHODS ====================
    
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
                           language: str = "en",
                           enable_preprocessing: bool = True,
                           enable_caching: bool = True) -> Optional[Dict]:
        """Convert speech audio to text using Google Cloud Speech-to-Text with optimizations

        Optimizations:
        - Result caching to avoid re-processing identical audio
        - Async I/O for file operations
        - Parallel preprocessing pipeline
        - Performance metrics tracking

        Args:
            audio_file: Path to audio file or audio bytes
            language: Language code for transcription
            enable_preprocessing: Apply transcript preprocessing (diarization, corrections, annotations)
            enable_caching: Use cached results if available

        Returns:
            Dict with transcribed text and analysis or None if failed
        """
        start_time = time.time()
        self.performance_metrics['total_requests'] += 1
        
        # Check cache first
        if enable_caching:
            cache_key = await self._get_audio_cache_key(audio_file, language, enable_preprocessing)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self.performance_metrics['cache_hits'] += 1
                logger.info(f"✅ Cache hit for audio (saved {time.time() - start_time:.2f}s)")
                return cached_result
            self.performance_metrics['cache_misses'] += 1
        
        # Try Google Cloud STT (primary service)
        if self._ensure_google_cloud_loaded():
            logger.info("Using Google Cloud Speech-to-Text (optimized)")
            result = await self._google_cloud_stt_optimized(audio_file, language)
            
            if result:
                # Apply preprocessing in parallel if enabled
                if enable_preprocessing:
                    result = await self._apply_preprocessing_async(result)
                
                # Cache the result
                if enable_caching:
                    self._add_to_cache(cache_key, result)
                
                # Update metrics
                processing_time = time.time() - start_time
                self._update_metrics(processing_time)
                logger.info(f"✅ STT completed in {processing_time:.2f}s")
                
                return result

        # Final fallback if Google Cloud STT is not available
        logger.warning("Google Cloud STT unavailable - using basic fallback")
        result = self._fallback_speech_to_text(audio_file, language)
        
        processing_time = time.time() - start_time
        self._update_metrics(processing_time)
        
        return result

    async def _google_cloud_stt(self, audio_file: Union[str, bytes], 
                               language: str = "en") -> Optional[Dict]:
        """Convert speech to text using Google Cloud Speech-to-Text API

        Args:
            audio_file: Path to audio file or audio bytes
            language: Language code (e.g., 'en-US', 'es-ES')

        Returns:
            Dict with transcribed text and analysis or None if failed
        """
        if not self._ensure_google_cloud_loaded():
            return None

        try:
            # Handle file input
            if isinstance(audio_file, str):
                with open(audio_file, 'rb') as audio:
                    content = audio.read()
            else:
                content = audio_file

            # Convert language code to Google Cloud format
            language_code = self._convert_to_google_language_code(language)

            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language_code,
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
                model="latest_long",  # Use latest model for best results
                use_enhanced=True,  # Use enhanced model if available
                # Enable speaker diarization for multi-speaker scenarios
                enable_speaker_diarization=True,
                diarization_speaker_count=2,
            )

            audio = speech.RecognitionAudio(content=content)

            # Perform recognition
            logger.info(f"Transcribing audio with Google Cloud STT (language: {language_code})")
            response = self.google_cloud_client.recognize(config=config, audio=audio)

            if not response.results:
                logger.warning("No transcription results from Google Cloud STT")
                return None

            # Extract the best alternative
            result = response.results[0]
            alternative = result.alternatives[0]
            
            # Build segments from word-level information
            segments = []
            if alternative.words:
                segments = [{
                    "text": word.word,
                    "start": word.start_time.total_seconds(),
                    "end": word.end_time.total_seconds(),
                    "confidence": word.confidence,
                    "speaker_tag": word.speaker_tag if hasattr(word, 'speaker_tag') else None
                } for word in alternative.words]

            # Calculate analysis metrics
            transcribed_text = alternative.transcript.strip()
            
            analysis = {
                "text": transcribed_text,
                "language": language_code,
                "segments": segments,
                "confidence": alternative.confidence,
                "speaking_rate": self._calculate_speaking_rate_from_segments(segments),
                "pause_analysis": self._analyze_pauses_from_segments(segments),
                "emotion_indicators": self._detect_emotion_from_text(transcribed_text),
                "speaker_tags": self._extract_speaker_tags(segments),
                "method": "google_cloud_stt"
            }

            logger.info(f"✅ Google Cloud STT successful: {transcribed_text[:50]}... (confidence: {alternative.confidence:.2f})")
            return analysis

        except Exception as e:
            logger.error(f"Google Cloud Speech-to-Text failed: {e}")
            return None

    def _convert_to_google_language_code(self, language: str) -> str:
        """Convert simple language code to Google Cloud format"""
        # Map common language codes to Google Cloud format
        language_map = {
            "en": "en-US",
            "es": "es-ES",
            "fr": "fr-FR",
            "de": "de-DE",
            "it": "it-IT",
            "pt": "pt-PT",
            "zh": "zh-CN",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "ar": "ar-SA",
            "hi": "hi-IN",
            "ru": "ru-RU"
        }
        
        # If already in correct format, return as is
        if "-" in language:
            return language
            
        return language_map.get(language.lower(), "en-US")

    def _calculate_speaking_rate_from_segments(self, segments: List[Dict]) -> float:
        """Calculate speaking rate from segment data"""
        if not segments:
            return 150.0  # Default average
        
        total_words = len(segments)
        if total_words == 0:
            return 150.0
        
        # Calculate duration
        first_start = segments[0].get("start", 0)
        last_end = segments[-1].get("end", 0)
        duration = last_end - first_start
        
        if duration > 0:
            return (total_words / duration) * 60  # Words per minute
        
        return 150.0

    def _analyze_pauses_from_segments(self, segments: List[Dict]) -> Dict:
        """Analyze pause patterns from segment data"""
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

    def _detect_emotion_from_text(self, text: str) -> Dict:
        """Detect emotional indicators from transcribed text"""
        text_lower = text.lower()
        
        emotion_indicators = {
            "excitement": ["amazing", "great", "fantastic", "wonderful", "awesome", "excellent"],
            "concern": ["worried", "concerned", "unsure", "doubt", "anxious", "nervous"],
            "satisfaction": ["good", "satisfied", "happy", "pleased", "glad", "content"],
            "frustration": ["frustrated", "annoyed", "difficult", "problem", "issue", "trouble"]
        }
        
        detected_emotions = {}
        for emotion, keywords in emotion_indicators.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)
            if count > 0:
                detected_emotions[emotion] = count / len(keywords)
        
        return detected_emotions

    def _extract_speaker_tags(self, segments: List[Dict]) -> Dict:
        """Extract speaker information from segments"""
        speaker_info = {}
        
        for segment in segments:
            speaker_tag = segment.get("speaker_tag")
            if speaker_tag is not None:
                if speaker_tag not in speaker_info:
                    speaker_info[speaker_tag] = {
                        "word_count": 0,
                        "speaking_time": 0
                    }
                
                speaker_info[speaker_tag]["word_count"] += 1
                duration = segment.get("end", 0) - segment.get("start", 0)
                speaker_info[speaker_tag]["speaking_time"] += duration
        
        return speaker_info

    def _apply_preprocessing(self, stt_result: Dict) -> Dict:
        """
        Apply transcript preprocessing pipeline:
        - STT corrections
        - Speaker diarization
        - Sentence segmentation
        - Training annotations
        """
        if not TRANSCRIPT_PROCESSOR_AVAILABLE:
            logger.warning("Transcript processor not available - skipping preprocessing")
            return stt_result
        
        try:
            processor = get_transcript_processor()
            processed_result = processor.process_transcript(stt_result)
            
            logger.info("✅ Transcript preprocessing complete")
            logger.info(f"   Corrections: {len(processed_result.get('corrections_applied', []))}")
            logger.info(f"   Speaker segments: {len(processed_result.get('speaker_segments', []))}")
            logger.info(f"   Annotations: {len(processed_result.get('annotations', []))}")
            
            return processed_result
        except Exception as e:
            logger.error(f"Transcript preprocessing failed: {e}")
            return stt_result



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
            HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY') or os.environ.get('HF_API_KEY')
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
                "available": self.available_services['google_cloud_stt'],
                "backends": {
                    "google_cloud": self.available_services['google_cloud_stt']
                },
                "fallback_available": True,
                "supported_languages": ["en-US", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-PT", "zh-CN", "ja-JP", "ko-KR", "ar-SA", "hi-IN", "ru-RU"] if self.available_services['google_cloud_stt'] else ["en"],
                "features": ["transcription", "timestamps", "confidence_scores", "speaker_diarization", "automatic_punctuation", "word_confidence"] if self.available_services['google_cloud_stt'] else ["basic_transcription"]
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
        
        if not self.available_services['whisper'] and not self.available_services['google_cloud_stt']:
            recommendations.append("For speech recognition (Whisper): pip install openai-whisper")
            recommendations.append("For speech recognition (Google Cloud): pip install google-cloud-speech")
        
        if not self.available_services['coqui_tts']:
            recommendations.append("For text-to-speech: pip install coqui-tts")
        
        if not self.available_services['librosa']:
            recommendations.append("For advanced audio processing: pip install librosa")
        
        if not self.available_services['scipy']:
            recommendations.append("For scientific computing: pip install scipy")
        
        if not self.available_services['torch']:
            recommendations.append("For GPU acceleration: pip install torch")
        
        if self.available_services['google_cloud_stt'] and not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            recommendations.append("Set GOOGLE_APPLICATION_CREDENTIALS environment variable to enable Google Cloud STT")
        
        return recommendations

    def is_available(self) -> Dict:
        """Check which voice services are available"""
        return {
            "google_cloud_stt": self.available_services['google_cloud_stt'],
            "coqui_tts": self.available_services['coqui_tts'],
            "emotion_synthesis": self.available_services['coqui_tts'],
            "voice_cloning": self.available_services['coqui_tts'],
            "advanced_audio_processing": self.available_services['librosa'] and self.available_services['scipy'],
            "gpu_acceleration": self.available_services['torch'] and str(self.device) != "cpu",
            "speaker_diarization": self.available_services['google_cloud_stt'],
            "fallback_mode": not any([
                self.available_services['whisper'], 
                self.available_services['google_cloud_stt'],
                self.available_services['coqui_tts']
            ])
        }

# Global enhanced voice service instance (lazy loaded)
voice_service = None

def get_voice_service():
    """Get or create the global voice service instance (lazy loading)"""
    global voice_service
    if voice_service is None:
        voice_service = EnhancedVoiceService()
    return voice_service