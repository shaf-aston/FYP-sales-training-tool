# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Quick Reference: Common Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with SAFE_GROQ_API_KEY (or ALTERNATIVE_GROQ_API_KEY) and SAMBANOVA_API_KEY
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### Running the Application
```bash
# Local development server
python -m flask run  # Runs on http://localhost:5000

# Production (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 src.web.app:app
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_acknowledgment_tactics.py -v

# Run with coverage
pytest tests/ --cov=src/chatbot --cov-report=html

# Load testing (4 profiles: light, medium, heavy, stress)
bash run_load_test.sh medium
# Or manually:
python tests/load_test.py https://fyp-sales-training-tool.onrender.com 20 60
```

### Code Quality (if needed)
```bash
# Check for linting issues (use existing tests as gold standard)
pytest tests/ -v

# Verify all imports resolve
python -c "from chatbot.chatbot import SalesChatbot; print('OK')"
```

---

## Architecture Overview

### System Design Pattern: FSM + LLM Orchestration

The system separates **deterministic control flow** (FSM) from **probabilistic generation** (LLM):

```
User Input → Intent Classification → FSM Advancement → Prompt Assembly → LLM Call → Response
                    (Analysis)             (Flow)          (Content)      (Provider)
```

**Why This Matters**: FSM ensures structured sales methodology (NEPQ for consultative, NEEDS→MATCH→CLOSE for transactional) without fine-tuning. LLM generates natural, human-like responses within those constraints.

### Core Module Roles

| Module | Responsibility | Key Classes |
|--------|-----------------|------------|
| `chatbot.py` | Session orchestrator, FSM state manager, API gateway | `SalesChatbot` |
| `flow.py` | FSM definitions & transition logic | `SalesFlowEngine`, `FLOWS` dict |
| `analysis.py` | Signal detection (intent, objections, sentiment) | `AnalysisEngine` (pure functions) |
| `content.py` | Prompt assembly, rules, tactical injection | `get_response_prompt()`, `get_base_rules()` |
| `providers/` | LLM abstraction (Groq primary, SambaNova backup) | `GroqProvider`, `SambaNovaProvider`, `BaseLLMProvider` |
| `trainer.py` | Coaching feedback generation | `SalesTrainer` |
| `session_analytics.py` | Conversation metrics for evaluation | `SessionAnalytics` |
| `knowledge.py` | Custom product knowledge injection | `KnowledgeBase` |
| `quiz.py` | Assessment quizzes (stage ID, next-move, direction) | `QuizEngine` |

### Strategy Detection & Switching

**Default**: Consultative (5-stage: intent → logical → emotional → pitch → objection)
**Alternative**: Transactional (3-stage: intent → pitch → objection)

Strategy is **detected from user signals** (budget mentions, urgency, product preference) in `chatbot.py:_detect_and_switch_strategy()`. Once detected, it locks unless user signals trigger a switch. This prevents mid-conversation strategy drift.

### Configuration-First Design

Instead of hardcoding business rules, the system reads from YAML:

- `signals.yaml` — Keyword patterns for intent, objections, commitment, guardedness
- `analysis_config.yaml` — Thresholds, advancement conditions, question patterns
- `product_config.yaml` — Product metadata, strategy assignments, keyword matching
- `tactics.yaml` — Tactical acknowledgment rules (vulnerability vs. guardedness vs. info request)
- `overrides.yaml` — Custom prompt overrides per product/strategy
- `variants.yaml` — A/B test variants for controlled experiments

**Key Pattern**: Config changes require **zero code changes**. Non-engineers can edit signals or products and immediately see effects.

---

## Key Architectural Decisions

### 1. In-Memory Sessions with Lazy Cleanup
Sessions are stored in `app.py:sessions` dict (not a database). This is intentional:
- Simpler for FYP scope (single-server deployment)
- Fast access for 100+ concurrent users
- Lazy cleanup: sessions are removed on stale requests (> 6 hours idle)

