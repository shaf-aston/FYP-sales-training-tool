"""
Audio processing utilities
Common audio operations and validation
"""
import io
import tempfile
import logging
from typing import Optional, Tuple, Union, List
from pathlib import Path

from .dependencies import sf, np, AudioSegment, librosa, nr, SOUNDFILE_AVAILABLE, PYDUB_AVAILABLE, NOISEREDUCE_AVAILABLE

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles common audio processing tasks"""
    
    @staticmethod
    def validate_audio(audio_data: bytes) -> bool:
        """Validate audio data format"""
        if not audio_data or len(audio_data) < 100:
            return False
        
        if not SOUNDFILE_AVAILABLE:
            return True  # Basic validation only
        
        try:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(audio_data)
                tmp.flush()
                data, samplerate = sf.read(tmp.name)
                return len(data) > 0 and samplerate > 0
        except Exception as e:
            logger.warning(f"Audio validation failed: {e}")
            return False
    
    @staticmethod
    def get_audio_info(audio_data: bytes) -> Optional[dict]:
        """Get audio file information"""
        if not SOUNDFILE_AVAILABLE:
            return None
        
        try:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(audio_data)
                tmp.flush()
                data, samplerate = sf.read(tmp.name)
                return {
                    'duration': len(data) / samplerate,
                    'sample_rate': samplerate,
                    'channels': data.shape[1] if len(data.shape) > 1 else 1,
                    'samples': len(data)
                }
        except Exception:
            return None
    
    @staticmethod
    def resample_audio(audio_data: bytes, target_sr: int = 16000) -> Optional[bytes]:
        """Resample audio to target sample rate"""
        if not SOUNDFILE_AVAILABLE or not librosa:
            return audio_data
        
        try:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(audio_data)
                tmp.flush()
                data, sr = sf.read(tmp.name)
                
                if sr != target_sr:
                    data = librosa.resample(data, orig_sr=sr, target_sr=target_sr)
                
                output = io.BytesIO()
                sf.write(output, data, target_sr, format='WAV')
                output.seek(0)
                return output.read()
        except Exception as e:
            logger.error(f"Resampling failed: {e}")
            return audio_data
    
    @staticmethod
    def reduce_noise(audio_data: bytes) -> bytes:
        """Apply noise reduction to audio"""
        if not NOISEREDUCE_AVAILABLE or not SOUNDFILE_AVAILABLE:
            return audio_data
        
        try:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(audio_data)
                tmp.flush()
                data, sr = sf.read(tmp.name)
                
                reduced_noise = nr.reduce_noise(y=data, sr=sr)
                
                output = io.BytesIO()
                sf.write(output, reduced_noise, sr, format='WAV')
                output.seek(0)
                return output.read()
        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")
            return audio_data
    
    @staticmethod
    def convert_format(audio_data: bytes, output_format: str = 'wav') -> bytes:
        """Convert audio to different format"""
        if not PYDUB_AVAILABLE:
            return audio_data
        
        try:
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            output_buffer = io.BytesIO()
            
            export_params = {}
            if output_format.lower() == 'mp3':
                export_params['bitrate'] = '128k'
            
            audio_segment.export(output_buffer, format=output_format.lower(), **export_params)
            output_buffer.seek(0)
            return output_buffer.read()
        except Exception as e:
            logger.error(f"Format conversion failed: {e}")
            return audio_data
    
    @staticmethod
    def chunk_audio(audio_data: bytes, chunk_duration: float = 30.0) -> List[bytes]:
        """Split audio into chunks"""
        if not PYDUB_AVAILABLE:
            return [audio_data]
        
        try:
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            chunk_length_ms = int(chunk_duration * 1000)
            
            chunks = []
            for i in range(0, len(audio_segment), chunk_length_ms):
                chunk = audio_segment[i:i + chunk_length_ms]
                output = io.BytesIO()
                chunk.export(output, format='wav')
                output.seek(0)
                chunks.append(output.read())
            
            return chunks
        except Exception as e:
            logger.error(f"Audio chunking failed: {e}")
            return [audio_data]