"""A recording past the speech engine's per-file limit, cut into parts and joined back into one call
(core/calls/audio_parts.py, /api/calls/transcribe). ffmpeg is replaced by a fake that writes the parts it would, so
this runs where ffmpeg is not installed; the one test with the real ffmpeg is skipped there."""
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core.calls import audio_parts
from core.calls.audio_parts import AudioUnreadable, join_parts, transcribe_in_parts
from core.infra.constants import TRANSCRIPTION
from core.infra.providers.transcribe import Segment, TranscriptionUnavailable

ROOT = Path(__file__).resolve().parent.parent
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def fake_ffmpeg(parts, returncode=0, seen=None):
    """A stand-in for subprocess.run: writes `parts` ([(start, end, bytes)]) and ffmpeg's csv list where the command
    says, and records the command and keyword arguments in `seen`."""
    def run(cmd, **kw):
        if seen is not None:
            seen.update(cmd=cmd, kw=kw, source_existed=Path(cmd[cmd.index("-i") + 1]).exists())
        folder = Path(cmd[-1]).parent
        rows = []
        for i, (start, end, size) in enumerate(parts):
            name = f"part{i:03d}.mp3"
            (folder / name).write_bytes(b"\0" * size)
            rows.append(f"{name},{start:.6f},{end:.6f}")
        (folder / "parts.csv").write_text("\n".join(rows) + "\n")
        return subprocess.CompletedProcess(cmd, returncode, b"", b"recording.mp3: Invalid data found\n")
    return run


def per_part(audio, name):
    """A fake engine: one segment a second into each part, saying which part it heard."""
    return [Segment(1.0, f"heard {name}"), Segment(30.5, "still talking")]


@pytest.fixture
def with_ffmpeg(monkeypatch):
    monkeypatch.setattr(audio_parts.shutil, "which", lambda name: "/usr/bin/ffmpeg")


def test_segments_are_shifted_by_their_part_start():
    joined = join_parts([(0.0, [Segment(2.0, "one")]), (600.0, []), (1200.0, [Segment(0.5, "two"), Segment(9, "three")])])
    assert joined == [Segment(2.0, "one"), Segment(1200.5, "two"), Segment(1209.0, "three")]


def test_the_configured_parts_fit_the_engine_limit():
    part_bytes = TRANSCRIPTION["part_seconds"] * TRANSCRIPTION["part_kbps"] * 1000 / 8
    assert part_bytes < TRANSCRIPTION["max_bytes"] / 2   # room for the container and a variable bitrate
    assert TRANSCRIPTION["max_upload_bytes"] > TRANSCRIPTION["max_bytes"]


def test_parts_are_transcribed_and_joined_in_call_time(with_ffmpeg):
    seen = {}
    parts = [(0, 600.012, 4_800_000), (600.012, 1200.024, 4_800_000), (1200.024, 1500, 2_400_000)]
    segments = transcribe_in_parts(io.BytesIO(b"ID3 a long call"), "mp3", per_part, run=fake_ffmpeg(parts, seen=seen))
    assert [s.start for s in segments] == [1.0, 30.5, 601.012, 630.512, 1201.024, 1230.524]
    assert [s.text for s in segments[::2]] == ["heard part000.mp3", "heard part001.mp3", "heard part002.mp3"]
    folder = Path(seen["cmd"][-1]).parent
    assert not folder.exists()   # the recording and its parts are gone


def test_the_command_is_safe_and_makes_small_parts(with_ffmpeg):
    seen = {}
    transcribe_in_parts(io.BytesIO(b"x"), "m4a", per_part, run=fake_ffmpeg([(0, 10, 100)], seen=seen))
    cmd, kw = seen["cmd"], seen["kw"]
    assert isinstance(cmd, list) and "shell" not in kw and kw["timeout"] == TRANSCRIPTION["split_timeout_seconds"]
    assert seen["source_existed"] and Path(cmd[cmd.index("-i") + 1]).name == "recording.m4a"   # never the learner's name
    assert cmd[cmd.index("-ac") + 1] == "1" and cmd[cmd.index("-ar") + 1] == str(TRANSCRIPTION["part_sample_rate"])
    assert cmd[cmd.index("-b:a") + 1] == f"{TRANSCRIPTION['part_kbps']}k"
    assert cmd[cmd.index("-segment_time") + 1] == str(TRANSCRIPTION["part_seconds"])


