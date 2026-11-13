"""Text to speech. `speak(text, speaker)` tries the engines in limits.yaml `speech.engines` in turn (Kokoro on this
machine, then Groq) and returns WAV audio, or None so the browser reads it instead. Every line said is kept on disk,
so a line heard before (the bank's and the script's lines come round again) plays at once.

`speaker` picks the voice: "seller" (buy mode's seller), or "buyer" with the persona's name, whose own words (he,
she, his wife) choose a male or female voice; the same persona always gets the same voice.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import sys
import threading
import urllib.request
import wave
from functools import lru_cache

from groq import Groq

from core.infra.constants import SPEECH
from core.infra.env import ROOT_DIR
from core.infra.logs import timed
from core.infra.providers.config import get_groq_api_keys

logger = logging.getLogger(__name__)
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_FEMALE = re.compile(r"\b(she|her|hers|herself|husband|mum|mother|wife's)\b", re.I)
_MALE = re.compile(r"\b(he|his|him|himself|wife|dad|father|husband's)\b", re.I)


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


# --- how the web asks for a line: one request per sentence (web/src/lib/tone.ts speakable, voice/speech/tts.ts
# sentences). Kept in step with them so a line made ahead of time (scripts/speech_prewarm.py) is the one asked for.
_PAUSE = "¶"
_LONG_PAUSE = re.compile(r"\s*\[pause[^\]]*\]\s*")
_TONES = "slow|deliberate|calm|gentle|soft|warm|serious|firm|curious|playful|excited|upbeat"
_NOTE = re.compile(rf"\((?:{_TONES})(?:,\s*(?:{_TONES}))*\)\s*")
_KEY = re.compile(r"==(.+?)==")
_LOUD = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_STRESS = re.compile(r"(^|[\s(\"'“‘])_(\w[^_]*?)_(?=[\s.,!?…:;)—\-\"'”’]|$)")


def spoken_sentences(text: str) -> list[str]:
    """A message as the web sends it to be read: marks gone, each bubble ending a sentence, then one piece per
    sentence (a scrap under 4 characters joined to the next)."""
    bubbles = [b.strip() for b in _NOTE.sub("", _LONG_PAUSE.sub(_PAUSE, text or "")).split(_PAUSE) if b.strip()]
    words = []
    for b in bubbles:
        b = _STRESS.sub(r"\1\2", _LOUD.sub(r"\1", _KEY.sub(r"\1", b)))
        words.append(b if re.search(r"[.!?…]$", b) else f"{b}.")
    out: list[str] = []
    for part in (p.strip() for p in re.split(r"(?<=[.!?…])\s+", " ".join(words))):
        if not part:
            continue
        if out and len(out[-1]) < 4:
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def is_cached(text: str, voice: str, speed: float = 1.0) -> bool:
    return _cache_path("kokoro", voice, speed, " ".join(text.split())).exists()


def _persona_words(name: str) -> str:
    """A configured persona's words (background, pains, personality), to hear he or she in; "" for an unknown one."""
    from core.infra.loader import load_buyer_config   # here: the loader is heavier than this module needs at import
    for group in load_buyer_config()["personas"].values():
        for p in group:
            if p.get("name", "").lower() == (name or "").lower():
                return " ".join(str(v) for k, v in p.items() if k != "name")
    return ""


def pick_voice(speaker: str, persona: str = "", hint: str = "") -> str:
    """The Kokoro voice for who is speaking: the seller's, or a buyer's chosen by the persona's own words."""
    cfg = SPEECH["kokoro"]
    if speaker != "buyer":
        return cfg["seller"]
    words = f"{_persona_words(persona)} {hint}"
    female, male = len(_FEMALE.findall(words)), len(_MALE.findall(words))
    pool = cfg["female"] if female > male else cfg["male"] if male > female else cfg["female"] + cfg["male"]
    return pool[int(hashlib.sha1((persona or "?").lower().encode()).hexdigest(), 16) % len(pool)]


# --- the engines -------------------------------------------------------------------------------------------------

def kokoro_files() -> list:
    cfg = SPEECH["kokoro"]
    return [ROOT_DIR / cfg["dir"] / name for name in (cfg["model"], cfg["voices"])]


def fetch_files() -> None:
    """Kokoro's model and voices, fetched once (the deploy does it: scripts/deploy_vm.sh)."""
    for path in kokoro_files():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("speech: fetching %s", path.name)
            part = path.with_suffix(path.suffix + ".part")
            urllib.request.urlretrieve(SPEECH["kokoro"]["files_url"] + path.name, part)
            part.rename(path)