**If Scaling Needed**: Move to Redis `SessionSecurityManager` in `security.py` (already supports it).

### 2. YAML Over Database
Signals, products, and analysis rules live in YAML rather than a database because:
- Domain experts (non-engineers) can tweak signals and thresholds
- Git-versioned configuration enables rollback
- No dependency on external services

**Trade-off**: No real-time rule updates (restart required). Acceptable for FYP.

### 3. FSM as Constraint, Not State
The FSM (`flow.py`) defines *allowed transitions* but doesn't *store* state—the LLM does that implicitly:
- User message is analyzed for intent/objections/sentiment
- Analysis determines which FSM stage is appropriate
- Content generation (prompts) reinforces that stage
- If LLM drifts, next turn's analysis brings it back

This is more robust than storing `current_stage` in the DB because **analysis is the source of truth**.

### 4. Provider Factory with Hot-Swapping
Providers (`groq_provider.py`, `sambanova_provider.py`) implement `BaseLLMProvider`:
- `chat()` → returns `LLMResponse` with `text`, `latency_ms`
- `switch_provider()` in `chatbot.py` changes providers mid-session
- Groq is primary (faster, free tier), SambaNova is backup

Latest config: **Groq primary, SambaNova backup** (cloud-based, zero local dependencies).

### 5. Prompt Engineering as Behavioral Control
Instead of fine-tuning, `content.py` assembles prompts that:
1. Define stage-specific role (e.g., "You are at the EMOTIONAL stage, ask a future-pacing question")
2. Inject signal-detected tactics (e.g., "User showed vulnerability, use FULL acknowledgment")
3. Include universal rules in `_SHARED_RULES` (e.g., "DO NOT end pitch with a question")
4. Embed examples from `SIGNALS` dict (e.g., "Here are objection types you might hear...")

Result: 92% stage-appropriate progression without fine-tuning (verified by test suite).

---

## Code Patterns & Conventions

### Session Management Pattern
```python
# In app.py routes:
def require_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.args.get('session_id') or str(uuid.uuid4())
        if session_id not in sessions:
            sessions[session_id] = SalesChatbot(session_id, ...)  # Initialize
        return f(sessions[session_id], *args, **kwargs)
    return decorated_function

@app.route('/api/chat', methods=['POST'])
@require_session
def chat(chatbot):
    message = request.json['message']
    response = chatbot.chat(message)
    return jsonify(response)
```

### FSM Advancement Pattern
```python
# In chatbot.py:
# When to advance: analysis detects clear progression signals
if flow_engine.should_advance(current_stage, analysis):
    new_stage = flow_engine.get_next_stage(current_stage, strategy)
    session_analytics.record_stage_transition(current_stage, new_stage)
    current_stage = new_stage

# Prompt respects stage:
response_text = get_response_prompt(
    current_stage,
    strategy,
    history,
    analysis,  # Signal-detected: intent, objections, sentiment
    product_id
)
```

### Configuration Loading Pattern
```python
# In any module needing YAML:
from chatbot.loader import load_config

signals = load_config('signals.yaml')  # Cached via @lru_cache
analysis_config = load_config('analysis_config.yaml')

# Use cached config:
if user_sentiment == 'vulnerable':
    ack_tactic = signals['acknowledgment_tactics']['full']
```

### Provider Abstraction Pattern
```python
# In chatbot.py:
from chatbot.providers.factory import create_provider

provider = create_provider('groq')  # or 'sambanova'
response = provider.chat(
    messages=conversation_history,
    system_prompt=assembled_prompt,
    temperature=0.7,
    max_tokens=300
)
# response = LLMResponse(text=..., latency_ms=...)
```

---

## Testing Strategy