def test_a_split_second_tail_is_not_sent(with_ffmpeg):
    heard = []

    def engine(audio, name):
        heard.append(name)
        return []

    transcribe_in_parts(io.BytesIO(b"x"), "mp3", engine, run=fake_ffmpeg([(0, 600, 100), (600, 600.07, 10)]))
    assert heard == ["part000.mp3"]


def test_without_a_part_list_the_parts_are_spaced_by_part_seconds(with_ffmpeg):
    def run(cmd, **kw):
        result = fake_ffmpeg([(0, 1, 100), (1, 2, 100)])(cmd, **kw)
        (Path(cmd[-1]).parent / "parts.csv").unlink()
        return result

    segments = transcribe_in_parts(io.BytesIO(b"x"), "mp3", per_part, run=run)
    assert segments[2].start == TRANSCRIPTION["part_seconds"] + 1.0


def test_a_file_ffmpeg_cannot_read_is_unreadable(with_ffmpeg):
    seen = {}
    with pytest.raises(AudioUnreadable):
        transcribe_in_parts(io.BytesIO(b"not audio"), "mp3", per_part, run=fake_ffmpeg([], returncode=1, seen=seen))
    assert not Path(seen["cmd"][-1]).parent.exists()


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("ffmpeg", 1), FileNotFoundError("ffmpeg")])
def test_ffmpeg_too_slow_or_gone_is_unavailable(with_ffmpeg, error):
    def run(cmd, **kw):
        raise error

    with pytest.raises(TranscriptionUnavailable):
        transcribe_in_parts(io.BytesIO(b"x"), "mp3", per_part, run=run)


def test_a_part_over_the_engine_limit_is_never_sent(with_ffmpeg, monkeypatch):
    monkeypatch.setitem(TRANSCRIPTION, "max_bytes", 50)
    with pytest.raises(TranscriptionUnavailable):
        transcribe_in_parts(io.BytesIO(b"x"), "mp3", per_part, run=fake_ffmpeg([(0, 600, 51)]))


def test_no_ffmpeg_means_no_splitting(monkeypatch):
    monkeypatch.setattr(audio_parts.shutil, "which", lambda name: None)
    assert not audio_parts.can_split()
    with pytest.raises(TranscriptionUnavailable):
        transcribe_in_parts(io.BytesIO(b"x"), "mp3", per_part)


# --- the route ---

