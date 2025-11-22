"""
Integration test for the complete voice processing pipeline
Tests STT -> AI -> TTS flow with actual data
"""
import pytest
import asyncio
from pathlib import Path

# Test data
TEST_TEXT = "Hello, this is a test message for the voice processing pipeline."
SILENT_AUDIO = b'\x00' * 4096  # Simple silent audio for testing

class TestVoiceIntegration:
    """Integration tests for complete voice processing"""
    
    @pytest.fixture
    def voice_service(self):
        """Voice service fixture"""
        from src.services import create_voice_service
        return create_voice_service()
    
    def test_text_to_speech_basic(self, voice_service):
        """Test basic text to speech conversion"""
        result = voice_service.synthesize(TEST_TEXT)
        
        assert result is not None
        assert result.text == TEST_TEXT
        assert result.audio_data
        assert len(result.audio_data) > 0
        assert result.duration > 0
    
    def test_speech_to_text_basic(self, voice_service):
        """Test basic speech to text conversion"""
        # This test uses silent audio which should return empty text
        result = voice_service.transcribe(SILENT_AUDIO)
        
        assert result is not None
        assert isinstance(result.text, str)
        assert isinstance(result.confidence, float)
        assert 0 <= result.confidence <= 1
    
    def test_voice_service_metrics(self, voice_service):
        """Test voice service metrics collection"""
        # Perform some operations
        voice_service.synthesize("Test message")
        voice_service.transcribe(SILENT_AUDIO)
        
        metrics = voice_service.get_metrics()
        assert metrics is not None
        assert 'total_requests' in metrics
        assert metrics['total_requests'] > 0
    
    def test_voice_service_health(self, voice_service):
        """Test voice service health check"""
        health = voice_service.health_check()
        
        assert health is not None
        assert 'status' in health
        assert health['stt_available'] is True
        assert health['tts_available'] is True

class TestServiceConfiguration:
    """Test service configuration and initialization"""
    
    def test_stt_configuration(self):
        """Test STT service configuration"""
        from src.services import create_stt_service
        from src.models.stt.models import STTProvider
        
        service = create_stt_service(
            model_name="base",
            provider="faster_whisper"
        )
        
        assert service.config.model_name == "base"
        assert service.config.provider == STTProvider.FASTER_WHISPER
    
    def test_tts_configuration(self):
        """Test TTS service configuration"""
        from src.services import create_tts_service
        from src.models.tts.models import TTSProvider
        
        service = create_tts_service(
            provider="pyttsx3"  # Fallback provider
        )
        
        assert service.config.provider == TTSProvider.PYTTSX3

class TestErrorHandling:
    """Test error handling in voice services"""
    
    def test_invalid_audio_handling(self):
        """Test handling of invalid audio data"""
        from src.services import create_stt_service
        
        service = create_stt_service()
        
        with pytest.raises(ValueError):
            service.transcribe(b'')  # Empty audio
        
        with pytest.raises(ValueError):
            service.transcribe(b'invalid')  # Invalid audio data
    
    def test_empty_text_handling(self):
        """Test handling of empty text"""
        from src.services import create_tts_service
        
        service = create_tts_service()
        
        with pytest.raises(ValueError):
            service.synthesize('')  # Empty text
        
        with pytest.raises(ValueError):
            service.synthesize('   ')  # Whitespace only

if __name__ == "__main__":
    pytest.main([__file__, "-v"])