### Test Organization
- **Unit tests**: Pure logic, no LLM calls (e.g., `test_analysis.py`, `test_flow.py`)
- **Integration tests**: FSM + Analysis together, mock LLM (e.g., `test_consultative_flow_integration.py`)
- **Behavioral tests**: Verify NEPQ framework adherence (e.g., `test_acknowledgment_tactics.py`)
- **Load tests**: Concurrent user simulation for Render deployment (e.g., `load_test.py`)

### Test Fixtures (in `conftest.py`)
```python
# Pytest auto-discovers fixtures:
@pytest.fixture
def chatbot():
    return SalesChatbot(session_id="test_session")

@pytest.fixture
def mock_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test_key")
    return GroqProvider()
```

### Key Test Patterns

**Pure signal detection** (no LLM):
```python
def test_intent_detection():
    analysis = AnalysisEngine()
    result = analysis.classify_intent("I really need a car by next week")
    assert result == 'high'
```

**FSM advancement** (mock LLM):
```python
def test_advance_to_logical(chatbot, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "dummy")
    chatbot.chat("I need a car")  # intent signal
    assert chatbot._current_stage == 'intent'

    chatbot.chat("My old one keeps breaking")  # objection/problem
    # FSM detects advancement condition
    assert chatbot._current_stage == 'logical'
```

**Load test**:
```bash
python tests/load_test.py https://fyp-sales-training-tool.onrender.com 20 60
# Creates 20 virtual users, runs for 60 seconds
# Prints: requests, latency (avg/median/p95), error rate
# Pass if: <10% error rate and p95 < 5s
```

---

## Important Modules to Know

### Dual Strategy Support
Both consultative and transactional flows coexist:
- **Consultative**: NEPQ-based (emotional stage included)
- **Transactional**: Budget-focused, direct pitch (no emotional stage)

Strategy is detected in `_detect_and_switch_strategy()` from user signals (mentions of budget, urgency, or specific product).

### Objection Handling
Objections are classified into 6 types (smokescreen, money, fear, partner, logistical, indecision) in `analysis.py:classify_objection()`.
The canonical decision matrix is stored in the repository as `Objection Handling matrix SOP.pdf` and the implementation used by prompts lives in `content.py` as `_SOP_FLOWS` (consultative) and `_SOP_FLOWS_TRANSACTIONAL` (transactional overrides).

### Tactical Acknowledgment
User sentiment (vulnerable vs. guarded vs. neutral) determines how we validate:
- **Vulnerable** (disclosed personal problem): Full acknowledgment ("That must be frustrating...")
- **Guarded** (defensive): Light acknowledgment ("Got it")
- **Neutral** (info request): No acknowledgment

Detected in `analysis.py:identify_user_sentiment()`.

### Performance Tracking
Every chat turn logs latency to `metrics.jsonl`:
```json
{"session_id": "abc123", "provider": "groq", "latency_ms": 987, "turn": 5}
```

Used by `PerformanceTracker.get_summary()` for monitoring.

---

## Common Modification Patterns

### Adding a New Product Signal
1. Edit `src/config/product_config.yaml`: add product name and keywords
2. Set `strategy: "consultative"` or `"transactional"`
3. No code changes needed—`loader.py` picks it up automatically

### Changing Advancement Thresholds
1. Edit `src/config/analysis_config.yaml`: adjust `high_intent_required` or `objection_threshold`
2. Tests in `test_consultative_flow_integration.py` verify progression
3. Run: `pytest tests/test_consultative_flow_integration.py -v`

### Adding a New Tactic
1. Add keyword patterns to `src/config/tactics.yaml`
2. Import and use in `content.py`: `get_tactic('acknowledgment', sentiment)`
3. Test with `test_acknowledgment_tactics.py`

### Swapping LLM Providers
1. Choose provider at session init (for example: `provider="sambanova"`)
2. Both providers implement same `BaseLLMProvider` interface
3. No code changes—factory pattern handles it

---

## Codebase State & Known Limitations

