"""Text to speech. One function, so another engine drops in here; model and voice live in limits.yaml speech."""

import io
import logging
import re
import wave

from groq import Groq

from ..constants import SPEECH
from .config import get_groq_api_keys

logger = logging.getLogger(__name__)
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def chunks(text: str, limit: int) -> list[str]:
    """The text as pieces the engine takes: whole sentences, joined while they fit under `limit`; a sentence
    longer than that is cut at a space. The pieces read back in order."""
    out: list[str] = []
    for sentence in SENTENCE_END.split(text.strip()):
        words = sentence.split()
        while words:
            piece = ""
            while words and len(f"{piece} {words[0]}".strip()) <= limit:
                piece = f"{piece} {words.pop(0)}".strip()
            if not piece:  # one word over the limit: cut it
                piece, words[0] = words[0][:limit], words[0][limit:]
            if out and len(f"{out[-1]} {piece}") <= limit:
                out[-1] = f"{out[-1]} {piece}"
            else:
                out.append(piece)
    return out


def join_wav(parts: list[bytes]) -> bytes:
    """Several WAV files as one: the first one's format, every one's frames in order."""
    with wave.open(io.BytesIO(parts[0])) as first:
        params = first.getparams()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setparams(params)
        for part in parts:
            with wave.open(io.BytesIO(part)) as w:
                out.writeframes(w.readframes(w.getnframes()))
    return buf.getvalue()


def speak(text: str) -> bytes | None:
    """The text as audio, or None (no key, empty, engine failed) so the browser reads it instead. Long text
    goes to the engine in sentence-sized pieces and comes back as one audio file."""
    keys = get_groq_api_keys()
    if not keys or not text.strip():
        return None
    style = SPEECH.get("style", "")
    limit = SPEECH["max_chars"] - (len(style) + 1 if style else 0)
    try:
        client = Groq(api_key=keys[0])
        parts = []
        for piece in chunks(text, limit):
            audio = client.audio.speech.create(
                model=SPEECH["model"], voice=SPEECH["voice"], input=f"{style} {piece}".strip(),
                response_format=SPEECH["format"])
            parts.append(audio.read())
        return parts[0] if len(parts) == 1 else join_wav(parts)
    except Exception as e:  # noqa: BLE001 - any engine failure falls back to the browser voice
        logger.warning("speech failed: %s", e)
        return None
