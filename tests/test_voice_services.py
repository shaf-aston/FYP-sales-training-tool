import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.voice_services.voice_service import EnhancedVoiceService, get_voice_service, reset_voice_service
from src.services.voice_services.stt_service import STTResult, EnhancedSTTService
from src.services.voice_services.tts_service import EnhancedTTSService, TTSVoiceProfile
from training.core.utils import set_seed

@pytest.fixture(autouse=True)
def set_test_seed():
    set_seed(42) # Set a fixed, valid seed for all tests

@pytest.fixture(autouse=True)
def run_around_tests():
    reset_voice_service()
    yield
    reset_voice_service()

@pytest.fixture
def mock_stt_service():
    mock = AsyncMock(spec=EnhancedSTTService)
    mock.transcribe_audio.return_value = STTResult(text="hello world", confidence=0.9)
    return mock

@pytest.fixture
def mock_tts_service():
    mock = MagicMock(spec=EnhancedTTSService)
    mock.synthesize_speech.return_value = b"mock_audio_bytes"
    mock.get_available_voices.return_value = [
        {"name": "System", "model_name": "test_model", "speaker_id": "system_speaker"}
    ]
    mock.get_stats.return_value = {"gpu_enabled": False}
    return mock

@pytest.mark.asyncio
async def test_speech_to_text_success(mock_stt_service):
    with patch('src.services.voice_services.voice_service.get_stt_service', return_value=mock_stt_service):
        service = EnhancedVoiceService()
        audio_data = b"some_audio_data"
        result = await service.speech_to_text(audio_data)
        
        assert result is not None
        assert result['text'] == "hello world"
        assert result['confidence'] == 0.9
        mock_stt_service.transcribe_audio.assert_called_once_with(audio_data, sample_rate=16000, language="en")

@pytest.mark.asyncio
async def test_text_to_speech_success(mock_tts_service):
    with patch('src.services.voice_services.voice_service.get_tts_service', return_value=mock_tts_service):
        service = EnhancedVoiceService()
        text = "hello world"
        audio_bytes = await service.text_to_speech(text)
        
        assert audio_bytes == b"mock_audio_bytes"
        mock_tts_service.synthesize_speech.assert_called_once_with(text, persona_name="System", output_format="wav")

@pytest.mark.asyncio
async def test_get_voice_capabilities(mock_stt_service, mock_tts_service):
    with patch('src.services.voice_services.voice_service.get_stt_service', return_value=mock_stt_service), \
         patch('src.services.voice_services.voice_service.get_tts_service', return_value=mock_tts_service):
        service = EnhancedVoiceService()
        capabilities = service.get_voice_capabilities()
        
        assert capabilities['stt']['available'] is True
        assert capabilities['tts']['available'] is True
        assert capabilities['available_voices'] == {"System": {"name": "System", "model_name": "test_model", "speaker_id": "system_speaker"}}

@pytest.mark.asyncio
async def test_stt_service_not_available():
    with patch('src.services.voice_services.voice_service.STT_AVAILABLE', False):
        service = EnhancedVoiceService()
        audio_data = b"some_audio_data"
        result = await service.speech_to_text(audio_data)
        assert result is None

@pytest.mark.asyncio
async def test_tts_service_not_available():
    with patch('src.services.voice_services.voice_service.TTS_AVAILABLE', False):
        service = EnhancedVoiceService()
        text = "hello world"
        audio_bytes = await service.text_to_speech(text)
        assert audio_bytes is None

@pytest.mark.asyncio
async def test_speech_to_text_file_path(mock_stt_service, tmp_path):
    with patch('src.services.voice_services.voice_service.get_stt_service', return_value=mock_stt_service):
        service = EnhancedVoiceService()
        audio_content = b"file_audio_data"
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_bytes(audio_content)
        
        result = await service.speech_to_text(str(audio_file))
        
        assert result is not None
        assert result['text'] == "hello world"
        mock_stt_service.transcribe_audio.assert_called_once_with(audio_content, sample_rate=16000, language="en")

@pytest.mark.asyncio
async def test_get_voice_service_singleton():
    reset_voice_service()
    service1 = get_voice_service()
    service2 = get_voice_service()
    assert service1 is service2