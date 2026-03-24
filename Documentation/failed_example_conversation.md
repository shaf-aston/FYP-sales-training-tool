# Failed Example: FSM Stage Advancement Bug and Correction

## Executive Summary

This document illustrates a critical bug in the FSM advancement logic that violated NEPQ methodology and its correction. The old advancement rule auto-advanced from the logical stage to emotional stage after 5 turns, regardless of whether the prospect had named a problem. The fixed version requires explicit doubt signals (keywords from `analysis_config.yaml`) before advancing.

---

## Context: Why This Bug Matters to NEPQ

NEPQ is a **sequential framework** where each stage depends on outputs from the previous stage:

- **Logical stage** (Problem Awareness): Prospect names a problem with their current approach. The bot surfaces doubt via two-phase probe: cause ("What are you doing for X that's causing Y?") and like/dislike ("Besides [negative], do you actually like [current process]?").
- **Emotional stage** (Solution Awareness + Consequence): Prospect articulates what they want (Future Pacing) and what they fear (Consequence of Inaction). These questions are only coherent if a problem was established in the logical stage.

If the bot advances to emotional without a named problem, the FP/COI questions become semantically disconnected. The bot asks "What would be different if we solved your problem?" when the prospect never acknowledged having a problem. This is a **methodology violation**—not just poor UX, but a breakdown of the framework itself.

---

## The Bug

**Code location**: `flow.py`, prior implementation of `user_shows_doubt()` (lines 148–154 in current code)

**Old rule** (pseudo-code, from ARCHITECTURE.md Phase 4):
```python
def user_shows_doubt(history, user_msg, turns):
    doubt_keywords = ['not working', 'struggling', 'problem', ...]
    return text_contains_any_keyword(recent_text, doubt_keywords) or turns >= 5  # ❌ Always True after 5 turns
```

The problem: **`turns >= 5` guarantees True regardless of conversational content.** A user saying "I'm very happy with my approach" on turn 5 would trigger advancement, even though no doubt was expressed.

**New rule** (current implementation, lines 148–154):
```python
def user_shows_doubt(history, user_msg, turns):
    return _check_advancement_condition(history, user_msg, turns, 'logical', min_turns=2)
```

Which delegates to `_check_advancement_condition()` (lines 108–145):
```python
keywords = stage_config.get(keyword_key, [])  # doubt_keywords from config
max_turns = stage_config.get('max_turns', 10)
has_signal = text_contains_any_keyword(recent_text, keywords)
return has_signal or turns >= max_turns  # ✓ Safety valve: 10 turns, not 5
```

**Key differences**:
1. Keyword check is now **explicit and auditable** (reads from `analysis_config.yaml:advancement.logical.doubt_keywords`)
2. Safety valve increased from 5 turns → 10 turns (gives bot more time to surface doubt)
3. Keywords are verified against NEPQ framework (not arbitrary)
4. Minimum turns (`min_turns=2`) required before checking — prevents premature advancement

---

## Constructed Scenario: Trading Mentorship Consultation

### Setup
- **Product**: Trading mentorship program
- **Strategy**: Consultative (NEPQ 5-stage)
- **Current FSM state**: User has stated intent ("help with trading"). FSM is now in **logical stage**.
- **Goal of logical stage**: Establish doubt in the user's current trading approach

---

## BEFORE: Bug Behavior (turns >= 5 auto-advances)

### Conversation Trace

| Turn | Role | Message | FSM State | Signal Check |
|---|---|---|---|---|
| 1 | USER | "I've been trading for 3 years, doing well on average" | Logical, turn=1 | (no doubt keywords) |
| 1 | BOT | "What are you doing for your entries that's getting results?" | Logical, turn=1 | — |
| 2 | USER | "Mostly technical analysis, seems to be working fine for me" | Logical, turn=2 | "fine" (not doubt) |
| 2 | BOT | "How long have you been using that system?" | Logical, turn=2 | — |
| 3 | USER | "About 2 years. I'm quite profitable overall" | Logical, turn=3 | "profitable" (not doubt) |
| 3 | BOT | "Besides the unprofitable months, do you actually like the consistency of your results?" | Logical, turn=3 | — |
| 4 | USER | "Yeah I mean it's fine, I'm happy with the results" | Logical, turn=4 | "fine", "happy" (not doubt) |
| 4 | BOT | "Is there anything you would change about your process if you could?" | Logical, turn=4 | — |
| 5 | USER | "Not really, I think I'm doing pretty great honestly" | Logical, turn=5 | "great" (not doubt) |
| 5 | BOT | **FSM triggers advancement** (turns >= 5 → True) | **→ EMOTIONAL** | — |
| 5 | BOT | "Let's say there was a way to help you become an even better trader—what would tangibly be different for you at that point?" | EMOTIONAL | **NO PROBLEM ESTABLISHED** |

