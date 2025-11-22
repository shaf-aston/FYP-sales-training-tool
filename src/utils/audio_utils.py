"""
Audio Processing Utilities
Handles audio file operations, format conversion, and validation
"""
import logging
import os
import tempfile
import wave
from typing import Optional, Tuple, Dict, Any, Union
from pathlib import Path

from src.utils.dependencies import sf, librosa, DEPENDENCIES

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Audio processing utilities"""
    
    SUPPORTED_FORMATS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}
    DEFAULT_SAMPLE_RATE = 16000
    DEFAULT_CHANNELS = 1
    
    @staticmethod
    def validate_audio_file(file_path: str) -> Dict[str, Any]:
        """
        Validate audio file and get metadata
        
        Returns:
            Dict with validation results and metadata
        """
        if not os.path.exists(file_path):
            return {"valid": False, "error": "File not found"}
        
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in AudioProcessor.SUPPORTED_FORMATS:
            return {
                "valid": False,
                "error": f"Unsupported format: {file_ext}",
                "supported": list(AudioProcessor.SUPPORTED_FORMATS)
            }
        
        try:
            if DEPENDENCIES["soundfile"]:
                info = sf.info(file_path)
                return {
                    "valid": True,
                    "duration": info.frames / info.samplerate,
                    "sample_rate": info.samplerate,
                    "channels": info.channels,
                    "format": info.format,
                    "file_size": os.path.getsize(file_path)
                }
            elif DEPENDENCIES["librosa"]:
                y, sr = librosa.load(file_path, sr=None)
                return {
                    "valid": True,
                    "duration": len(y) / sr,
                    "sample_rate": sr,
                    "channels": 1 if y.ndim == 1 else y.shape[0],
                    "format": "unknown",
                    "file_size": os.path.getsize(file_path)
                }
            else:
                # Basic validation without detailed info
                return {
                    "valid": True,
                    "duration": 0,
                    "sample_rate": 0,
                    "channels": 0,
                    "format": "unknown",
                    "file_size": os.path.getsize(file_path),
                    "warning": "Limited audio processing capabilities"
                }
        
        except Exception as e:
            logger.error(f"Audio validation failed: {e}")
            return {"valid": False, "error": str(e)}
    
    @staticmethod
    def convert_to_wav(input_path: str, output_path: Optional[str] = None,
                      sample_rate: int = DEFAULT_SAMPLE_RATE,
                      channels: int = DEFAULT_CHANNELS) -> str:
        """
        Convert audio file to WAV format
        
        Args:
            input_path: Input audio file path
            output_path: Output WAV file path (auto-generated if None)
            sample_rate: Target sample rate
            channels: Target channel count
            
        Returns:
            Path to converted WAV file
        """
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".wav")
        
        try:
            if DEPENDENCIES["librosa"]:
                # Load audio with librosa
                y, sr = librosa.load(input_path, sr=sample_rate, mono=(channels == 1))
                
                # Save as WAV
                if DEPENDENCIES["soundfile"]:
                    sf.write(output_path, y, sr)
                else:
                    # Fallback to wave module for basic WAV writing
                    AudioProcessor._write_wav_basic(output_path, y, sr)
                
                logger.info(f"Converted {input_path} to {output_path}")
                return output_path
            
            elif DEPENDENCIES["soundfile"]:
                # Use soundfile for conversion
                data, sr = sf.read(input_path)
                
                # Resample if needed (basic approach)
                if sr != sample_rate:
                    logger.warning("Sample rate conversion not available without librosa")
                
                # Convert to mono if needed
                if data.ndim > 1 and channels == 1:
                    data = data.mean(axis=1)
                
                sf.write(output_path, data, sr)
                return output_path
            
            else:
                # No conversion libraries available
                logger.error("No audio conversion libraries available")
                raise RuntimeError("Audio conversion not supported")
        
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            raise
    
    @staticmethod
    def _write_wav_basic(output_path: str, audio_data, sample_rate: int):
        """Write WAV file using basic wave module"""
        # Convert float32 to int16
        import numpy as np
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        with wave.open(output_path, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
    
    @staticmethod
    def normalize_audio(audio_data, target_level: float = 0.8) -> any:
        """
        Normalize audio to target level
        
        Args:
            audio_data: Audio data array
            target_level: Target normalization level (0.0-1.0)
            
        Returns:
            Normalized audio data
        """
        try:
            import numpy as np
            
            # Convert to numpy if needed
            if not isinstance(audio_data, np.ndarray):
                audio_data = np.array(audio_data)
            
            # Calculate current peak
            peak = np.abs(audio_data).max()
            
            if peak > 0:
                # Normalize to target level
                normalized = audio_data * (target_level / peak)
                return normalized
            else:
                return audio_data
        
        except Exception as e:
            logger.error(f"Audio normalization failed: {e}")
            return audio_data
    
    @staticmethod
    def apply_noise_reduction(audio_data, sample_rate: int) -> any:
        """
        Apply basic noise reduction
        
        Args:
            audio_data: Audio data array
            sample_rate: Audio sample rate
            
        Returns:
            Processed audio data
        """
        try:
            if not DEPENDENCIES["librosa"]:
                logger.warning("Librosa not available for noise reduction")
                return audio_data
            
            import numpy as np
            
            # Simple spectral subtraction approach
            # This is a basic implementation - more sophisticated methods available
            
            # Convert to frequency domain
            stft = librosa.stft(audio_data)
            magnitude = np.abs(stft)
            phase = np.angle(stft)
            
            # Estimate noise from first few frames
            noise_frames = min(10, magnitude.shape[1] // 4)
            noise_profile = np.mean(magnitude[:, :noise_frames], axis=1, keepdims=True)
            
            # Spectral subtraction
            alpha = 2.0  # Over-subtraction factor
            subtracted = magnitude - alpha * noise_profile
            
            # Ensure non-negative values
            subtracted = np.maximum(subtracted, 0.1 * magnitude)
            
            # Reconstruct signal
            processed_stft = subtracted * np.exp(1j * phase)
            processed_audio = librosa.istft(processed_stft)
            
            return processed_audio
        
        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")
            return audio_data
    
    @staticmethod
    def trim_silence(audio_data, sample_rate: int, 
                    threshold_db: float = -30.0) -> Tuple[any, float]:
        """
        Trim silence from beginning and end of audio
        
        Args:
            audio_data: Audio data array
            sample_rate: Audio sample rate
            threshold_db: Silence threshold in dB
            
        Returns:
            Tuple of (trimmed_audio, trim_duration)
        """
        try:
            if not DEPENDENCIES["librosa"]:
                logger.warning("Librosa not available for silence trimming")
                return audio_data, 0.0
            
            # Use librosa's trim function
            trimmed_audio, index = librosa.effects.trim(
                audio_data, 
                top_db=-threshold_db
            )
            
            # Calculate trimmed duration
            original_duration = len(audio_data) / sample_rate
            trimmed_duration = len(trimmed_audio) / sample_rate
            trim_amount = original_duration - trimmed_duration
            
            logger.debug(f"Trimmed {trim_amount:.2f}s of silence")
            
            return trimmed_audio, trim_amount
        
        except Exception as e:
            logger.error(f"Silence trimming failed: {e}")
            return audio_data, 0.0
    
    @staticmethod
    def split_on_silence(audio_data, sample_rate: int,
                        min_silence_len: float = 0.5,
                        silence_thresh_db: float = -40.0,
                        keep_silence: float = 0.1) -> list:
        """
        Split audio on silence
        
        Args:
            audio_data: Audio data array
            sample_rate: Audio sample rate
            min_silence_len: Minimum silence length in seconds
            silence_thresh_db: Silence threshold in dB
            keep_silence: Amount of silence to keep (seconds)
            
        Returns:
            List of audio segments
        """
        try:
            if not DEPENDENCIES["librosa"]:
                logger.warning("Librosa not available for silence splitting")
                return [audio_data]
            
            import numpy as np
            
            # Convert parameters to samples
            min_silence_samples = int(min_silence_len * sample_rate)
            keep_silence_samples = int(keep_silence * sample_rate)
            
            # Calculate RMS energy
            frame_length = 2048
            hop_length = 512
            
            rms = librosa.feature.rms(
                y=audio_data, 
                frame_length=frame_length,
                hop_length=hop_length
            )[0]
            
            # Convert to dB
            rms_db = librosa.amplitude_to_db(rms)
            
            # Find silence regions
            silence_mask = rms_db < silence_thresh_db
            
            # Find split points
            split_indices = []
            in_silence = False
            silence_start = 0
            
            for i, is_silent in enumerate(silence_mask):
                if is_silent and not in_silence:
                    silence_start = i
                    in_silence = True
                elif not is_silent and in_silence:
                    silence_duration = i - silence_start
                    if silence_duration >= min_silence_samples // hop_length:
                        # Add split point in middle of silence
                        split_point = (silence_start + i) // 2 * hop_length
                        split_indices.append(split_point)
                    in_silence = False
            
            # Split audio at identified points
            if not split_indices:
                return [audio_data]
            
            segments = []
            start_idx = 0
            
            for split_idx in split_indices:
                end_idx = min(split_idx + keep_silence_samples, len(audio_data))
                if end_idx > start_idx:
                    segments.append(audio_data[start_idx:end_idx])
                start_idx = max(0, split_idx - keep_silence_samples)
            
            # Add final segment
            if start_idx < len(audio_data):
                segments.append(audio_data[start_idx:])
            
            logger.info(f"Split audio into {len(segments)} segments")
            return segments
        
        except Exception as e:
            logger.error(f"Audio splitting failed: {e}")
            return [audio_data]
    
    @staticmethod
    def get_audio_features(audio_data, sample_rate: int) -> Dict[str, float]:
        """
        Extract basic audio features
        
        Args:
            audio_data: Audio data array
            sample_rate: Audio sample rate
            
        Returns:
            Dictionary of audio features
        """
        try:
            import numpy as np
            
            features = {
                "duration": len(audio_data) / sample_rate,
                "sample_rate": sample_rate,
                "rms_energy": float(np.sqrt(np.mean(audio_data**2))),
                "zero_crossing_rate": 0.0,
                "spectral_centroid": 0.0
            }
            
            # Zero crossing rate
            zero_crossings = np.diff(np.signbit(audio_data))
            features["zero_crossing_rate"] = np.sum(zero_crossings) / len(audio_data)
            
            if DEPENDENCIES["librosa"]:
                # More sophisticated features with librosa
                features["spectral_centroid"] = float(
                    np.mean(librosa.feature.spectral_centroid(
                        y=audio_data, sr=sample_rate
                    ))
                )
                
                # Add tempo if detectable
                try:
                    tempo, _ = librosa.beat.beat_track(y=audio_data, sr=sample_rate)
                    features["tempo"] = float(tempo)
                except:
                    features["tempo"] = 0.0
            
            return features
        
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return {
                "duration": len(audio_data) / sample_rate if sample_rate > 0 else 0,
                "sample_rate": sample_rate,
                "error": str(e)
            }