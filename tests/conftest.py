"""
Global pytest configuration and fixtures
"""
import os
import sys
import pytest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

# Common test configurations
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