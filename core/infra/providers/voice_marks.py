"""The script's stress marks, heard (marks: core/buy_mode/script_engine/words/tone.py): a **loud** word said louder
and higher, a _stretched_ word drawn out, ==key== words given a beat before and said a little slower and higher.

Kokoro reads plain phonemes, so the marks are carried out around it. The marked words get a full stress in the
phonemes; the model reports when every phoneme is spoken, so each marked word's stretch of audio is known. That
stretch is swapped for the same words from a slower take of the same line, raised in pitch by resampling (which
also shortens it, so the take is that much slower again), made louder, and crossfaded in where the words meet the
rest of the line. Everything else is the model's own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from core.infra.constants import SPEECH

RATE = 24000   # Kokoro's sample rate
_KEY = r"==(?P<key>.+?)=="
_LOUD = r"\*\*(?P<loud>\S(?:.*?\S)?)\*\*"
_STRETCH = r"(?P<lead>^|[\s(\"'“‘])_(?P<stretch>\w[^_]*?)_(?=[\s.,!?…:;)—\-\"'”’]|$)"   # "_all_", never belief_cost
_MARK = re.compile(f"{_KEY}|{_LOUD}|{_STRETCH}")
_VOWELS = set("aeiouæɑɐɒɔəɛɜɪʊʌʏøœɤɯɨʉɘɵɞɶyAEIOUᵻ")
_PUNCT_CHARS = ".,!?…:;—-\"'“”‘’()"


@dataclass(frozen=True)
class Run:
    text: str
    mark: str = ""   # "", "loud", "stretch" or "key"


def runs(sentence: str) -> list[Run]:
    """The sentence as plain and marked runs, in order."""
    out, at = [], 0
    for m in _MARK.finditer(sentence or ""):
        kind = next(k for k in ("key", "loud", "stretch") if m[k])
        out.append(Run(sentence[at:m.start() + len(m["lead"] or "")]))
        out.append(Run(m[kind], kind))
        at = m.end()
    out.append(Run((sentence or "")[at:]))
    return [r for r in out if r.text]


def plain(sentence: str) -> str:
    """The words alone: marks gone, and a stray one left by a split line ("==" with no partner) gone too."""
    text = "".join(r.text for r in runs(sentence))
    return " ".join(re.sub(r"==|\*\*|(?<!\w)_|_(?!\w)", "", text).split())


def marked(sentence: str) -> bool:
    return any(r.mark for r in runs(sentence))


def full_stress(word: str) -> str:
    """A word's phonemes with a primary stress: its secondary one raised, or one put before its first vowel."""
    if "ˈ" in word:
        return word
    if "ˌ" in word:
        return word.replace("ˌ", "ˈ", 1)
    i = next((i for i, c in enumerate(word) if c in _VOWELS), None)
    return word if i is None else word[:i] + "ˈ" + word[i:]


def _words(tokenizer, text: str, lang: str) -> list[str]:
    """The text's phonemes word by word, punctuation that stands alone ("..." after a marked word) stuck to the
    word before it, as it is when the whole line is phonemised."""
    out: list[str] = []
    for w in tokenizer.known(tokenizer.phonemize(text, lang)).split() if text.strip() else []:
        if out and not w.strip(_PUNCT_CHARS):
            out[-1] += w
        else:
            out.append(w)
    return out


def phonemes(tokenizer, sentence: str, lang: str) -> tuple[str, list[tuple[str, int, int]]]:
    """The sentence's phonemes (only those the model knows) and each marked run's [start, end) in them.

    The whole line is phonemised at once, so every word sounds as it does in context; each run is phonemised alone
    only to count its words. When the counts disagree (a number read as several words, say) the runs' own phonemes
    are joined instead. In a marked run of several words only those that carry a stress already are given a full
    one ("the whole _year_", not "THE whole year"); a single marked word always is."""
    parts = runs(sentence)
    whole = _words(tokenizer, plain(sentence), lang)
    per_run, joined = [_words(tokenizer, plain(r.text), lang) for r in parts], []
    for ws in per_run:   # a run that starts with bare punctuation ("..." after **now**): it belongs to the word before
        if joined and ws and not ws[0].strip(_PUNCT_CHARS):
            joined[-1] += ws.pop(0)
        joined += ws
    counts = [len(ws) for ws in per_run]
    if sum(counts) != len(whole):
        whole = joined
    spans, out, pos, at = [], [], 0, 0
    for r, n in zip(parts, counts):
        first = last = None
        for word in whole[at:at + n]:
            if r.mark:   # the word's own sounds; punctuation stuck to it stays outside the span
                lead = len(word) - len(word.lstrip(_PUNCT_CHARS))
                sounds = word[lead:].rstrip(_PUNCT_CHARS)
                stressed = full_stress(sounds) if n == 1 or "ˈ" in sounds or "ˌ" in sounds else sounds
                word = word[:lead] + stressed + word[lead + len(sounds):]
                first = pos + lead if first is None else first
                last = pos + lead + len(stressed)
            out.append(word)
            pos += len(word) + 1
        if first is not None:
            spans.append((r.mark, first, last))
        at += n
    return " ".join(out), spans


