# Sales Roleplay Chatbot

Rule-based sales training system using KALAP V2 framework. Implements Smash Formula methodology for realistic conversation practice with real-time response validation and phase-based progression.

## Key Technologies

- **Backend**: FastAPI + KALAP V2 core engine (Python)
- **Frontend**: React.js SPA
- **Libraries**: rapidfuzz, jinja2, textblob (3 minimal dependencies)

## Main Features

- Interactive roleplay with configurable prospect personas
- 6-phase conversation flow (Intent → Logical Certainty → Emotional Certainty → Future Pace → Consequences → Pitch)
- Real-time response validation with phase advancement gates
- Intent/objection detection via fuzzy matching
- Session context tracking and commitment temperature monitoring

## Architecture

**Modular design** (High cohesion, loose coupling):

```
Frontend (React) → Backend (FastAPI) → KALAP V2 Core
    ├─ response_generator.py - Orchestrator
    ├─ context_tracker.py - Session data
    ├─ question_router.py - Strategic question selection
    ├─ phase_manager.py - Phase transitions & gates
    ├─ answer_validator.py - Response scoring & validation
    └─ fuzzy_matcher.py - Intent detection
```

**Code Quality**:
- Zero hardcoding (all config in constants.js + JSON)
- Single Responsibility Principle applied
- 113 tests passing (100%): 70 core + 43 supporting, organized by component criticality

**Recent Updates (2026-01-19)**:
- ✅ Implemented `fuzzy_matcher.py` - Intent detection with typo tolerance (13/13 tests passing)
- ✅ Implemented `question_router.py` - Strategic question selection (10/10 tests passing)
- ✅ Complete documentation: See `docs/implementation-decision.md` and `docs/implementation-summary.md`
- ✅ Validated end-to-end: API responds <100ms with deterministic phase progression

---

## Setup (3 Steps)

**Prerequisites**: Python 3.12+, Node.js 18+

### 1. Environment Configuration
```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env
```

### 2. Backend (Terminal 1)
```bash
cd "Sales roleplay chatbot"
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Server runs at: `http://localhost:8000`

### 3. Frontend (Terminal 2)
```bash
cd "Sales roleplay chatbot/frontend"
npm install && npm start
```
App opens at: `http://localhost:3000`

**Tests** (optional):
```bash
cd "Sales roleplay chatbot" && pytest tests/ -v
```

---

## Design Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| **Rule-based over LLM** | Deterministic behavior enables 100% test coverage; <100ms response time | Predictable, auditable, testable |
| **6 focused modules** | Single Responsibility Principle applied per module | Independent testing, clear boundaries |
| **JSON configuration** | Phase definitions, scoring rules externalized | Non-technical users can modify behavior without code changes |
| **In-memory storage** | Academic FYP scope: single-user, session-based | Zero infrastructure overhead; appropriate for prototype stage |
| **Test organization** | Core (70 tests) vs Supporting (43 tests) by criticality | Prioritized test execution; clear component importance |

**Trade-offs Accepted**:
- Simplicity over NLP sophistication (fuzzy matching vs transformer models)
- Explicit rules over learned patterns (maintainability, explainability)
- Session-based over persistent storage (development velocity, reduced complexity)

---
