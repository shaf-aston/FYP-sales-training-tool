"""Reading real transcript exports into speaker turns. Each sample copies a real tool's layout."""
import pytest

from core.calls.reader import load_calls_config
from core.calls.transcript import parse, seconds

CFG = load_calls_config()

FATHOM = """Fathom Demo - September 16
VIEW RECORDING - 8 mins (4 mins of highlights): https://fathom.video/share/abc

---

0:00 - Rita West
  All right. Hello. And welcome.
  What brings you here today?
0:26 - Sam Dale
  Hey, doing great. We need help with onboarding.
  BOOKMARK: pricing - WATCH: https://fathom.video/share/abc?t=30
1:02 - Rita West
  How long has that been a problem?
"""

ZOOM_VTT = """WEBVTT

1
00:02:35.600 --> 00:02:37.139
Norio Kobota (Sony Group Corporation): Hello! Good morning!

2
00:02:37.200 --> 00:02:39.000
Norio Kobota (Sony Group Corporation): How are you today?

3
00:02:40.000 --> 00:02:42.500
Jane Smith: Good thanks, a bit busy.
"""

ZOOM_SAVED = """[Stephen Simon] 12:56:48
Interesting, testing.

[Suman Sahil] 13:00:34
that we don't

[Stephen Simon] 13:00:40
Why not?
"""

MEET = """﻿Mar 20, 2026
Review DBX to Neo4j - Transcript
00:00:00

Sam Longley: Yeah, we're supposed to have 50 here.
Guhan Sivaji: Oh
Sam Longley: yeah.
00:01:00
Guhan Sivaji: What does that cost?
Transcription ended after 00:30:47
This editable transcript was computer generated and might contain errors.
"""

TEAMS_VTT = """WEBVTT\r
\r
1c7dab68-1f2e-4a3b-9c8d-0e1f2a3b4c5d/17-1\r
00:00:06.000 --> 00:00:07.000\r
<v Mauch, Lukas>Not really.</v>\r
\r
1c7dab68-1f2e-4a3b-9c8d-0e1f2a3b4c5d/16-0\r
00:00:04.021 --> 00:00:04.901\r
<v &#193;lvaro Ruiz>What does it\r
output?</v>\r
"""

TEAMS_DOCX = """Transcript
April 17, 2025, 4:29PM
Sydney Smith (She/Her) started transcription
Sarah Hakim   0:59
Alright, it is time to start.
So welcome everyone.
Sydney Smith (She/Her)   1:10
Thanks Sarah.
"""

OTTER = """Unknown Speaker  0:00
You guys ready?

Speaker 2  0:05
Yes, go ahead.

Transcribed by https://otter.ai
"""

GONG = """Transcript
 0:00 | David McGeary
Hey Justin, thanks for joining today.
 0:12 | Justin Lee
Happy to be here.
"""

SRT = """1
00:00:05,790 --> 00:00:13,514
John: So what are you using now?

2
00:00:14,000 --> 00:00:16,000
Mary: A spreadsheet,
honestly.
"""

MARKDOWN = """## Transcript
**Ann:** Hi there, how can I help?
**Bob:** Just browsing for now.
**Ann:** What are you looking for?
**Bob:** Something for the team.
"""


@pytest.mark.parametrize("text, fmt, first, speakers", [
    (FATHOM, "speaker_blocks", ("Rita West", "All right. Hello. And welcome. What brings you here today?", "0:00"), 2),
    (ZOOM_VTT, "vtt", ("Norio Kobota", "Hello! Good morning! How are you today?", "00:02:35.600"), 2),
    (ZOOM_SAVED, "speaker_blocks", ("Stephen Simon", "Interesting, testing.", "12:56:48"), 2),
    (MEET, "speaker_lines", ("Sam Longley", "Yeah, we're supposed to have 50 here.", "00:00:00"), 2),
    (TEAMS_VTT, "vtt", ("Álvaro Ruiz", "What does it output?", "00:00:04.021"), 2),
    (TEAMS_DOCX, "speaker_blocks", ("Sarah Hakim", "Alright, it is time to start. So welcome everyone.", "0:59"), 2),
    (OTTER, "speaker_blocks", ("Unknown Speaker", "You guys ready?", "0:00"), 2),
    (GONG, "speaker_blocks", ("David McGeary", "Hey Justin, thanks for joining today.", "0:00"), 2),
    (SRT, "srt", ("John", "So what are you using now?", "00:00:05,790"), 2),
    (MARKDOWN, "speaker_lines", ("Ann", "Hi there, how can I help?", None), 2),
])
def test_each_export_layout_reads_into_turns(text, fmt, first, speakers):
    found, turns = parse(text, CFG)
    assert found == fmt
    assert (turns[0].speaker, turns[0].text, turns[0].at) == first
    assert len({t.speaker for t in turns}) == speakers


def test_junk_lines_never_become_speech():
    _, turns = parse(FATHOM, CFG)
    said = " ".join(t.text for t in turns)
    assert "BOOKMARK" not in said and "fathom.video" not in said
    _, turns = parse(MEET, CFG)
    assert "Transcription ended" not in " ".join(t.text for t in turns)


def test_one_speakers_lines_and_cues_become_one_turn():
    _, turns = parse(MEET, CFG)
    # "Oh" / "yeah." are separate speakers' lines, so nothing merges across them...
    assert [t.speaker for t in turns] == ["Sam Longley", "Guhan Sivaji", "Sam Longley", "Guhan Sivaji"]
    # ...but the minute mark is no one's words; it times the next line.
    assert turns[-1].text == "What does that cost?" and turns[-1].at == "00:01:00"


def test_out_of_order_teams_cues_are_put_back_in_time_order():
    _, turns = parse(TEAMS_VTT, CFG)
    assert [t.speaker for t in turns] == ["Álvaro Ruiz", "Mauch, Lukas"]


def test_a_colon_in_ordinary_prose_is_not_a_speaker():
    prose = "Notes from today\nThe plan: ship on Friday.\nWe talked about pricing and the trial.\nNext step: send the deck."
    assert parse(prose, CFG) is None


@pytest.mark.parametrize("at, expected", [("0:05", 5), ("1:02:03.5", 3723.5), ("00:00:05,790", 5.79), (None, 0)])
def test_times_turn_into_seconds(at, expected):
    assert round(seconds(at), 3) == expected
