"""Optional live Groq TTS smoke test."""

import os

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()
pytestmark = pytest.mark.smoke


@pytest.mark.skipif(
    os.getenv("RUN_SMOKE_TESTS") != "1",
    reason="Set RUN_SMOKE_TESTS=1 to run live Groq TTS smoke tests.",
)
def test_groq_tts_smoke():
    key = os.environ.get("ALTERNATIVE_GROQ_API_KEY", "").split("#")[0].strip()
    if not key:
        pytest.skip("ALTERNATIVE_GROQ_API_KEY is not configured.")

    url = "https://api.groq.com/openai/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "canopylabs/orpheus-v1-english",
        "input": "Hello there, how are you doing?",
        "voice": "male_us",
        "format": "wav",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    assert response.status_code == 200, response.text
    assert response.content
