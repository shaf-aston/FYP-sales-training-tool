# Test Suite Organization

## Structure

Tests are organized into 6 logical categories:

### `unit/` — Core Module Unit Tests
- **Purpose**: Test individual functions/classes in isolation
- **Files**:
  - `test_core.py` — Analysis, signals, preferences, config loading, knowledge, aliases, providers
  - `test_chat_response_builder.py` — Response formatting
  - `test_user_turn_count.py` — Turn counter logic
  - `knowledge/test_knowledge_sanitization.py` — Knowledge base filtering

### `integration/` — End-to-End Flows & FSM
- **Purpose**: Test complete conversation paths, state transitions, regressions
- **Files**:
  - `test_consultative_flow.py` — FSM state machine flow
  - `test_conversations.py` — Multi-turn conversation scenarios
  - `test_dummy_chat.py` — Smoke test with DummyProvider
  - `test_regression_and_security.py` — Regression bugs, security invariants

### `providers/` — LLM & Voice Providers
- **Purpose**: Test provider abstraction, fallback logic, rate limiting
- **Files**:
  - `test_voice_provider.py` — Deepgram STT, Edge TTS initialization
  - `test_fallback.py` — Rate-limit fallback chains

### `web/` — Flask Web Routes
- **Purpose**: Test HTTP endpoints, request validation, status codes
- **Files**:
  - `test_routes.py` — `/api/voice/transcribe/`, `/api/voice/status/`, `/api/prospect/*`
  - `test_search.py` — Web search functionality

### `domain/` — Domain-Specific Logic
- **Purpose**: Test business logic specific to sales training
- **Files**:
  - `test_objection.py` — Objection classification & handling
  - `test_priority_fixes.py` — Specific behavioral requirements (intent lock, frustration, etc.)
  - `test_quiz.py` — Quiz engine & question delivery
  - `test_training.py` — Trainer, DevPanel, assessment logic
  - `test_scoring.py` — Signal detection, session length, stage progression scoring
  - `test_prospect.py` — Prospect mode conversation flow
  - `test_performance.py` — Performance metrics & tracking

### `config/` — Prompts & Configuration
- **Purpose**: Test prompt assembly, consistency, correctness
- **Files**:
  - `test_prompt_assembly.py` — Probe-based prompt validation
  - `test_prompt_integrity.py` — Stage coverage, dedup stability
  - `test_prompt_ordering.py` — Prompt sequencing, provider payloads

---

## Running Tests

### All tests
```bash
pytest tests/ -v
```

### By category
```bash
pytest tests/unit/ -v               # Core logic
pytest tests/integration/ -v        # End-to-end flows
pytest tests/providers/ -v          # LLM/Voice providers
pytest tests/web/ -v               # Web routes
pytest tests/domain/ -v            # Domain logic
pytest tests/config/ -v            # Prompts & config
```

### Specific test
```bash
pytest tests/domain/test_scoring.py::TestScoringLogic::test_signal_detection_25_points -v
```

---

## Coverage Status

| Category | Files | Status | Gap |
|----------|-------|--------|-----|
| unit | 4 | Strong (90%+) | None identified |
| integration | 4 | Strong (91%+) | Could expand regressions |
| providers | 2 | Medium (20-50%) | Rate-limit edge cases |
| web | 2 | Low (20-22%) | Most endpoints untested |
| domain | 7 | Medium (43-93%) | Training/scoring details |
| config | 3 | Strong (97%) | None identified |

**Total**: 22 test files, 443+ tests, ~60% coverage

---

## Notes

- **conftest.py** at root sets dev environment
- All test paths use `sys.path.insert(0, src)` fixture
- Mocking strategy: `unittest.mock` for external deps (providers, Flask)
- Use `DummyProvider` for end-to-end tests requiring no real API keys