def upload(client, data, name="call.mp3"):
    return client.post("/api/calls/transcribe", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")


@pytest.fixture
def labeller(monkeypatch):
    monkeypatch.setattr("backend.routes.calls.complete", lambda router, messages, **kw: "\n".join(
        f"{n}. {'AB'[n % 2]}" for n in range(1, 200)))
    monkeypatch.setattr("backend.routes.calls.ProviderRouter", lambda: None)


def test_a_recording_past_the_engine_limit_is_split(client, labeller, monkeypatch):
    monkeypatch.setitem(TRANSCRIPTION, "max_bytes", 1_000)
    monkeypatch.setattr("backend.routes.calls.can_split", lambda: True)
    calls = []

    def split(recording, ext, transcribe):
        calls.append((recording.read(), ext))
        return [Segment(5.0, "Hello, thanks for joining."), Segment(3605.0, "Thanks, bye.")]

    monkeypatch.setattr("backend.routes.calls.transcribe_in_parts", split)
    body = upload(client, b"y" * 1_001, "Big Call.MP3").get_json()
    assert calls == [(b"y" * 1_001, "mp3")]
    assert body["text"] == "[0:05] Speaker B: Hello, thanks for joining.\n[1:00:05] Speaker A: Thanks, bye."


def test_a_recording_within_the_engine_limit_is_sent_whole(client, labeller, monkeypatch):
    monkeypatch.setattr("backend.routes.calls.transcribe_in_parts", lambda *a: pytest.fail("split a small file"))
    monkeypatch.setattr("backend.routes.calls.transcribe", lambda audio, name: [Segment(0, f"{len(audio)} bytes")])
    assert upload(client, b"z" * 1_000).get_json()["text"] == "[0:00] Speaker B: 1000 bytes"


def test_past_the_upload_cap_is_too_big_even_with_ffmpeg(client, labeller, monkeypatch):
    monkeypatch.setitem(TRANSCRIPTION, "max_bytes", 1_000)
    monkeypatch.setitem(TRANSCRIPTION, "max_upload_bytes", 2_000_000)
    monkeypatch.setattr("backend.routes.calls.can_split", lambda: True)
    response = upload(client, b"y" * 2_000_001)
    assert response.status_code == 413 and "over 2 MB" in response.get_json()["error"]


def test_an_unreadable_recording_says_so(client, labeller, monkeypatch):
    monkeypatch.setitem(TRANSCRIPTION, "max_bytes", 10)
    monkeypatch.setattr("backend.routes.calls.can_split", lambda: True)

    def broken(*a):
        raise AudioUnreadable("bad")

    monkeypatch.setattr("backend.routes.calls.transcribe_in_parts", broken)
    response = upload(client, b"y" * 20)
    assert response.status_code == 400 and response.get_json()["code"] == "AUDIO_UNREADABLE"


# --- the real ffmpeg ---

@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg is not installed")
def test_a_60_minute_mp3_over_the_limit_reads(client, labeller, monkeypatch, tmp_path):
    """The plan's "done when": a 60-minute MP3 over 25 MB turns into one transcript. Ten minutes of tone is made once
    and repeated six times without re-encoding, so the file is real but quick to make."""
    ffmpeg = shutil.which("ffmpeg")
    quiet = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=300:sample_rate=16000:duration=600",
                            "-ac", "1", "-b:a", "64k", str(tmp_path / "ten.mp3")], check=True, timeout=120)
    (tmp_path / "list.txt").write_text("file 'ten.mp3'\n" * 6)
    subprocess.run(quiet + ["-f", "concat", "-safe", "0", "-i", str(tmp_path / "list.txt"), "-c", "copy",
                            str(tmp_path / "hour.mp3")], check=True, timeout=120)
    recording = (tmp_path / "hour.mp3").read_bytes()
    assert len(recording) > TRANSCRIPTION["max_bytes"]

    sizes = []

    def engine(audio, name):
        sizes.append(len(audio))
        return [Segment(2.0, f"Part {len(sizes)} starts here.")]

    monkeypatch.setattr("backend.routes.calls.transcribe", engine)
    body = upload(client, recording, "hour.mp3").get_json()
    assert len(sizes) == 6 and all(size < TRANSCRIPTION["max_bytes"] for size in sizes)
    lines = body["text"].splitlines()
    assert len(lines) == 6 and lines[-1].startswith("[50:0") and lines[-1].endswith("Part 6 starts here.")


@pytest.mark.skipif(sys.platform == "win32", reason="needs bash")
@pytest.mark.parametrize("installed", [True, False])
def test_ffmpeg_installer_installs_only_when_missing(tmp_path, installed):
    log = tmp_path / "calls"
    fake = tmp_path / "fake-sudo"   # stands in for "sudo -n": records what it was asked to run
    fake.write_text(f'#!/bin/sh\necho "$@" >> {log}\n')
    fake.chmod(0o755)
    env = {**os.environ, "SUDO": str(fake), "FFMPEG": "sh" if installed else "no-such-ffmpeg-here"}
    run = subprocess.run(["bash", "scripts/install_ffmpeg.sh"], check=False, cwd=ROOT, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    calls = log.read_text().splitlines() if log.exists() else []
    if installed:
        assert calls == []
    else:
        assert any("apt-get" in c and "install" in c and "ffmpeg" in c for c in calls)


def test_ffmpeg_reads_only_a_local_audio_file(tmp_path):
    """A "recording" that is really a playlist (HLS, concat) must not make ffmpeg open other files or URLs."""
    from core.calls.audio_parts import INPUT_FORMATS, split_command

    cmd = split_command("ffmpeg", tmp_path / "recording.mp3", tmp_path)
    assert cmd[cmd.index("-protocol_whitelist") + 1] == "file"
    allowed = cmd[cmd.index("-format_whitelist") + 1].split(",")
    assert allowed == INPUT_FORMATS.split(",") and not {"hls", "concat", "image2", "lavfi"} & set(allowed)
    assert cmd.index("-format_whitelist") < cmd.index("-i")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("body", ["#EXTM3U\n#EXTINF:10,\n/etc/hostname\n", "ffconcat version 1.0\nfile '/etc/hostname'\n"])
def test_a_playlist_dressed_as_a_recording_is_unreadable(tmp_path, body):
    with pytest.raises(AudioUnreadable):
        transcribe_in_parts(io.BytesIO(body.encode()), "mp3", lambda audio, name: [])
