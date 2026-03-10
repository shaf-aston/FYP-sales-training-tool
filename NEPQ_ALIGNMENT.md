# NEPQ Methodology Alignment — Impact Formula & Content.py

## Overview

This document verifies that the chatbot's **consultative sales flow** is built on **NEPQ (Neuro-Emotional Persuasion Questioning)**, the psychology-based sales methodology developed by **Jeremy Miner**. The `Impact formula.txt` file in this repository contains a practical implementation of NEPQ stages, and `src/chatbot/content.py` is designed to execute those stages through adaptive prompts.

---

## What is NEPQ?

**NEPQ = Neuro-Emotional Persuasion Questioning**

Core principle: *Human beings are most persuasive when they allow others to persuade themselves.*

Instead of telling prospects why they need a solution, NEPQ uses structured questions to guide prospects to **discover their own problems and articulate their own stakes**. This triggers deeper emotional engagement and higher commitment to change.

**Framework**: 7 sequential stages that build conviction → emotional investment → action

---

## Verified Free Resources

| Resource | Source | Status |
|----------|--------|--------|
| **NEPQ 101 Mini-Course** | [salesrevolution.pro](https://salesrevolution.pro) (Free sign-up) | ✅ Verified free |
| **7th Level Methodology Overview** | [7thlevelhq.com/our-methodology](https://7thlevelhq.com/our-methodology/) | ✅ Official Jeremy Miner |
| **NEPQ Creation Story** | [7thlevelhq.com/my-story-how-i-created-nepq](https://7thlevelhq.com/my-story-how-i-created-nepq) | ✅ Authoritative |
| **NEPQ 3.0 Documentation** | [7thlevelhq.com/nepq-3-0](https://7thlevelhq.com/nepq-3-0/) | ✅ Latest version |

**All resources are free to access and from the official 7th Level Communications organization founded by Jeremy Miner.**

---

## Stage Mapping: Impact Formula → Content.py

### Stage 1: INTENT (Connecting + Situation)

**Impact Formula (lines 3-12)**:
```
INTENT
Get tangible and experience
"It looks like you booked a time about possible help with {desired outcome}? How can I help?"
"What do you feel like you need help with in specific?"
→ tangible (desired outcome)
"What have you seen that makes you feel you don't have X?"
→ experience (current situation)
```

**Content.py Implementation**:

| File | Location | Implementation |
|------|----------|-----------------|
| `STRATEGY_PROMPTS["consultative"]["intent"]` | lines 122–142 | **GOOD**: Acknowledge + ask what brings them + listen for goal |
| `STRATEGY_PROMPTS["consultative"]["intent_low"]` | lines 143–164 | **Guarded variant**: Use elicitation statements (no direct Q) + soft follow-up |
| `generate_init_greeting("consultative")` | lines 400–411 | Initial greeting + training context |

**Alignment**: ✅ Content.py captures both tangible (goal) and experience (current situation) through adaptive questioning.

---

### Stage 2: LOGICAL CERTAINTY (Problem Awareness)

**Impact Formula (lines 15-33)**:
```
LOGICAL CERTAINTY
Get cause, problem, and probe

CAUSE:
"What are you doing for X that's causing {experience}?"
"How long have you been doing X?"

LIKE/DISLIKE + PROBLEM:
"Do you like it? Besides (negative), do you like {process}?"
→ If Yes: "What do you like about it?"
→ If No: "It can't be all terrible if you've been using it. What do you like about it?"
"Is there anything you would change about {process/result}?"
→ problem

IMPACT CHAIN:
"How long has that been going on for?"
"Has X had an impact on Y?"
```

**Content.py Implementation**:

| File | Location | Implementation |
|------|----------|-----------------|
| `STRATEGY_PROMPTS["consultative"]["logical"]` | lines 165–193 | **TWO-PHASE PROBE** ✅ |
| | | Phase 1 — CAUSE: Lines 172–175 |
| | | Phase 2 — LIKE/DISLIKE: Lines 177–182 |
| | | IMPACT CHAIN: Lines 183–185 |
| | | SELF-CHECK: Lines 187–191 |

**Alignment**: ✅ **Perfect match**. Content.py explicit phase structure mirrors Impact formula exactly:
- Cause questioning (what are you doing → how long)
- Like/dislike probe (establishes current approach satisfaction)
- Impact chain (connects problem to consequence)

---

### Stage 3: EMOTIONAL CERTAINTY (Solution Awareness + Consequence of Inaction)

**Impact Formula (lines 36-58)**:
```
EMOTIONAL CERTAINTY
Identity shift and future pace

IDENTITY FRAME:
"What's the rationale behind looking at a way to get more X,
rather than just doubling down on {current strategy}?"
"What's shifted now?"

FUTURE PACING (FP):
"Let's say there was a way of helping you with solving X...
what would tangibly be different for you / your business?"
"Step into those shoes for a second... what would that do for you personally?"

CONSEQUENCE OF INACTION (COI):
"What happens if you don't change? What if we continue down the current
trajectory with X for 2 weeks, 2 months, 2 years?"
"How would you feel at that point?"
```

**Content.py Implementation**:

| File | Location | Implementation |
|------|----------|-----------------|
| `STRATEGY_PROMPTS["consultative"]["emotional"]` | lines 194–227 | **THREE-PHASE STRUCTURE** ✅ |
| | | IDENTITY FRAME: Lines 201–205 |
| | | SOLUTION AWARENESS — FP: Lines 207–211 |
| | | CONSEQUENCE OF INACTION: Lines 213–217 |
| | | SELF-CHECK: Lines 222–224 |

**Alignment**: ✅ **Perfect match**. Content.py splits emotional stage into 3 phases:
1. **IDENTITY FRAME**: "Why look at change NOW?" (lines 203–205 match Impact formula lines 37–41)
2. **SOLUTION AWARENESS — FUTURE PACING**: "What would be different?" (lines 209–210 match Impact formula lines 50–52)
3. **CONSEQUENCE OF INACTION**: "What happens if you don't change?" (lines 215–216 match Impact formula lines 54–57)

---

### Stage 4: PITCH (Qualifying + Committing)

**Impact Formula (lines 59-71)**:
```
PITCH
Commitment to change, pillars, and sell themselves

"Are you willing to settle for that?"
"Why now? There's always the new year new me guy... Why actually draw that line?"
"Whose responsibility is it?"

"Based on what I've heard of {problem} and {goal},
I think what we're doing for sure could help you..."
"Would that be appropriate or what do you want to do?"

Go into 3 pillar pitch and add context to each pillar

"Based on what I've covered do you feel like this would actually get you to GOAL?"
"Total investment is $SS. How would you like to proceed?"
```

**Content.py Implementation**:

| File | Location | Implementation |
|------|----------|-----------------|
| `STRATEGY_PROMPTS["consultative"]["pitch"]` | lines 228–252 | **COMMITMENT + PILLARS** ✅ |
| | | COMMITMENT QUESTIONS: Lines 234–236 |
| | | TRANSITION: Lines 238–240 |
| | | CLOSE: Lines 242–243 |

**Alignment**: ✅ **Match**. Content.py covers:
- Commitment questions ("Are you willing to settle for [consequence]?" → Impact formula line 61)
- "Why now?" framing (line 236 → Impact formula line 62)
- 3-pillar presentation (line 239 → Impact formula line 67)
- Assumptive close (line 243 → Impact formula line 71)

---

### Stage 5: OBJECTION HANDLING

**Impact Formula**: Implicit (framework assumes some objections during pitch)

**Content.py Implementation**:

| File | Location | Implementation |
|------|----------|-----------------|
| `STRATEGY_PROMPTS["consultative"]["objection"]` | lines 253–269 | **CLASSIFY → RECALL → REFRAME → GENERATE** ✅ |

**Alignment**: ✅ Content.py follows NEPQ best practice for objections: classify type → recall stated stakes → reframe using prospect's own words → move forward.

---

## Consultative Strategy Execution Flow

```
User Message
    ↓
[analyze_state] → {intent: "high"/"low", guarded, question_fatigue}
    ↓
[generate_stage_prompt] → Selects adaptive version:
    ├─ INTENT: intent_low (guarded) OR intent (high)
    ├─ LOGICAL: Two-phase probe (cause → like/dislike → impact)
    ├─ EMOTIONAL: Identity Frame → FP → COI sequence
    ├─ PITCH: Commitment → 3 pillars → assumptive close
    └─ OBJECTION: Classify → Reframe
    ↓
[get_tactic] → Injects elicitation or lead-in based on user state
    ↓
Bot Response (with embedded stage-specific guidance)
```

---

## Transactional Strategy (Non-NEPQ)

For **transactional** sales (simple products, price-first), content.py uses a simpler framework: **NEEDS → MATCH → CLOSE**

| Stage | Framework | Goal |
|-------|-----------|------|
| `intent` | NEEDS | Gather budget + use-case (Max 2 turns) |
| `pitch` | MATCH + CLOSE | Present matching options → assumptive close |
| `objection` | CLASSIFY → REFRAME | Resolve concerns, don't dig into emotions |

This is **intentionally NOT NEPQ** — it's designed for efficiency, not emotional engagement.

---

## Key Implementation Details

### 1. Adaptive Prompt Injection (Content.py lines 630–776)

`generate_stage_prompt()` is the workhorse. It:
1. Analyzes current user state (`analyze_state` from `analysis.py`)
2. Selects base prompt (strategy + stage)
3. **Injects adaptive guidance** based on:
   - Guarded/defensive responses → elicitation tactic
   - Question fatigue → switch to statements
   - Directive user → move forward faster
   - Direct info request → override everything, provide options

**NEPQ alignment**: This adaptive injection ensures the bot doesn't rigidly follow stage prompts but instead adjusts tactics based on **prospect psychology**.

### 2. Elicitation Tactics (Content.py lines 14–81, TACTICS dict)

When a prospect is guarded (says "idk", "maybe", "not sure"), the bot uses **elicitation statements** instead of questions:

- **Presumptive**: "Probably still weighing things up."
- **Understatement**: "I imagine this probably isn't a huge priority right now."
- **Reflective**: "Still figuring things out."
- **Shared Observation**: "Most people in your position are usually dealing with X or Y."
- **Curiosity**: "I'm curious what sparked this—though no pressure."

**NEPQ alignment**: Elicitation is a **core NEPQ technique** — statements that invite correction are less confrontational than direct questions and work better with defensive prospects.

### 3. Lead-in Statements (Content.py lines 54–80, TACTICS dict)

When moving between topics or deepening exploration, the bot uses **contextual lead-ins**:

- **Summarizing**: "Okay, so the main thing is—"
- **Contextualizing**: "The reason I bring this up is—"
- **Transitioning**: "That makes sense. On a related note—"
- **Validating**: "That sounds frustrating."
- **Framing**: "This is usually the deciding factor—"

**NEPQ alignment**: These mirrors the **natural pacing** of NEPQ conversations — acknowledge, build context, move deeper.

### 4. Shared Rules (Content.py lines 439–482, _SHARED_RULES)

All strategies must follow:
- ✅ INFORMATION PRIORITY: If user asks for options, provide them immediately
- ✅ ANTI-PARROTING: Embed keywords, don't replay sentences
- ✅ QUESTION CLARITY: One question, one topic (no "or" in questions)
- ✅ NO EARLY CLOSING: Never ask "Would you like to buy?" (permission question)

**NEPQ alignment**: These enforce **conversational integrity** — the prospect should always feel like they're in control of the conversation's pace.

---

## Verification Checklist

### Consultative Flow (NEPQ-Based)

- [x] **Intent stage**: Discover tangible need + current experience
- [x] **Logical stage**: Two-phase probe (cause → like/dislike) + impact chain
- [x] **Emotional stage**: Identity frame → FP (what they want) → COI (what they fear)
- [x] **Pitch stage**: Commitment questions → 3-pillar connection → assumptive close
- [x] **Objection stage**: Classify type → recall stakes → reframe using prospect's words
- [x] **Adaptive tactics**: Elicitation for guarded users, direct answers for info requests
- [x] **Anti-validation rule**: No filler "that makes sense" (max 2 per 5 turns)
- [x] **No early pitching**: Hold product info until pitch stage (except transactional)

### Transactional Flow (Non-NEPQ)

- [x] **Intent**: Max 2 turns, get budget OR use-case
- [x] **Pitch**: MATCH options to need + assumptive close (no emotion probing)
- [x] **No elicitation machinery**: Direct, efficient, price-focused

---

## Why This Matters

1. **Psychological Foundation**: NEPQ is grounded in behavioral psychology (prospect-directed discovery = higher engagement)
2. **Stage Sequencing**: Each stage builds on the previous one (can't create FP/COI without first establishing doubt in logical stage)
3. **Adaptability**: Real prospects don't follow scripts — adaptive injection lets the bot stay in character while adjusting tactics
4. **Differentiation**: Consultative (NEPQ) vs Transactional (NEEDS→MATCH) are philosophically different and prompt-wise distinct

---

## References

### Official NEPQ Resources

1. **Jeremy Miner's 7th Level Communications**
   - Official methodology: https://7thlevelhq.com/our-methodology/
   - NEPQ origin story: https://7thlevelhq.com/my-story-how-i-created-nepq
   - Latest version (NEPQ 3.0): https://7thlevelhq.com/nepq-3-0/

2. **Free Training**
   - NEPQ 101 Mini-Course: https://salesrevolution.pro (free sign-up)
   - Includes breakdown of NEPQ stages + sample questions across industries

3. **Recommended Reading**
   - "NEPQ Black Book of Questions" (premium, 273+ expert-crafted questions)
   - YouTube: Jeremy Miner's teaching videos on 7th Level's channel

### Project Files

- **Impact formula.txt** (this repo): Practical NEPQ script with exact questions
- **src/chatbot/content.py**: Stage-specific prompts + adaptive tactics
- **src/chatbot/flow.py**: FSM that enforces stage sequencing
- **src/chatbot/analysis.py**: State detection (intent, guardedness, question fatigue)

---

## Summary

✅ **Consultative sales flow in this chatbot is a faithful implementation of NEPQ methodology.**

The `Impact formula.txt` is the blueprint, `content.py` is the execution layer, and `flow.py` ensures stage sequencing. The bot adapts tactics based on prospect psychology while maintaining methodological integrity.

**Transactional flow is intentionally different** — optimized for efficiency, not emotional depth.

Both strategies are grounded in **verified, free, open-source psychology-based sales principles**.
