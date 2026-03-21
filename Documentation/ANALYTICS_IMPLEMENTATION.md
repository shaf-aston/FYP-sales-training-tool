# Analytics & A/B Testing Implementation — FYP Evaluation Support

## Overview

Two complementary systems have been implemented to strengthen the FYP evaluation chapter with empirical evidence:

1. **Session Analytics** (`session_analytics.py`) — Conversation-level metrics tracking
2. **A/B Variant Selection** (`loader.py` enhancement) — Controlled prompt experimentation infrastructure

Both systems are non-intrusive (integrated with minimal code changes) and gracefully degrade if not used.

---

## 1. Session Analytics Module

### Purpose
Captures conversation-level events that directly support quantitative claims in the evaluation chapter:
- "X% of sessions reached the pitch stage"
- "Intent classification distributed as: high Y%, medium Z%, low W%"
- "Most common objection type: money (N occurrences)"
- "Strategy switched in M% of sessions"

### Location
`src/chatbot/session_analytics.py` (new file, ~250 lines)

### Architecture

**Storage**: `analytics.jsonl` (project root)
- Append-only event log (one JSON object per line)
- Auto-rotation: 10,000 line max → keeps newest 5,000
- Thread-safe file operations (lock-based)

**Event Types**:

| Event | Recorded When | Fields |
|-------|---|---|
| `session_start` | Bot session created | session_id, product_type, initial_strategy, ab_variant |
| `stage_transition` | FSM advances to new stage | from_stage, to_stage, strategy, user_turns_in_stage |
| `intent_classification` | Each user turn | intent_level (low/medium/high), user_turn |
| `objection_classified` | At OBJECTION stage | objection_type (money/fear/partner/etc), strategy, user_turn |
| `strategy_switch` | Strategy changes mid-conversation | from_strategy, to_strategy, reason, user_turn |
| `session_end` | Session closes | final_stage, final_strategy, user_turn_count, bot_turn_count |

### Key APIs

```python
# Recording events (called internally)
SessionAnalytics.record_session_start(session_id, product_type, initial_strategy, ab_variant)
SessionAnalytics.record_stage_transition(session_id, from_stage, to_stage, strategy, user_turns_in_stage)
SessionAnalytics.record_intent_classification(session_id, intent_level, user_turn_count)
SessionAnalytics.record_objection_classified(session_id, objection_type, strategy, user_turn_count)
SessionAnalytics.record_strategy_switch(session_id, from_strategy, to_strategy, reason, user_turn_count)
SessionAnalytics.record_session_end(session_id, final_stage, final_strategy, user_turn_count, bot_turn_count)

# Retrieval (for evaluation analysis)
events = SessionAnalytics.get_session_analytics(session_id)  # Per-session event log
summary = SessionAnalytics.get_evaluation_summary()  # Aggregated stats
```

### Integration Points

1. **`chatbot.py:__init__`** — Records session start with A/B variant
2. **`chatbot.py:chat()`** — Records intent classification on each turn
3. **`chatbot.py:chat()`** — Records objection classification at OBJECTION stage
4. **`chatbot.py:_apply_advancement()`** — Records stage transitions and strategy switches
5. **Application layer** — Can call `record_session_end()` on session closure

### Evaluation Summary Output

`GET /api/analytics/summary` returns:

```json
{
  "total_sessions": 150,
  "stage_reach": {
    "intent": 150,
    "logical": 95,
    "emotional": 78,
    "pitch": 65,
    "objection": 45
  },
  "intent_distribution": {
    "low": 25,
    "medium": 89,
    "high": 36
  },
  "objection_types": {
    "money": 12,
    "fear": 8,
    "partner": 5,
    "smokescreen": 15,
    "unknown": 5
  },
  "initial_strategy": {
    "intent": 150,
    "consultative": 0,
    "transactional": 0
  },
  "strategy_switches": 145,
  "ab_variants": {
    "variant_a": 73,
    "variant_b": 77
  },
  "sessions_reached_pitch": 65,
  "sessions_reached_objection": 45
}
```

