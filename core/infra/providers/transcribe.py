"""Speech to text. One function, so another engine drops in here; model and limits live in limits.yaml transcription."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from groq import Groq

from core.infra.constants import TRANSCRIPTION
from core.infra.logs import timed
from core.infra.providers.config import get_groq_api_keys

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment:
    start: float   # seconds from the start of the recording
    text: str


class TranscriptionUnavailable(RuntimeError):
    """No key, or the engine failed: the learner is told to use a transcript instead."""


def _field(item, name):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


@timed
def transcribe(audio: bytes, filename: str) -> list[Segment]:
    """The recording as timed segments of speech (no speakers: the engine does not tell voices apart).
    Raises TranscriptionUnavailable."""
    keys = get_groq_api_keys()
    if not keys:
        raise TranscriptionUnavailable("no key")
    try:
        client = Groq(api_key=keys[0], timeout=TRANSCRIPTION["timeout_seconds"], max_retries=0)
        result = client.audio.transcriptions.create(
            file=(filename, audio), model=TRANSCRIPTION["model"], response_format="verbose_json",
        )
    except Exception as e:   # noqa: BLE001 - any engine failure means the same thing to the learner
        logger.warning("transcription failed: %s", e)
        raise TranscriptionUnavailable(str(e)) from e
    segments = _field(result, "segments") or []
    out = [Segment(float(_field(s, "start") or 0), str(_field(s, "text") or "").strip()) for s in segments]
    return [s for s in out if s.text]
