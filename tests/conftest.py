"""
Global pytest configuration and fixtures

This conftest provides lightweight stubs for heavy external
dependencies and registers minimal voice service submodules so
unit tests that import those symbols can run without requiring
the full external environment.
"""
import os
import sys
import pytest
from pathlib import Path
import importlib.util
import types
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

# Mock heavy external libraries so importing project modules doesn't fail
sys.modules['transformers'] = MagicMock()
sys.modules['bitsandbytes'] = MagicMock()
sys.modules['accelerate'] = MagicMock()
sys.modules['optimum'] = MagicMock()
sys.modules['optimum.bettertransformer'] = MagicMock()
sys.modules['psutil'] = MagicMock()

mock_numpy = MagicMock()
mock_numpy.__version__ = "1.23.0"
sys.modules['numpy'] = mock_numpy
sys.modules['pandas'] = MagicMock()
sys.modules['datasets'] = MagicMock()
sys.modules['hydra'] = MagicMock()
sys.modules['hydra.core'] = MagicMock()
sys.modules['hydra.core.config_store'] = MagicMock()
sys.modules['hydra.core.global_hydra'] = MagicMock()
sys.modules['hydra.core.hydra_config'] = MagicMock()
sys.modules['omegaconf'] = MagicMock()

# Provide lightweight stubs for the voice_services submodules that unit
# tests import directly. These are intentionally minimal: they provide
# real class/type objects so tests can use them as specs when creating
# AsyncMock/MagicMock instances.
stt_mod = types.ModuleType('src.services.voice_services.stt_service')
class STTResult:
    def __init__(self, text, confidence=0.0, language="en", duration=0.0, processing_time=0.0):
        self.text = text
        self.confidence = confidence
        self.language = language
        self.duration = duration
        self.processing_time = processing_time

class EnhancedSTTService:
    """Minimal EnhancedSTTService stub used for unit test specs"""
    def transcribe_audio(self, audio_bytes, sample_rate=16000, language="en"):
        return STTResult(text="", confidence=0.0, language=language, duration=0.0, processing_time=0.0)

def get_stt_service():
    return EnhancedSTTService()

stt_mod.EnhancedSTTService = EnhancedSTTService
stt_mod.STTResult = STTResult
stt_mod.get_stt_service = get_stt_service

tts_mod = types.ModuleType('src.services.voice_services.tts_service')
class EnhancedTTSService:
    """Minimal EnhancedTTSService stub used for unit test specs"""
    def synthesize_speech(self, text, persona_name="System", output_format="wav"):
        return b""
    def get_available_voices(self):
        return []
    def get_stats(self):
        return {"gpu_enabled": False}

class TTSVoiceProfile:
    pass

def get_tts_service():
    return EnhancedTTSService()

tts_mod.EnhancedTTSService = EnhancedTTSService
tts_mod.TTSVoiceProfile = TTSVoiceProfile
tts_mod.get_tts_service = get_tts_service

# Register only the specific voice service submodules; leave the main
# 'src' package to be imported from the repository so the real modules
# (like voice_service.py) are used in tests.
sys.modules['src.services.voice_services.stt_service'] = stt_mod
sys.modules['src.services.voice_services.tts_service'] = tts_mod
sys.modules['src.services.voice_services.voice_config'] = MagicMock()

# Lightweight mocks for other internal services used during tests
# NOTE: Do NOT mock 'config_loader' - tests need the real implementation
sys.modules['services.session_service'] = MagicMock()
sys.modules['services.quality_metrics_service'] = MagicMock()
sys.modules['services.model_service'] = MagicMock()
sys.modules['services.transcript_processor'] = MagicMock()

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test")

    # Mock torch and its commonly used submodules to avoid heavy install
    mock_torch = MagicMock()
    mock_torch.__spec__ = MagicMock()
    mock_torch.__spec__.loader = MagicMock()
    sys.modules['torch'] = mock_torch
    mock_torch.utils = MagicMock()
    mock_torch.utils.data = MagicMock()
    mock_torch.utils.data.DataLoader = MagicMock()
    mock_torch.utils.data.Dataset = MagicMock()
    mock_torch.nn = MagicMock()
    sys.modules['torch.utils'] = mock_torch.utils
    sys.modules['torch.utils.data'] = mock_torch.utils.data
    sys.modules['torch.nn'] = mock_torch.nn
    sys.modules['torch.optim'] = MagicMock()


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_output_dir(project_root):
    """Create and return test output directory"""
    output_dir = project_root / "tests" / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture(scope="session")
def logs_dir(project_root):
    """Get logs directory"""
    return project_root / "logs"


@pytest.fixture
def mock_voice_service():
    """Mock voice service for testing"""
    class MockVoiceService:
        def is_available(self):
            return {"local": True, "elevenlabs": False, "huggingface": False}

        def get_voice_capabilities(self):
            return ["text-to-speech", "speech-to-text"]

    return MockVoiceService()