class _Kokoro:
    """Kokoro-82M through onnxruntime: one model per process."""

    def __init__(self):
        import onnxruntime as ort   # heavy imports, only when the engine is really used
        from kokoro_onnx import Kokoro

        cfg = SPEECH["kokoro"]
        fetch_files()
        folder = ROOT_DIR / cfg["dir"]
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = int(cfg["threads"])
        session = ort.InferenceSession(str(folder / cfg["model"]), options, providers=["CPUExecutionProvider"])
        self.model = Kokoro.from_session(session, str(folder / cfg["voices"]))
        self.lock = threading.Lock()   # one line at a time: two at once on two cores is slower for both

    def say(self, text: str, voice: str, speed: float) -> bytes:
        with self.lock:
            samples, rate = self.model.create(text, voice=voice, speed=speed, lang="en-gb" if voice[:1] == "b" else "en-us")
        pcm = (samples.clip(-1, 1) * 32767).astype("<i2").tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        return buf.getvalue()


@lru_cache(maxsize=1)
def kokoro() -> _Kokoro:
    return _Kokoro()


def _kokoro_engine(text: str, voice: str, speed: float) -> bytes | None:
    return kokoro().say(text, voice, speed)


def _groq_engine(text: str, voice: str, speed: float) -> bytes | None:   # noqa: ARG001 - its own voice, its own pace
    keys = get_groq_api_keys()
    if not keys:
        return None
    style = SPEECH.get("style", "")
    limit = SPEECH["max_chars"] - (len(style) + 1 if style else 0)
    client = Groq(api_key=keys[0])
    parts = []
    for piece in chunks(text, limit):
        audio = client.audio.speech.create(model=SPEECH["model"], voice=SPEECH["voice"], input=f"{style} {piece}".strip(),
                                           response_format=SPEECH["format"])
        parts.append(audio.read())
    return parts[0] if len(parts) == 1 else join_wav(parts)


ENGINES = {"kokoro": _kokoro_engine, "groq": _groq_engine}


def warm() -> None:
    """Load the first engine ahead of the first reply. Only files already here (the deploy fetches them), and never
    under a test run, which imports the app too."""
    if "pytest" in sys.modules or not all(p.exists() for p in kokoro_files()):
        return
    if SPEECH.get("engines", ["groq"])[0] == "kokoro":
        try:
            kokoro().say("Hello.", SPEECH["kokoro"]["seller"], 1.0)
        except Exception:   # noqa: BLE001 - the next engine speaks instead
            logger.exception("speech: kokoro unavailable")


# --- the cache ---------------------------------------------------------------------------------------------------

def _cache_path(engine: str, voice: str, speed: float, text: str):
    key = hashlib.sha1(f"{engine}|{voice}|{speed:.2f}|{text}".encode()).hexdigest()
    return ROOT_DIR / SPEECH.get("cache_dir", ".cache/speech") / key[:2] / f"{key}.wav"


def _trim_cache() -> None:
    """Oldest lines out once the cache passes its size."""
    folder = ROOT_DIR / SPEECH.get("cache_dir", ".cache/speech")
    files = sorted(folder.glob("*/*.wav"), key=lambda p: p.stat().st_mtime)
    total, cap = sum(p.stat().st_size for p in files), SPEECH.get("cache_max_mb", 300) * 1_000_000
    for path in files:
        if total <= cap:
            break
        total -= path.stat().st_size
        path.unlink(missing_ok=True)


@timed
def speak(text: str, speaker: str = "seller", persona: str = "", hint: str = "", speed: float = 1.0,
          voice: str | None = None, engines: list[str] | None = None) -> bytes | None:
    """The text as WAV audio, or None (empty, or no engine answered) so the browser reads it instead. `voice` and
    `engines` are for making lines ahead of time (scripts/speech_prewarm.py): a set Kokoro voice, Kokoro only."""
    text = " ".join((text or "").split())
    if not text:
        return None
    speed = min(1.5, max(0.6, speed))
    for name in engines or SPEECH.get("engines", ["groq"]):
        voice_now = (voice or pick_voice(speaker, persona, hint)) if name == "kokoro" else SPEECH["voice"]
        path = _cache_path(name, voice_now, speed, text)
        if path.exists():
            path.touch()
            return path.read_bytes()
        try:
            audio = ENGINES[name](text, voice_now, speed)
        except Exception as e:  # noqa: BLE001 - any engine failure: the next one, then the browser voice
            logger.warning("speech: %s failed: %s", name, e)
            continue
        if audio:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
            if hashlib.sha1(text.encode()).digest()[0] < 8:   # now and then, not on every line
                _trim_cache()
            return audio
    return None
