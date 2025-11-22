"""
Essential test suite for the sales roleplay chatbot
Covers core functionality with minimal redundancy
"""
import pytest
import sys
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

@pytest.fixture
def project_root_path():
    """Project root path fixture"""
    return project_root

class TestBasicImports:
    """Test that essential modules can be imported"""
    
    def test_core_services_import(self):
        """Test core services can be imported"""
        try:
            from src.services import VoiceService, STTService, TTSService
            assert VoiceService is not None
            assert STTService is not None
            assert TTSService is not None
        except ImportError as e:
            pytest.fail(f"Failed to import core services: {e}")
    
    def test_models_import(self):
        """Test models can be imported"""
        try:
            from src.models import STTResult, TTSResult, VoiceProfile
            assert STTResult is not None
            assert TTSResult is not None
            assert VoiceProfile is not None
        except ImportError as e:
            pytest.fail(f"Failed to import models: {e}")
    
    def test_utils_import(self):
        """Test utilities can be imported"""
        try:
            from src.utils.audio import AudioProcessor
            from src.utils.config import config
            assert AudioProcessor is not None
            assert config is not None
        except ImportError as e:
            pytest.fail(f"Failed to import utilities: {e}")

class TestConfiguration:
    """Test configuration management"""
    
    def test_config_loading(self):
        """Test configuration loads without errors"""
        from src.utils.config import config, get_config
        
        assert config is not None
        assert get_config() is not None
        assert hasattr(config, 'app')
        assert hasattr(config, 'voice')
        assert hasattr(config, 'ai')
    
    def test_config_values(self):
        """Test configuration has expected values"""
        from src.utils.config import config
        
        assert config.app.title
        assert config.app.version
        assert config.voice.stt_provider
        assert config.voice.tts_provider

class TestVoiceServices:
    """Test voice services functionality"""
    
    def test_voice_service_creation(self):
        """Test voice service can be created"""
        from src.services import create_voice_service
        
        service = create_voice_service()
        assert service is not None
        assert hasattr(service, 'stt_service')
        assert hasattr(service, 'tts_service')
    
    def test_stt_service_creation(self):
        """Test STT service can be created"""
        from src.services import create_stt_service
        
        service = create_stt_service()
        assert service is not None
        assert hasattr(service, 'config')
        assert hasattr(service, 'transcribe')
    
    def test_tts_service_creation(self):
        """Test TTS service can be created"""
        from src.services import create_tts_service
        
        service = create_tts_service()
        assert service is not None
        assert hasattr(service, 'config')
        assert hasattr(service, 'synthesize')

class TestLegacyCompatibility:
    """Test backward compatibility with existing code"""
    
    def test_legacy_voice_service_import(self):
        """Test legacy voice service imports work"""
        try:
            from src.services.voice_services import get_voice_service, get_stt_service, get_tts_service
            assert get_voice_service is not None
            assert get_stt_service is not None
            assert get_tts_service is not None
        except ImportError as e:
            pytest.fail(f"Failed to import legacy services: {e}")
    
    def test_legacy_voice_emotion_import(self):
        """Test legacy voice emotion import works"""
        try:
            from src.services.voice_services import VoiceEmotion
            assert VoiceEmotion is not None
        except ImportError as e:
            pytest.fail(f"Failed to import VoiceEmotion: {e}")

class TestAudioDependencies:
    """Test audio dependency management"""
    
    def test_dependency_checking(self):
        """Test dependency availability checking"""
        from src.utils.audio.dependencies import get_availability_status
        
        status = get_availability_status()
        assert isinstance(status, dict)
        assert 'whisper' in status
        assert 'coqui_tts' in status
        assert 'soundfile' in status
    
    def test_audio_processor(self):
        """Test audio processor can be instantiated"""
        from src.utils.audio import AudioProcessor
        
        processor = AudioProcessor()
        assert processor is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])