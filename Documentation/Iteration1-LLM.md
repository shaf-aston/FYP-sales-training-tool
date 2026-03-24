# Iteration 1 — Local LLM (Qwen2.5)

## Overview
The first iteration ran a local Qwen2.5 model on the development machine for all response generation. The chatbot attempted to follow the IMPACT sales methodology, supplemented by external sales datasets. The model was upgraded mid-iteration from 0.5B to 1.5B parameters after severe quality failures, but neither resolved the core latency problem.

## Duration
**28 September 2025 – 22 November 2025** (~8 weeks)

### Key Git Commits (Verified)
| Date | Commit | Description |
|------|--------|-------------|
| 2025-09-28 | `5afe843` | Project start — "really basic starter ai responses" |
| 2025-09-30 | `aaf8498` | "ai conversing, but not being direct" — directness issues noted |
| 2025-10-02 | `48fb0c1` | "slow speed, gonna be optimized" — latency issues documented |
| 2025-10-27 | `6391f53` | "Ui and structuring; initial implementation" |
| 2025-10-30 | `f4a5d60` | "Frontend ui made, and **bad conversational ai** is current" — quality crisis |
| 2025-11-05 | `d7eafec` | "some ai model, ready for training, frontend completed" — model upgrade attempt |
| 2025-11-22 | `a843434` | "Clean repository" — iteration end, **100+ files deleted** |

## Codebase Complexity (Git-Verified)

The Iteration 1 codebase grew to **470+ files** with multiple interdependent services:

| Module | Purpose | Lines |
|--------|---------|-------|
| `FeedbackAnalyticsService` | Orchestrated 5 analyzer submodules | ~100 |
| `ConversationAnalyzer` | Basic conversation metrics | dedicated file |
| `CommunicationAnalyzer` | Communication style analysis | dedicated file |
| `SalesProcessAnalyzer` | Methodology adherence | dedicated file |
| `EmotionalIntelligenceAnalyzer` | EQ and rapport scoring | dedicated file |
| `FeedbackGenerator` | Feedback compilation | dedicated file |
| `ChatService` | Session management, caching, LangChain integration | ~100 |
| `ModelService` | Model loading with quantization attempts | ~80 |

**Additional infrastructure:**
- React frontend (`frontend/src/`)
- SQLite databases (`sessions.db`, `quality_metrics.db`)
- Training pipeline (`training/` with 8+ training scripts)
- Voice services (`stt_service.py`, `tts_service.py`)
- LangChain integration (`langchain_conversation_service.py`)

## Hardware
- Development machine: Lenovo ThinkPad (Intel i7-8550U, 11 GB RAM total; ~3 GB available at runtime — Windows and VS Code consuming ~8 GB)
- Model stage 1: Qwen2.5-0.5B (~1 GB RAM; smallest available instruct model, chosen for minimal footprint)
- Model stage 2: Qwen2.5-1.5B (~3 GB RAM; upgraded mid-iteration after 0.5B quality failures — ~3x reduction in issues, but latency remained unacceptable)

## Model Configuration (From `config/model_config.py`, commit `d7eafec`)

```python
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

GENERATION_CONFIG = {
    "base_model": {
        "max_new_tokens": 200,      # Token limit to reduce latency
        "do_sample": True,          # Sampling for variety
        "temperature": 0.85,        # High = creative but unpredictable
        "repetition_penalty": 1.15  # Tried to prevent loops
    }
}
```

**Problem:** `max_new_tokens: 200` truncated responses mid-sentence. Setting it higher restored coherence but returned 3–5 minute latency.

## Fallback System (Evidence of AI Failures)

The codebase included a hardcoded fallback array (`fallback_responses.py`), proving the AI failed frequently enough to require static backups:

```python
FALLBACK_RESPONSES = [
    "I'm hoping you can help me figure out the best approach...",
    "Sorry, I got distracted for a moment. Could you ask me that again?",
    "I'd really like to understand what would work best for someone like me."
]
```

This fallback system was called when `generate_ai_response()` returned empty or failed.

## Inference Latency
- 3–5 minutes per response (Qwen2.5-1.5B on available hardware)
- Root cause: memory bandwidth bottleneck (i7-8550U dual-channel LPDDR3 at ~38 GB/s) + continuous page-file swapping with only ~3 GB free RAM + thermal throttling from 2.7 GHz to 1.4–1.8 GHz after ~90 seconds of sustained load
- Latency was a primary usability blocker; made real-time conversation practice infeasible

## Observed Failures

### 1. Response Truncation
Output token limits were applied to reduce inference time — this caused responses to cut off mid-sentence or mid-argument before completing a stage objective. Removing the limit restored coherence but returned full latency. No viable middle ground was found.

### 2. Verbose / Unfocused Output ("Waffle")
Model produced excessively long responses that lost conversational focus. Rather than advancing the IMPACT stage, output often restated context or repeated previous points without progression.

### 3. Markdown Artefacts in Output
Despite explicit prompt instructions prohibiting markdown formatting, the model injected heading symbols (`####`), emphasis markers (`*****`), and role labels (`Salesperson:`) into conversational responses. This required an additional post-processing layer to strip artefacts before presenting output to the user.

### 4. Role Confusion
The model intermittently generated salesperson responses instead of maintaining the customer/prospect persona. Conversation structure would invert — the bot would offer solutions rather than express needs or objections — breaking the training scenario entirely.

### 5. Prompt Non-Adherence
Prompt-level constraints were inconsistently followed. Behavioural instructions (tone, stage adherence, format) did not reliably propagate to output, even with repeated reinforcement in the system prompt.

### 6. Dataset Integration Issues
External sales datasets added noise. Some dataset phrasings conflicted with the methodology prompts, producing inconsistent persona behaviour regardless of model parameters.

## Cleanup Commit Analysis (`a843434`, 22 Nov 2025)

The iteration-ending cleanup removed:
- **100+ large video files** (training materials)
- **Databases** (`sessions.db`, `quality_metrics.db`)
- **Training scripts** and roleplay transcripts
- **NEPQ Black Book PDF** (33 MB)
- Multiple API and architecture documentation files

**Commit message:** "Clean repository - remove all external data and large files"

This cleanup confirms the approach was abandoned, not evolved.

## Conclusion
The combination of multi-minute latency, role confusion, unreliable prompt adherence, and the need for post-processing to correct output artefacts made this approach unviable for interactive training. Following supervisor feedback, the approach was revised toward a first-principles rule-based technique to regain control over conversation flow — the basis of Iteration 2.