---

## 2. A/B Variant Selection System

### Purpose
Enables controlled prompt experiments for academic evaluation:
- Compare NEPQ-aligned prompts (treatment) vs generic prompts (control)
- Deterministic assignment: same session always gets same variant
- Foundation for publishable contribution: "NEPQ methodology improved pitch reach by X%"

### Location
- Main: `loader.py` (new functions `assign_ab_variant()`, `get_variant_prompt()`)
- Config: `src/config/variants.yaml` (new file, template provided)

### Deterministic Assignment

```python
def assign_ab_variant(session_id) -> str:
    """
    Hash-based determinism: MD5(session_id) % 2 → {0: 'variant_a', 1: 'variant_b'}

    - Same session_id always produces same variant (reproducible)
    - Random distribution across new sessions (50/50 expected)
    - No state storage (stateless, scalable)
    """
```

**Example**:
```python
assign_ab_variant("user_alice_session_1")   # → "variant_a" (always)
assign_ab_variant("user_bob_session_1")     # → "variant_b" (always)
assign_ab_variant("user_alice_session_2")   # → "variant_b" (always)
```

### Variant Retrieval

```python
def get_variant_prompt(base_prompt, variant_type, strategy=None) -> str:
    """
    Looks up variant in variants.yaml.
    Falls back to base_prompt if:
    - variants.yaml doesn't exist (graceful degradation)
    - variant_type not found in config
    - No prompt templates defined

    Usage:
        variant_b_intent_prompt = get_variant_prompt(
            base_prompt=INTENT_PROMPT_BASE,
            variant_type="variant_b",
            strategy="consultative"
        )
    """
```

### Configuration Template

File: `src/config/variants.yaml`

```yaml
variant_a:
  description: "Control — generic sales prompts"
  prompts:
    intent: "..."
    logical: "..."
    emotional: "..."

variant_b:
  description: "Treatment — NEPQ-aligned prompts"
  prompts:
    intent: "..."
    logical: "..."
    emotional: "..."
```

**Current status**: Template provided; prompt content to be added during evaluation phase.

### Integration

1. **Session assignment** — Called in `SalesChatbot.__init__()`:
```python
self._ab_variant = assign_ab_variant(session_id)
```

2. **Recording variant** — In `SessionAnalytics.record_session_start()`:
```python
ab_variant=self._ab_variant
```

3. **Optional prompt replacement** — In `content.py` or prompt generation (not yet integrated):
```python
prompt = get_variant_prompt(base_prompt, self.bot._ab_variant, strategy="consultative")
```

---

## Web API Endpoints

### Get Session Analytics
```
GET /api/analytics/session/<session_id>
```
Returns all events for a session (for detailed post-hoc analysis).

**Example Response**:
```json
{
  "success": true,
  "session_id": "user_alice_1",
  "events": [
    {"timestamp": "2026-03-21T10:30:00", "event_type": "session_start", ...},
    {"timestamp": "2026-03-21T10:30:30", "event_type": "intent_classification", ...},
    ...
  ]
}
```

### Get Evaluation Summary
```
GET /api/analytics/summary
```
Returns aggregated analytics across all sessions (for evaluation chapter numbers).

**Example Response**:
```json
{
  "success": true,
  "total_sessions": 150,
  "stage_reach": {...},
  "intent_distribution": {...},
  ...
}
```

---

## Usage in Evaluation Chapter

### Quantitative Claims Now Supported

| Claim | Data Source |
|-------|---|
| "X% of sessions reached the pitch stage" | `stage_reach['pitch'] / total_sessions` |
| "Intent detected as high in Y% of turns" | `intent_distribution['high'] / (sum of all turns)` |
| "Most common objection: money (Z occurrences)" | `max(objection_types)` |
| "Strategy correctly switched in M sessions" | `sum(strategy_switches)` |
| "NEPQ variant (variant_b) reached pitch more often" | Compare `stage_reach['pitch']` by variant |

