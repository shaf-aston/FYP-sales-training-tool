"""The script's stress marks, heard (core/infra/providers/voice_marks.py): found, stressed in the phonemes, and
carried out on the audio of the marked words only."""

import numpy as np
import pytest
from kokoro_onnx.sliding import Timing
from kokoro_onnx.tokenizer import Tokenizer

from core.infra.providers import voice_marks as vm

RATE = vm.RATE


def test_a_line_splits_into_plain_and_marked_runs():
    assert vm.runs("It's about ==them==.") == [vm.Run("It's about "), vm.Run("them", "key"), vm.Run(".")]
    assert [r.mark for r in vm.runs("Where are you **now**... that you _don't_ want?")] == ["", "loud", "", "stretch", ""]
    assert vm.runs("the belief_cost slot") == [vm.Run("the belief_cost slot")]   # never a stretch inside a word
    assert not vm.marked("Plain words.") and vm.marked("It's _all_ on you.")


def test_the_words_alone_lose_every_mark_even_a_stray_one():
    assert vm.plain("Where are you **now**... that you _don't_ want?") == "Where are you now... that you don't want?"
    assert vm.plain("about ==being there for") == "about being there for"   # a key mark split across two sentences
    assert vm.plain("the belief_cost slot") == "the belief_cost slot"


def test_a_marked_word_gets_a_full_stress():
    assert vm.full_stress("ðˌɛm") == "ðˈɛm" and vm.full_stress("nˈaʊ") == "nˈaʊ" and vm.full_stress("ðæt") == "ðˈæt"


@pytest.fixture(scope="module")
def tokenizer():
    return Tokenizer()


def test_the_marked_words_are_found_in_the_lines_phonemes(tokenizer):
    ph, spans = vm.phonemes(tokenizer, "What is it about where you are **now**...", "en-us")
    (kind, a, b), = spans
    assert kind == "loud" and ph[a:b] == "nˈaʊ" and ph.endswith("nˈaʊ...")   # the dots stay outside the word
    ph, spans = vm.phonemes(tokenizer, "So it's really about ==being there== for them.", "en-us")
    assert spans[0][0] == "key" and ph[spans[0][1]:spans[0][2]].split() == ["bˈiːɪŋ", "ðˈɛɹ"]
    ph, spans = vm.phonemes(tokenizer, "It's about ==them==.", "en-us")
    assert ph[spans[0][1]:spans[0][2]] == "ðˈɛm" and ph.endswith("ðˈɛm.")   # stressed, though "them" alone isn't
    ph, spans = vm.phonemes(tokenizer, "It's 4,000 for ==the whole year==.", "en-us")
    assert "ðə hˈoʊl" in ph[spans[0][1]:spans[0][2]]   # in a run of words, "the" stays light


class FakeModel:
    """Each phoneme 40 ms of a steady tone at a set speed; slower takes are longer, as the model's are."""

    def __init__(self):
        self.tokenizer = Tokenizer()
        self.speeds = []

    def create_timed(self, ph, voice, speed, lang, is_phonemes):
        self.speeds.append(speed)
        known, step = self.tokenizer.known(ph), int(0.04 * RATE / speed)
        audio = np.concatenate([np.zeros(step, np.float32) if p == " " else
                                (0.2 * np.sin(np.arange(step) * 2 * np.pi * 150 / RATE)).astype(np.float32)
                                for p in known])
        timings = [Timing(p, i * step / RATE, (i + 1) * step / RATE) for i, p in enumerate(known)]
        return audio, RATE, timings


def _rms(x):
    return float(np.sqrt((x ** 2).mean()))


def test_a_loud_word_is_louder_and_the_rest_is_untouched():
    model = FakeModel()
    plain, _, _ = model.create_timed(vm.phonemes(model.tokenizer, "So **now** we start.", "en-us")[0], "v", 1.0, "", True)
    audio, ((kind, a, b),) = vm.render_parts(model, "So **now** we start.", "v", 1.0, "en-us")
    assert kind == "loud" and b - a > 0
    assert _rms(audio[a:b]) > 1.3 * _rms(plain[a:b])            # +4 dB, give or take the crossfades
    assert np.allclose(audio[b + 2000:], plain[-(len(audio) - b - 2000):], atol=1e-4)   # what follows: as made


def test_a_stretched_word_takes_longer_and_a_key_word_waits_a_beat():
    model = FakeModel()
    _, _, timings = model.create_timed(vm.phonemes(model.tokenizer, "that you don't want it", "en-us")[0], "v", 1.0, "", True)
    audio, ((_, a, b),) = vm.render_parts(model, "that you _don't_ want it", "v", 1.0, "en-us")
    word = sum(t.end - t.start for t in timings[8:14]) * RATE   # "dˈoʊnt", from "ðæt juː "
    assert b - a > 1.3 * word
    plain_len = len(model.create_timed(vm.phonemes(model.tokenizer, "It's about them.", "en-us")[0], "v", 1, "", True)[0])
    audio, ((kind, a, _),) = vm.render_parts(model, "It's about ==them==.", "v", 1.0, "en-us")
    assert kind == "key" and len(audio) > plain_len + 0.12 * RATE   # the beat, and the slower word
    assert min(model.speeds) >= 0.5                                  # never past what the model takes


def test_a_line_without_marks_is_one_take():
    model = FakeModel()
    audio, placed = vm.render_parts(model, "Nothing marked here.", "v", 1.0, "en-us")
    assert placed == [] and len(model.speeds) == 1
