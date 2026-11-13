"""Dictation: one spoken turn from the learner's mic, as text. `dictate(audio)` tries the engines in limits.yaml
`dictation.engines` in turn: Parakeet on this machine (no daily limit, the audio never leaves us), then Groq's
Whisper. None when neither hears anything, so the learner is told and can type instead.

The browser sends what MediaRecorder made (webm/opus, ogg, mp4); ffmpeg turns it into 16 kHz mono first.
Uploaded call recordings are a different job (transcribe.py: long files, timed segments).
"""

from __future__ import annotations

import io
import logging
import subprocess
import sys
import threading
from functools import lru_cache

import numpy as np

from core.infra.constants import DICTATION, TRANSCRIPTION
from core.infra.env import ROOT_DIR
from core.infra.logs import timed
from core.infra.providers.config import get_groq_api_keys

logger = logging.getLogger(__name__)
RATE = 16000


class NoSpeech(RuntimeError):
    """Nothing could be heard in the clip (silence, a bad file, every engine down)."""


def decode(audio: bytes) -> np.ndarray:
    """Any browser recording as 16 kHz mono float samples (ffmpeg). Raises NoSpeech for something that isn't audio."""
    try:
        out = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", "pipe:0", "-t", str(DICTATION["max_seconds"]),
                              "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"],
                             input=audio, capture_output=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, OSError) as e:
        raise NoSpeech(f"not audio: {e}") from e
    return np.frombuffer(out, dtype="<i2").astype(np.float32) / 32768.0


def _files() -> list:
    cfg = DICTATION["parakeet"]
    return [ROOT_DIR / cfg["dir"] / name for name in cfg["files"]]


def fetch_files() -> None:
    """Parakeet's files, fetched once into a plain folder (the deploy does it: scripts/deploy_vm.sh)."""
    from huggingface_hub import hf_hub_download   # only when fetching

    cfg = DICTATION["parakeet"]
    for path in _files():
        if not path.exists():
            logger.info("dictation: fetching %s", path.name)
            hf_hub_download(cfg["repo"], path.name, local_dir=str(path.parent))


class _Parakeet:
    def __init__(self):
        import onnx_asr   # heavy, only when the engine is really used
        import onnxruntime as ort

        fetch_files()
        options = ort.SessionOptions()
        options.intra_op_num_threads = int(DICTATION["parakeet"]["threads"])
        self.model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", str(ROOT_DIR / DICTATION["parakeet"]["dir"]),
                                         quantization="int8", sess_options=options)
        self.lock = threading.Lock()

    def hear(self, samples: np.ndarray) -> str:
        with self.lock:
            return str(self.model.recognize(samples, sample_rate=RATE)).strip()


@lru_cache(maxsize=1)
def parakeet() -> _Parakeet:
    return _Parakeet()


def _wav(samples: np.ndarray) -> bytes:
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((samples.clip(-1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _groq(samples: np.ndarray) -> str:
    from groq import Groq
    keys = get_groq_api_keys()
    if not keys:
        return ""
    client = Groq(api_key=keys[0], timeout=30, max_retries=0)
    result = client.audio.transcriptions.create(file=("turn.wav", _wav(samples)), model=TRANSCRIPTION["model"],
                                                response_format="text", language="en")
    return str(result).strip()


ENGINES = {"parakeet": lambda s: parakeet().hear(s), "groq": _groq}


def warm() -> None:
    """Load the local engine ahead of the first turn: only files already here, never under a test run."""
    if "pytest" in sys.modules or not all(p.exists() for p in _files()):
        return
    try:
        parakeet().hear(np.zeros(RATE // 2, dtype=np.float32))
    except Exception:   # noqa: BLE001 - Groq hears instead
        logger.exception("dictation: parakeet unavailable")


@timed
def dictate(audio: bytes) -> str:
    """What was said in the clip. Raises NoSpeech when nothing was heard or no engine answered."""
    samples = decode(audio)
    if samples.size < RATE // 4 or float(np.abs(samples).max(initial=0)) < 0.005:
        raise NoSpeech("silence")
    for name in DICTATION.get("engines", ["groq"]):
        try:
            text = ENGINES[name](samples)
        except Exception as e:  # noqa: BLE001 - the next engine, then the learner types
            logger.warning("dictation: %s failed: %s", name, e)
            continue
        if any(c.isalnum() for c in text):
            return text
    raise NoSpeech("no engine heard anything")
