"""The call read stage by stage (core/sell_mode/call_stages.py): a call that does each stage well, and one that
skips to the pitch, each read the way a coach would."""

from core.infra.loader import load_buyer_config
from core.sell_mode.call_stages import ORDER, analyse_stages, focus
from core.sell_mode.session_review import build_review

BEHAVIOUR = load_buyer_config()["difficulty_profiles"]["medium"]["behaviour"]
OPENER = "Hi, I'm Sam, small business owner. I'm looking at options, cost reduction is top of my list."

GOOD = [
    ("Thanks for making the time, Sam. Before I tell you anything about us, what made you take this call today?",
     "Honestly, mostly that admin eats my evenings. I end up doing it at nine at night."),
    ("That makes sense. What's been the hardest part of that lately?",
     "Biggest one? I'm losing customers to competitors. I've tried to fix it myself and it hasn't stuck."),
    ("How long has that been going on?", "On and off for about a year."),
    ("And what happens if nothing changes over the next year?", "I'd probably burn out, if I'm honest."),
    ("What would getting your evenings back mean for you personally?", "I'd actually see my kids before bed."),
    ("How are you handling the admin at the moment?", "Spreadsheets, mostly. It's a mess."),
    ("What's stopped you sorting this out before now?", "Time, mostly. And I tried a tool that didn't stick."),
    ("So if I've got this right, admin is eating your evenings, you're losing customers, and you want to see your kids before bed.",
     "Yeah, that's it exactly."),
    ("We take the admin off your plate so your evenings are yours again, and you get a weekly summary of your customers.",
     "That would help, to be honest."),
    ("The investment is $4,000 for the year.", "That's more than I was expecting, to be honest."),
    ("That's fair. What's making you hesitate, the amount or something else?", "The amount, mostly."),
    ("Would it make sense to book a walkthrough on Thursday so you can see it?", "Yeah, go on then."),
]
WEAK = [
    ("Hi Sam, I'll keep this quick. Our package is the best on the market.", "That's a lot. Can we slow down a bit?"),
    ("Honestly, you need to decide today. The price goes up tomorrow.", "Can we back up? I'm not there yet."),
    ("It's $4,000 for the year. That's a great deal for what you get.",
     "Okay. I'd need to think about that. I've seen similar options for less."),
    ("Look, everyone signs up. Trust me, it's worth it. Shall we get you started today?", "I'm not ready to book anything yet."),
]


def stages(pairs):
    history = [{"role": "assistant", "content": OPENER}]
    for seller, buyer in pairs:
        history += [{"role": "user", "content": seller}, {"role": "assistant", "content": buyer}]
    return {s["id"]: s for s in analyse_stages(build_review(history, BEHAVIOUR)["turns"])}


def test_a_call_that_does_each_stage_reads_strong_with_its_evidence():
    got = stages(GOOD)
    assert list(got) == list(ORDER)
    assert {sid: s["status"] for sid, s in got.items()} == {sid: "strong" for sid in ORDER}
    assert got["goals"]["turns"] == [5]                     # the identity rung: "for you personally"
    assert got["situation"]["turns"] == [6, 7]              # not turn 1: "what made you take this call today?"
    assert got["problem"]["turns"] == [2, 3, 4]             # the problem, how long, what staying put costs
    assert got["objections"]["turns"] == [11]               # acknowledged and asked, after "more than I expected"
    assert focus(list(got.values())) is None


def test_a_call_that_jumps_to_the_pitch_reads_as_a_coach_would():
    got = stages(WEAK)
    assert got["opening"]["status"] == "missed"
    assert got["solution"]["status"] == got["price"]["status"] == got["close"]["status"] == "early"
    # "I'm not there yet" got the price, "...options for less" got "trust me": pushed harder both times
    assert got["objections"]["status"] == "weak" and got["objections"]["turns"] == [3, 4]
    for sid in ("goals", "situation", "problem", "obstacle", "playback"):
        assert got[sid]["status"] == "missed", sid
    assert focus(list(got.values()))["id"] == "opening"     # the earliest gap: the rest builds on it


def test_every_stage_says_why_it_matters_and_what_to_try():
    for s in stages(WEAK).values():
        assert s["why"] and s["says"]
        assert s["next"], s["id"]                         # not strong: there is a line to try next time


def test_taking_the_first_answer_is_only_part_of_the_goal():
    got = stages([("What are you hoping to achieve this year?", "More customers, mainly."),
                  ("Great. We help with exactly that.", "Okay.")])
    assert got["goals"]["status"] == "partly"


def test_no_concern_raised_is_nothing_to_work_on():
    got = stages(GOOD[:3])
    assert got["objections"]["status"] == "none" and not got["objections"]["next"]
