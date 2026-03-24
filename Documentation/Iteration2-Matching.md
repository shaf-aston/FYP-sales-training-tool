# Iteration 2 — First-Principles Fuzzy Matching

## Overview
The second iteration replaced the local LLM with a deterministic, rule-based approach to conversation flow. Rather than using a dialogue management framework (Dialogflow, Rasa), the system was built from first principles using fuzzy string matching to classify user input and select scripted responses.

## Duration
**Late November 2025 – 19 January 2026** (~7–8 weeks)

### Timeline Context (Git Verified)
| Period | Description |
|--------|-------------|
| 2025-11-22 | Iteration 1 ends (commit `a843434`: "Clean repository") |
| Nov–Jan | **Local prototyping period** — rule-based approach developed offline |
| 2026-01-20 | Iteration 2 ends → Current system begins (commit `9e48fad`: "working simple llm with grok api") |

*Note: No commits between Nov 22 and Jan 20 as fuzzy-matching prototype was developed locally before the pivot to LLM API approach. This "gap" represents the experimental period where rule-based matching was tested and ultimately rejected.*

## Approach
User utterances were matched against a set of predefined intent patterns using fuzzy string similarity (e.g. token-ratio matching via a library such as `rapidfuzz` / `fuzzywuzzy`). Based on the closest match, the system selected a scripted response and advanced through the IMPACT formula stages deterministically. No LLM was involved in response generation.

## Motivation (Problems Addressed from Iteration 1)
- Eliminate multi-minute LLM inference latency
- Enforce strict adherence to the IMPACT formula stage sequence
- Remove dependency on a local model that could not reliably follow prompt constraints
- Gain full, auditable control over conversation flow without a third-party dialogue platform

## Latency
Near-instantaneous. Pattern matching and response selection were fast enough for real-time conversation.

## Observed Failures

### 1. Rigidity of Responses
Scripted responses could not adapt language to the user's specific phrasing, context, or product domain. Every matched intent produced the same fixed reply, making repeated conversations feel mechanical and predictable.

### 2. High Manual Maintenance Cost
Each new intent, stage variation, or edge case required separately hand-coding response branches. The approach scaled poorly — adding coverage for one strategy required substantial duplicated effort.

### 3. No Support for Multiple Strategies
The architecture could not flexibly accommodate different sales strategies (e.g. consultative vs. transactional) without a near-complete rewrite of the matching and routing logic.

### 4. Lack of Humanisation
Responses lacked natural variation in language. While the stage-progression logic was sound, the output was noticeably robotic — unsuitable for a training tool where realistic human-like dialogue is a core requirement.

## What Worked
- Stage-sequencing and process adherence to the IMPACT formula were reliable
- Response latency was not a bottleneck
- Deterministic control over conversation flow was fully achieved

## Conclusion
Iteration 2 demonstrated that deterministic stage control was achievable and valuable, but scripted responses were insufficient for a realistic training experience. The final architecture (current system) retained the deterministic FSM for stage management from this iteration while restoring LLM generation — now via a cloud provider (Groq) — for natural language output within each stage.

---

## Transition to Current System (20 January 2026)

### The Pivot Decision
After validating that deterministic stage control worked but scripted responses failed, the decision was made to combine:
1. **FSM from Iteration 2** — deterministic stage progression, auditable transitions
2. **LLM from cloud API** — natural language generation without local hardware constraints

### Key Commit
- **Commit:** `9e48fad` (20 January 2026)
- **Message:** "working simple llm with grok api"
- **Significance:** First working integration of cloud LLM API with FSM control

### Radical Simplification (Git-Verified)

The pivot commit shows a dramatic reduction in complexity:

| Metric | Iteration 1 | Current System (commit `9e48fad`) |
|--------|-------------|-----------------------------------|
| **Python files** | 40+ | **3** (`app.py`, `chatbot.py`, `test_groq_model.py`) |
| **Total files** | 470+ | ~50 |
| **Lines deleted** | — | 63,776 |
| **Dependencies** | transformers, torch, LangChain, SQLite | Flask, groq |

### New Architecture (From `chatbot.py`, commit `9e48fad`)

```python
class SalesChatbot:
    def __init__(self, api_key=None, model_name=None):
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.3-70b-versatile"
        self.history = []
        self.stage = "intent"  # Simple stage tracking

    def get_stage_prompt(self):
        """Returns the system prompt for current stage based on IMPACT framework"""
        stage_instructions = {
            "intent": "Figure out what they actually want...",
            "logical": "Understand what they're currently doing...",
            "emotional": "Create urgency by exploring consequences...",
            "pitch": "Get commitment to move forward..."
        }
        return base + stage_instructions[self.stage]
```

**Key insight:** The 470-file codebase with 5 analyzer services, training pipelines, and React frontend was replaced by a single `SalesChatbot` class (~120 lines) that:
- Uses Groq API for inference (sub-second latency)
- Tracks stage with a simple string (`self.stage = "intent"`)
- Defines stage behaviour in a dictionary (auditable, editable)

### What Changed from Iteration 1
| Aspect | Iteration 1 (Local LLM) | Current System (Cloud LLM) |
|--------|-------------------------|----------------------------|
| Model | Qwen2.5 (1.5B local) | Llama 3.3 70B (Groq cloud) |
| Latency | 3–5 minutes | <1 second |
| Stage control | LLM-inferred | FSM-enforced (from Iteration 2) |
| Cost | Hardware only | API usage (~$0 free tier) |
| Scalability | Single machine | Cloud-native |
| Codebase size | 470+ files | 3 files |

### What Carried Forward from Iteration 2
- Deterministic FSM stage transitions
- Explicit advancement signals (keyword-based, not turn-count)
- First-principles control philosophy (no Dialogflow/Rasa dependency)
- Stage-specific behaviour isolation