### Accessing Data

**Python (local analysis)**:
```python
from src.chatbot.session_analytics import SessionAnalytics

summary = SessionAnalytics.get_evaluation_summary()
print(f"Sessions reached pitch: {summary['sessions_reached_pitch']}")
print(f"Total sessions: {summary['total_sessions']}")
print(f"Pitch reach rate: {summary['sessions_reached_pitch'] / summary['total_sessions'] * 100:.1f}%")
```

**HTTP (from web app)**:
```bash
curl http://localhost:5000/api/analytics/summary | jq .
```

**Post-analysis (example)**:
```python
# Extract variant_b performance
import json
with open('analytics.jsonl') as f:
    events = [json.loads(line) for line in f]

variant_b_sessions = {e['session_id'] for e in events
                      if e.get('event_type') == 'session_start'
                      and e.get('ab_variant') == 'variant_b'}

variant_b_pitch_reach = sum(1 for e in events
                            if e.get('event_type') == 'stage_transition'
                            and e.get('to_stage') == 'pitch'
                            and e['session_id'] in variant_b_sessions)
```

---

## Design Principles

### 1. **Minimal Intrusion**
- New module is self-contained (`session_analytics.py`)
- Loader functions added to existing module (non-breaking)
- Optional config file (`variants.yaml`)
- Recording calls can be safely disabled/removed (clean separation)

### 2. **Graceful Degradation**
- Missing `variants.yaml` → system uses base prompts (no errors)
- Missing analytics.jsonl → system creates it on first write
- Analytics failures logged but don't crash bot
- A/B variant assignment works even if never used

### 3. **Empirical Integrity**
- Deterministic assignment prevents selection bias
- Full event log enables post-hoc validation ("Did we really measure this?")
- No modification of core FSM logic (analytics is purely observational)
- Thread-safe file operations (supports concurrent sessions)

### 4. **Academic Rigor**
- Structured event logging (not loose metrics)
- Timestamped records (reproducible, auditable)
- Aggregation functions (transparent methodology)
- API endpoints (data accessible beyond local analysis)

---

## Next Steps (Optional Enhancements)

1. **Populate `variants.yaml`** with real prompt variants during evaluation phase
2. **Call `get_variant_prompt()`** in `content.py` to actually use variants
3. **Call `record_session_end()`** in web layer for complete session lifecycle tracking
4. **Analyze variant performance** post-study using `GET /api/analytics/summary`
5. **Document findings** in evaluation chapter with concrete numbers from `analytics.jsonl`

---

## Files Modified/Created

| File | Change | Type |
|------|--------|------|
| `src/chatbot/session_analytics.py` | New module (analytics core) | NEW |
| `src/config/variants.yaml` | A/B variant config template | NEW |
| `src/chatbot/loader.py` | Added `assign_ab_variant()`, `get_variant_prompt()` | MODIFIED |
| `src/chatbot/chatbot.py` | Integrated analytics recording (6 calls) | MODIFIED |
| `src/web/app.py` | Added `/api/analytics/*` endpoints | MODIFIED |

---

## Verification

Run inline test:
```python
import sys
sys.path.insert(0, 'src')
from chatbot.session_analytics import SessionAnalytics
from chatbot.loader import assign_ab_variant

# Test A/B variant
v1 = assign_ab_variant("test_1")
v2 = assign_ab_variant("test_1")
assert v1 == v2  # Deterministic: OK

# Test analytics
SessionAnalytics.record_session_start("test", "cars", "consultative", "variant_a")
summary = SessionAnalytics.get_evaluation_summary()
assert summary['total_sessions'] == 1  # Recording works: OK
```

All imports and functions verified working.

---

## Backward Compatibility

✓ All existing functionality preserved
✓ No breaking changes to FSM, LLM, or web routes
✓ Analytics optional (can disable by removing calls)
✓ A/B variants optional (can ignore variant assignment)

System ready for evaluation phase data collection.
