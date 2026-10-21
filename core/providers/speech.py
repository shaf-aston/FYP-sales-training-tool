"""Text to speech. One function, so another engine drops in here; model and voice live in limits.yaml speech."""

import logging

from groq import Groq

from ..constants import SPEECH
from ..logs import timed
from .config import get_groq_api_keys

logger = logging.getLogger(__name__)


@timed
def speak(text: str) -> bytes | None:
    """The text as audio, or None (no key, too long, engine failed) so the browser reads it instead."""
    keys = get_groq_api_keys()
    if not keys or not text.strip() or len(text) > SPEECH["max_chars"]:
        return None
    try:
        audio = Groq(api_key=keys[0]).audio.speech.create(
            model=SPEECH["model"], voice=SPEECH["voice"], input=text, response_format=SPEECH["format"])
        return audio.read()
    except Exception as e:  # any engine failure falls back to the browser voice
        logger.warning("speech failed: %s", e)
        return None
