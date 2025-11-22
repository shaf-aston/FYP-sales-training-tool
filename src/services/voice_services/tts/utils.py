"""
TTS Text Processing and Audio Utilities
"""

import re
import io
import logging
import hashlib
from typing import List

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    AudioSegment = None
    PYDUB_AVAILABLE = False

logger = logging.getLogger(__name__)


class TextChunker:
    """Text chunking utilities for long TTS inputs"""
    
    @staticmethod
    def chunk_text(text: str, max_chunk_length: int = 500, preserve_sentences: bool = True) -> List[str]:
        """Chunk long text for TTS processing"""
        if len(text) <= max_chunk_length:
            return [text]
        
        chunks = []
        
        if preserve_sentences:
            # Split by sentences first
            sentences = re.split(r'(?<=[.!?])\s+', text)
            current_chunk = ""
            
            for sentence in sentences:
                if len(current_chunk + sentence) <= max_chunk_length:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            # Simple word-based chunking
            words = text.split()
            current_chunk = ""
            
            for word in words:
                if len(current_chunk + word) <= max_chunk_length:
                    current_chunk += word + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = word + " "
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        
        return chunks
    
    @staticmethod
    def merge_audio_chunks(audio_chunks: List[bytes], output_format: str = "wav") -> bytes:
        """Merge multiple audio chunks into single audio file"""
        if not audio_chunks or not PYDUB_AVAILABLE:
            return audio_chunks[0] if audio_chunks else b""
        
        try:
            combined = None
            
            for chunk in audio_chunks:
                if chunk:
                    chunk_audio = AudioSegment.from_wav(io.BytesIO(chunk))
                    if combined is None:
                        combined = chunk_audio
                    else:
                        combined += chunk_audio
            
            if combined:
                output_buffer = io.BytesIO()
                combined.export(output_buffer, format=output_format)
                return output_buffer.getvalue()
            
            return b""
            
        except Exception as e:
            logger.error(f"Error merging audio chunks: {e}")
            return audio_chunks[0] if audio_chunks else b""


class AudioFormatConverter:
    """Audio format conversion utilities"""
    
    @staticmethod
    def convert_format(audio_data: bytes, input_format: str, output_format: str) -> bytes:
        """Convert audio between different formats"""
        if not PYDUB_AVAILABLE:
            logger.warning("pydub not available for format conversion")
            return audio_data
        
        if input_format.lower() == output_format.lower():
            return audio_data
        
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=input_format)
            output_buffer = io.BytesIO()
            audio.export(output_buffer, format=output_format)
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error converting audio format: {e}")
            return audio_data
    
    @staticmethod
    def get_supported_formats() -> List[str]:
        """Get list of supported audio formats"""
        base_formats = ["wav"]
        
        if PYDUB_AVAILABLE:
            base_formats.extend(["mp3", "ogg", "flac", "aac"])
        
        return base_formats


def clean_text_for_tts(text: str) -> str:
    """Clean and prepare text for TTS synthesis"""
    text = text.strip()
    
    # Remove markdown formatting
    text = text.replace("**", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("`", "")
    
    # Expand abbreviations
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
    
    # Truncate if too long
    if len(text) > 500:
        text = text[:497] + "..."
        logger.warning("Text truncated for TTS generation")
    
    return text


def get_cache_key(text: str, voice_profile) -> str:
    """Generate cache key for text and voice profile"""
    content = f"{text}_{voice_profile.model_name}_{voice_profile.speaker_id}_{voice_profile.speed}_{voice_profile.pitch_shift}"
    return hashlib.md5(content.encode()).hexdigest()