### Recent Improvements (March 2026)
- **SambaNova Backup Integration**: Backup cloud provider (no local LLM dependency)
- **Load Testing**: 392-line load test with 4 profiles (light/medium/heavy/stress)
- **Code Cleanup**: ~110 lines of dead code removed, section headers added
- **Session Analytics**: Tracks stage transitions and intent distribution for evaluation

### Known Limitations (Acknowledged, Not Bugs)
- **In-Memory Sessions**: Scale limited to single server (~100 concurrent users)
- **YAML-Only Config**: Changes require Flask restart
- **Cold-Start Metrics Scan**: First `/api/debug/metrics` call scans full JSONL file (< 5k lines, acceptable)
- **Provider Latency**: Groq ~900-1000ms, SambaNova varies by selected model

### Technical Debt (Deferred to Post-FYP)
- `content.py` is 600+ lines and mixes prompts, assembly, and acknowledgment logic (SRP violation, but low risk to refactor)
- No GraphQL API (REST is sufficient for current scope)

---

## Files Not to Edit (and Why)

### `src/chatbot/content.py`
- **620+ lines** of carefully crafted prompts and rules
- Every phrase is intentional and connected to NEPQ framework
- **Changes risk methodology adherence** (92% stage accuracy validated through this file)
- Only edit if you've read `NEPQ_ALIGNMENT.md` and understand the theory

### `signals.yaml` (Core Keyword Set)
- Signals used for intent/objection/sentiment detection
- Removing or duplicating keywords can break analysis
- **Read comments carefully** before editing—some are collision-avoidance (e.g., "ok" vs. "okay")

### Test Files (Unless Adding Tests)
- `conftest.py` sets PYTHONPATH and environment
- `helpers.py` provides shared test utilities
- Existing tests are the ground truth for behavior validation

---

## Debugging Tips

### "ModuleNotFoundError: chatbot"
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
python -m pytest tests/test_status.py -v
```

### "GROQ_API_KEY not found"
```bash
# Check .env exists
cat .env | grep GROQ_API_KEY

# Or set directly
export GROQ_API_KEY="gsk_..."
python -m flask run
```

### LLM Response is Off-Topic
1. Check `current_stage` in logs
2. Verify `analysis.classify_intent()` is detecting signals correctly
3. Check `_SHARED_RULES` in `content.py`—may need stricter constraint
4. Review LLM system prompt in `get_response_prompt()`

### FSM Won't Advance
1. Enable debug logging: `ENABLE_DEBUG_PANEL=true` in `.env`
2. Visit `/api/debug/session/<session_id>`
3. Check `analysis` object—ensure signals are detected
4. Check `_current_stage` and `_should_advance()` logic in `flow.py`

---

## Documentation Reference

| File | Purpose |
|------|---------|
| `README.md` | Quick start, feature overview |
| `Documentation/ARCHITECTURE_CONSOLIDATED.md` | System design, module responsibilities, FSM details |
| `Documentation/Project-doc.md` | Full thesis-like report (FYP submission) |
| `.claude/projects/.../memory/MEMORY.md` | This Claude's persistent session memory |
| `tests/TESTING_STRATEGY.md` | Test methodology and framework (if exists) |

---

## Deployment Checklist

Before pushing to Render:
- [ ] `.env` has `SAFE_GROQ_API_KEY` (or `ALTERNATIVE_GROQ_API_KEY`) and `SAMBANOVA_API_KEY`
- [ ] `LLM_PROVIDER=groq` is set as primary
- [ ] `pytest tests/ -v` passes (all tests green)
- [ ] `bash run_load_test.sh light` completes with <10% error rate
- [ ] Check `/api/status` returns provider list
- [ ] Check `/api/chat` works with test message

---

## Summary

**This is a FSM + LLM hybrid** that enforces sales methodology without fine-tuning. The architecture separates concerns (analysis → flow → content → providers), uses YAML for configuration, and tests extensively. New contributors should focus on understanding the FSM logic first, then the analysis/content pipeline, before touching provider code.

