"""
Simplified pytest configuration 
Minimal setup for essential testing
"""
import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configure logging
logging.basicConfig(level=logging.WARNING)

# Mock heavy dependencies for faster test loading
sys.modules['transformers'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['datasets'] = MagicMock()
sys.modules['accelerate'] = MagicMock()

@pytest.fixture(scope="session")
def project_root():
    """Project root path"""
    return PROJECT_ROOT

@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        'stt_provider': 'faster_whisper',
        'tts_provider': 'pyttsx3', 
        'cache_enabled': False
    }

@pytest.fixture
def sample_audio():
    """Sample audio for testing"""
    return b'\x00' * 4096

@pytest.fixture
def sample_text():
    """Sample text for testing"""
    return "Test message for voice processing"