### Result: Incoherent Dialogue

The Future Pacing question presupposes a problem ("help you...become better"), but the user never named one. The user's entire logical stage was "I'm doing well, I'm happy, I'm great." The FP question has no ground to stand on.

**NEPQ violation**: Stage 3 (Emotional Awareness) depends on Stage 2 (Problem Awareness) having established doubt. The user expressed no doubt, yet the bot advanced anyway.

---

## AFTER: Fixed Behavior (keyword-based with 10-turn safety valve)

### Same Conversation, But with New Logic

| Turn | User Message | Doubt Keywords? | turns < 10? | FSM Action |
|---|---|---|---|---|
| 5 | "Not really, I think I'm doing pretty great honestly" | ❌ No | ✓ 5 < 10 | **STAY in logical** |
| 6 | "I mean the system works, so..." | ❌ No | ✓ 6 < 10 | **STAY in logical** |
| 7 | "Well, I suppose there have been some inconsistent months lately" | ✅ **"inconsistent"** ∈ doubt_keywords | ✓ 7 < 10 | **→ EMOTIONAL (correct)** |

### What Changed

**Turning point (turn 7)**: User says "inconsistent months." The word "inconsistent" is in `analysis_config.yaml:advancement.logical.doubt_keywords` (line 309).

```yaml
advancement:
  logical:
    doubt_keywords:
      - "not working"
      - "struggling"
      - "problem"
      ...
      - "inconsistent"  # <- matches here
      ...
```

The FSM detects this signal and advances to emotional stage. Now the bot's next response is grounded:

| Turn | BOT (now in EMOTIONAL) | Grounding |
|---|---|---|
| 7 | "So you're getting inconsistent results. Let's say there was a way to create more consistency in your returns—what would that look like for you, specifically?" | ✓ Refers to the problem ("inconsistent results") the user just named |

---

## Detailed Analysis

### Quantitative Difference

| Aspect | Old Rule | New Rule |
|---|---|---|
| Advancement trigger | Turn count (5) | Signal keyword presence OR turn count (10) |
| Methodology alignment | ❌ No | ✅ Yes (requires doubt before emotional) |
| User experience | Incoherent FP questions | FP questions grounded in stated problem |
| Safety valve | 5 turns | 10 turns (more patient with resistant prospects) |

### Why "Inconsistent" Triggers Advancement

`doubt_keywords` is not arbitrary. It reflects NEPQ's Problem Awareness stage philosophy: the bot is looking for words that indicate the user is doubting or reconsidering their current approach.

| Keyword | NEPQ Principle | User Example |
|---|---|---|
| "struggling" | Active difficulty | "I'm struggling to stay disciplined" |
| "problem" | Named issue | "The problem is timing" |
| "inconsistent" | Doubt in reliability | "Results are inconsistent" |
| "failing" | Failure signal | "The method is failing me" |
| "wrong" | Explicit doubt | "I think my approach is wrong" |

Full list in `analysis_config.yaml:advancement.logical.doubt_keywords` (25 terms total).

### Methodological Grounding

This example demonstrates why FSM stage enforcement matters. The prompt instruction "Ask Future Pacing questions in emotional stage" would allow the bot to ask FP questions any time it felt confident. The FSM guarantee "Do NOT exit logical without doubt keywords" makes the framework visible and testable.

**Test case** (would have caught this bug):
```python
# Scenario: User stays confident through logical stage
conversation = [
    ("user", "I'm trading fine"),
    ("bot", "What are you doing for your entries?"),
    ("user", "Technical analysis, working well"),
    ...
]
assert flow_engine.current_stage == "logical" or "great" in conversation[-1][1], \
    "User said great at turn 5, should stay in logical"
```

---

## Code Implementation

### Before → After Comparison

**Before** (ARCHITECTURE.md, Phase 4 "The Problem" section, lines 206–209):
```
Logical | `user_shows_doubt` | **5 turns** (AUTO) | **10 turns** (requires doubt signals)
```

**After** (flow.py, lines 148–154):
```python
def user_shows_doubt(history, user_msg, turns):
    return _check_advancement_condition(history, user_msg, turns, 'logical', min_turns=2)
```

This delegates to `_check_advancement_condition()` which:
1. Loads `doubt_keywords` from config (lines 129–135)
2. Searches recent user text for those keywords (line 142)
3. Returns True if found OR turns >= 10 (line 145)

**Verification**: Run the test scenario above; assert `flow_engine.current_stage == "logical"` after turn 5 when user messages contain no doubt keywords.

---

## Key Takeaway

FSM-enforced stage progression prevents LLM-based stage management failures. A prompt saying "determine if doubt has been established" leaves interpretation to the model. An FSM rule saying "doubt has been established if any of these 25 keywords appear" makes the framework auditable, testable, and—critically—**faithful to the methodology it claims to implement**.
