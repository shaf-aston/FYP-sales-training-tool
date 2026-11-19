"""A recording past the speech engine's per-file limit (transcription.max_bytes) -> one list of timed segments.

ffmpeg cuts it into parts of `part_seconds`, each re-encoded as small mono mp3 so it fits the engine's limit. Each part
is transcribed on its own and its segments shifted by the part's start, so the speakers are then labelled once over
the whole call (core/calls/audio.py) as if it had been one file. The recording and its parts live only in a temporary
folder that is always deleted: recordings are never stored.
"""

from __future__ import annotations

import csv
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from core.infra.constants import TRANSCRIPTION
from core.infra.providers.transcribe import Segment, TranscriptionUnavailable

logger = logging.getLogger(__name__)

PART_NAME = "part%03d.mp3"
PART_LIST = "parts.csv"   # ffmpeg writes "file,start,end" per part: the true starts, not part_seconds multiples


class AudioUnreadable(ValueError):
    """ffmpeg could not decode the upload: it is not a recording, or it is damaged."""


# ffmpeg's demuxers for transcription.formats (mp3/mpga, m4a/mp4, mpeg, wav, webm, ogg, flac).
INPUT_FORMATS = "mp3,mov,mp4,m4a,3gp,3g2,mj2,mpeg,wav,matroska,webm,ogg,flac,aac"


def can_split() -> bool:
    """Whether ffmpeg is installed. Without it a recording past max_bytes is refused as too big, as before."""
    return shutil.which("ffmpeg") is not None


def split_command(ffmpeg: str, source: Path, folder: Path) -> list[str]:
    """The ffmpeg arguments that cut `source` into small parts in `folder`. Only paths we made go in, never the
    learner's file name, and it runs without a shell."""
    return [
        # Only a local file, and only audio containers: a "recording" that is really a playlist (HLS, concat)
        # would otherwise make ffmpeg open other files or URLs.
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-protocol_whitelist", "file", "-format_whitelist", INPUT_FORMATS, "-i", str(source),
        "-vn", "-ac", "1", "-ar", str(TRANSCRIPTION["part_sample_rate"]),
        "-c:a", "libmp3lame", "-b:a", f"{TRANSCRIPTION['part_kbps']}k",
        "-f", "segment", "-segment_time", str(TRANSCRIPTION["part_seconds"]), "-reset_timestamps", "1",
        "-segment_list", str(folder / PART_LIST), "-segment_list_type", "csv",
        str(folder / PART_NAME),
    ]


def join_parts(parts: list[tuple[float, list[Segment]]]) -> list[Segment]:
    """(part start, its segments) in order -> one call's segments, each timed from the start of the whole call."""
    return [Segment(start + s.start, s.text) for start, segments in parts for s in segments]


def _plan(folder: Path) -> list[tuple[Path, float]]:
    """(part file, start in the call) for each part worth sending. Falls back to part_seconds steps if ffmpeg wrote
    no list; drops a tail part shorter than min_part_seconds."""
    files = sorted(folder.glob("part*.mp3"))
    listed = folder / PART_LIST
    rows = list(csv.reader(listed.read_text("utf-8").splitlines())) if listed.exists() else []
    times = {row[0]: (float(row[1]), float(row[2])) for row in rows if len(row) >= 3}
    step = TRANSCRIPTION["part_seconds"]
    plan = []
    for i, path in enumerate(files):
        start, end = times.get(path.name, (i * step, (i + 1) * step))
        if end - start >= TRANSCRIPTION["min_part_seconds"]:
            plan.append((path, start))
    return plan


def transcribe_in_parts(recording: BinaryIO, ext: str, transcribe: Callable[[bytes, str], list[Segment]],
                        run: Callable = subprocess.run) -> list[Segment]:
    """The whole recording as timed segments, transcribed part by part. `ext` must already be one of
    transcription.formats (it names the temporary copy, so ffmpeg knows the container). Raises AudioUnreadable
    for a file ffmpeg cannot decode, TranscriptionUnavailable when ffmpeg is missing, too slow, or makes a part the
    engine would refuse."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise TranscriptionUnavailable("ffmpeg is not installed")
    with tempfile.TemporaryDirectory(prefix="eloquence-audio-") as tmp:
        folder = Path(tmp)
        source = folder / f"recording.{ext}"
        with source.open("wb") as out:
            shutil.copyfileobj(recording, out)
        try:
            done = run(split_command(ffmpeg, source, folder), capture_output=True,
                       timeout=TRANSCRIPTION["split_timeout_seconds"], check=False)
        except subprocess.TimeoutExpired as e:
            raise TranscriptionUnavailable("splitting the recording timed out") from e
        except OSError as e:
            raise TranscriptionUnavailable(f"ffmpeg did not run: {e}") from e
        if done.returncode != 0:
            tail = (done.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:]
            logger.warning("ffmpeg could not split a recording: %s", tail[0] if tail else done.returncode)
            raise AudioUnreadable("ffmpeg could not read the recording")
        source.unlink()   # the parts are all that is needed now; free the space early
        plan = _plan(folder)
        if not plan:
            raise AudioUnreadable("ffmpeg found no audio")
        parts = []
        for path, start in plan:
            audio = path.read_bytes()
            if len(audio) > TRANSCRIPTION["max_bytes"]:
                raise TranscriptionUnavailable(f"a part is {len(audio)} bytes, over the engine's limit")
            parts.append((start, transcribe(audio, path.name)))
    return join_parts(parts)