# --- the audio ---------------------------------------------------------------------------------------------------

def _ramp(n: int) -> np.ndarray:
    return (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, max(n, 1)))).astype(np.float32)


def _edge(timings, i: int, before: bool) -> int:
    """The sample where the words from phoneme i start (before=True), or where those ending before phoneme i end:
    the middle of the gap next to them when there is one."""
    j = i - 1 if before else i
    if 0 <= j < len(timings) and timings[j].phoneme == " ":
        return int((timings[j].start + timings[j].end) / 2 * RATE)
    return int((timings[i].start if before else timings[i - 1].end) * RATE)


def _quietest(audio: np.ndarray, a: int, b: int) -> int:
    """The quietest 5 ms in audio[a:b], where a beat can go without a click."""
    frame = RATE // 200
    a, b = max(0, a), min(len(audio), b)
    if b - a < 2 * frame:
        return a
    energy = np.convolve(audio[a:b] ** 2, np.ones(frame), "valid")
    return a + int(np.argmin(energy)) + frame // 2


def _higher(piece: np.ndarray, semitones: float) -> np.ndarray:
    """The piece played faster by a resample: higher by `semitones`, and shorter by the same ratio."""
    if not semitones or len(piece) < 4:
        return piece
    n = int(round(len(piece) / 2 ** (semitones / 12)))
    spectrum = np.fft.rfft(piece)
    keep = n // 2 + 1
    return (np.fft.irfft(spectrum[:keep], n) * (n / len(piece))).astype(piece.dtype)


def _splice(audio: np.ndarray, a: int, b: int, piece: np.ndarray, fade: int) -> np.ndarray:
    """audio[a:b] replaced by the piece, crossfaded over `fade` samples at each end."""
    n = min(fade, a, len(audio) - b, len(piece) // 2)
    body = piece.copy()
    if n:
        r = _ramp(n)
        body[:n] = audio[a:a + n] * (1 - r) + body[:n] * r
        body[-n:] = body[-n:] * (1 - r) + audio[b - n:b] * r
    return np.concatenate([audio[:a], body, audio[b:]])


def _louder(audio: np.ndarray, a: int, b: int, db: float, fade: int) -> np.ndarray:
    if not db or b <= a:
        return audio
    gain = np.full(b - a, 10 ** (db / 20), dtype=np.float32)
    n = min(fade, (b - a) // 2)
    gain[:n] = 1 + (gain[0] - 1) * _ramp(n)
    gain[b - a - n:] = 1 + (gain[0] - 1) * _ramp(n)[::-1]
    out = audio.copy()
    out[a:b] *= gain
    return out


def render(model, sentence: str, voice, speed: float, lang: str) -> np.ndarray:
    """The sentence as float audio with its marks heard. Needs a model export that reports durations."""
    return render_parts(model, sentence, voice, speed, lang)[0]


def render_parts(model, sentence: str, voice, speed: float, lang: str) -> tuple[np.ndarray, list[tuple[str, int, int]]]:
    """render(), with where each marked run ended up: [(mark, first sample, end sample)]."""
    cfg = SPEECH["marks"]
    ph, spans = phonemes(model.tokenizer, sentence, lang)
    take = lambda s: model.create_timed(ph, voice=voice, speed=min(2.0, max(0.5, s)), lang=lang, is_phonemes=True)  # noqa: E731
    audio, _, timings = take(speed)
    if not spans or len(timings) != len(model.tokenizer.known(ph)):
        return audio, []
    fade = int(cfg["fade_ms"] / 1000 * RATE)
    takes, placed = {}, []
    for kind, start, end in sorted(spans, key=lambda s: -s[1]):   # the last first, so earlier places stay put
        how = cfg[kind]
        a, b = _edge(timings, start, True), _edge(timings, end, False)
        longer, higher = how.get("longer", 1.0), how.get("higher", 0.0)
        if longer != 1.0 or higher:
            slower = longer * 2 ** (higher / 12)   # the resample takes this much back off
            if slower not in takes:
                takes[slower] = take(speed / slower)
            s_audio, _, s_timings = takes[slower]
            if len(s_timings) == len(timings):
                piece = _higher(s_audio[_edge(s_timings, start, True):_edge(s_timings, end, False)], higher)
                audio = _splice(audio, a, b, piece, fade)
                b = a + len(piece)
        audio = _louder(audio, a, b, how.get("louder_db", 0.0), fade)
        if how.get("beat_ms") and start > 1:
            at = _quietest(audio, int(timings[start - 1].start * RATE) - fade, a + fade)
            beat = int(how["beat_ms"] / 1000 * RATE)
            audio = np.concatenate([audio[:at], np.zeros(beat, audio.dtype), audio[at:]])
            a, b = a + beat, b + beat
            placed = [(k, x + beat, y + beat) for k, x, y in placed]
        placed.insert(0, (kind, a, b))
    peak = float(np.abs(audio).max() or 1.0)
    return (audio * (0.98 / peak) if peak > 0.98 else audio), placed
