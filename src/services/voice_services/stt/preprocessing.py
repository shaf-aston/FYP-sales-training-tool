"""
STT Audio Preprocessing Utilities
"""

import os
import tempfile
import logging
from typing import Dict, Union

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None
    SOUNDFILE_AVAILABLE = False

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    nr = None
    NOISEREDUCE_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class AudioPreprocessor:
    """Audio preprocessing utilities for STT"""
    
    @staticmethod
    def validate_audio_format(audio_data: bytes) -> Dict[str, Union[bool, str]]:
        """Validate audio format and detect corruption"""
        validation = {
            "valid": True,
            "format_detected": None,
            "sample_rate": None,
            "duration": None,
            "issues": [],
            "recommendations": []
        }
        
        try:
            if len(audio_data) < 44:
                validation["valid"] = False
                validation["issues"].append("Audio file too small")
                return validation
            
            # Check WAV header
            if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
                validation["format_detected"] = "wav"
            elif audio_data[:3] == b'ID3' or audio_data[:2] == b'\xff\xfb':
                validation["format_detected"] = "mp3"
                validation["recommendations"].append("Convert MP3 to WAV for better processing")
            
            if SOUNDFILE_AVAILABLE:
                try:
                    import io
                    with io.BytesIO(audio_data) as audio_buffer:
                        info = sf.info(audio_buffer)
                        validation["sample_rate"] = info.samplerate
                        validation["duration"] = info.duration
                        
                        if info.samplerate < 8000:
                            validation["issues"].append("Sample rate too low (< 8kHz)")
                        elif info.samplerate > 48000:
                            validation["recommendations"].append("Consider downsampling from high sample rate")
                        
                        if info.duration < 0.1:
                            validation["issues"].append("Audio too short (< 0.1s)")
                        elif info.duration > 300:
                            validation["recommendations"].append("Long audio may need chunking")
                            
                except Exception as e:
                    validation["issues"].append(f"Could not read audio info: {e}")
            
        except Exception as e:
            validation["valid"] = False
            validation["issues"].append(f"Audio validation error: {e}")
        
        return validation
    
    @staticmethod
    def apply_noise_reduction(audio_data: bytes, sample_rate: int = 16000) -> bytes:
        """Apply noise reduction to audio data"""
        if not NOISEREDUCE_AVAILABLE or not SOUNDFILE_AVAILABLE:
            logger.warning("Noise reduction not available")
            return audio_data
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
            
            try:
                audio, sr = sf.read(tmp_file.name)
                reduced_noise = nr.reduce_noise(y=audio, sr=sr)
                
                output_buffer = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                sf.write(output_buffer.name, reduced_noise, sr)
                
                with open(output_buffer.name, 'rb') as f:
                    processed_audio = f.read()
                
                os.unlink(output_buffer.name)
                return processed_audio
                
            finally:
                os.unlink(tmp_file.name)
                
        except Exception as e:
            logger.error(f"Error applying noise reduction: {e}")
            return audio_data
    
    @staticmethod
    def normalize_audio_level(audio_data: bytes) -> bytes:
        """Normalize audio level"""
        if not SOUNDFILE_AVAILABLE or not NUMPY_AVAILABLE:
            return audio_data
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
            
            try:
                audio, sr = sf.read(tmp_file.name)
                
                # Normalize to [-1, 1] range
                max_val = np.max(np.abs(audio))
                if max_val > 0:
                    normalized_audio = audio / max_val
                else:
                    normalized_audio = audio
                
                output_buffer = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                sf.write(output_buffer.name, normalized_audio, sr)
                
                with open(output_buffer.name, 'rb') as f:
                    processed_audio = f.read()
                
                os.unlink(output_buffer.name)
                return processed_audio
                
            finally:
                os.unlink(tmp_file.name)
                
        except Exception as e:
            logger.error(f"Error normalizing audio: {e}")
            return audio_data