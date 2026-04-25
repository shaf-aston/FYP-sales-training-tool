# DONT REMOVE THIS FILE

## Appendix C: Project Development Diary (condensed)

Project: Sales conversation AI chatbot — FSM-driven routing, prompt-based behavioural control, and real-time coaching feedback.
Timeline: September 2025 – April 2026 (28 weeks)

---

### Phase Timeline

**Sep–Nov 2025**: Built local LLM prototype + FastAPI. Hit immediate walls — latency >2s per turn, memory thrashing at 5+ turn conversations made interactive training unusable. Switched to cloud APIs (Groq) in parallel.

**Nov–Jan 2026**: Ethics review cleared. Evaluated provider options (including an experimental vendor called "Lotus"); settled on Groq + OpenRouter fallback but kept provider abstraction loose so alternatives remain testable.

**Feb 2026**: Strategy Pattern refactor. Early design used polymorphic "strategy" objects that accumulated logic fast — stage transitions, prompt selection, signal analysis all tangled together. Replaced with YAML-driven FSM. Now stage transitions are declarative (FLOWS dict + advancement rules in YAML), and non-engineers can edit signals/thresholds without touching Python.

**Mar 2026**: Hardening & empirical fixes (15 P0–P1 bugs):
- Prompt layering: fixed order (overrides → adaptations → baseline) to prevent conflicting instructions
- Stage gating: objection SOPs only inject at OBJECTION stage (isolated from other stages)
- Keyword matching: switched from substring to whole-word regex (e.g., "no" no longer matches "know")
- Question fatigue: detect 2+ questions in last 4 messages, flip bot to statements instead of interrogation
- Measured improvement: false intent detection 40% → 92% accuracy; premature stage advancement 40% → 94% accuracy

**Apr 2026**: Simulation & evaluation. Implemented role-specific prospect framing (bot reads spec; prospect AI reads buyer research) to avoid leaking ground truth. Added deterministic, session-locked A/B variant assignment (hash-based, not DB). Built analytics system to track stage transitions, objection types, strategy switches — enables empirical evaluation.

---

### Critical Technical Decisions (Made & Rationale)

**1. YAML Configuration Over Relational Database**
- **Scope**: 350 keyword entries (signals.yaml), 12 tunable thresholds (analysis_config.yaml), product metadata (product_config.yaml)
- **Why YAML**: Read-only at runtime (loaded once via lru_cache). Signal keywords are framework-fixed (NEPQ, not per-user tuning). Sales trainers edit YAML directly; diffs are human-readable in git.
- **Trade-off**: No runtime write validation. Mitigated by `_REQUIRED_SIGNAL_KEYS` guard (raises on load if any mandatory key is missing).
- **Alternative rejected**: SQLite/PostgreSQL overkill (binary diffs unreadable); JSON lacks multiline string support and comments.

**2. Hybrid FSM + LLM Over Pure LLM**
- **Problem solved**: Early prototype delegated stage progression to LLM prompt ("determine if doubt is sufficient; if yes, advance"). Result: same doubt-level yielded different outcomes depending on model's context window. Unauditable.
- **Decision**: FSM provides three guarantees:
  1. Observable state (`current_stage` queryable)
  2. Deterministic transitions (same signals → same outcome always)
  3. Auditability (ADVANCEMENT_RULES registry maps rule name to function)
- **Evidence**: `doubt_keywords` list has 25 explicit terms ("struggling", "not working", "problem", "difficult", etc.). If user says "struggling", FSM advances to EMOTIONAL stage. If user says "everything is fine", FSM does not advance, regardless of turn count.
- **Measured correctness**: 25 test scenarios; false stage advancement rate 40% → 94% post-fix.
- **Trade-off**: FSM enforces linear stage sequence (intent → logical → emotional → pitch → objection). Mitigated by `urgency_skip_to` overrides (direct info requests jump to pitch immediately).

**3. Inline Imports to Break Circular Dependency**
- **Problem**: `content.py` needed `analyze_state()` from `analysis.py`; `analysis.py` needed signals from `content.py`. Circular import at module load time.
- **Solution**: `analysis.py` imports signals directly from `config_loader.py`. `content.py` imports analysis functions **inside function bodies** (line 707 in `generate_stage_prompt()`), not at module scope.
- **Trade-off**: Dependency graph less obvious; deferred import errors surface only when function is first called (not at startup). Acceptable — integration tests catch this immediately.
- **Future**: Planned extraction to `prompt_builder.py` (post-FYP).

**4. Stage-Gated Objection Handling**
- **Decision**: Objection classification and SOP injection only occur during OBJECTION stage, via dedicated `build_objection_context()` function in content.py. Driven by `objection_flows.yaml` (not hardcoded).
- **Why**: Prevents SOP scripts leaking into INT, LOGICAL, EMOTIONAL, PITCH stages. Centralizes data (YAML) separate from logic.
- **Tested**: `test_objection_sop.py` includes `TestStagePromptInjectsSopSteps` and `TestObjectionIsolation` to catch regression.

**5. Layered Application Boundary (Controller → Service → Domain → Infrastructure)**
- **Layers**:
  - Presentation: Flask route handlers (validate HTTP shape, session headers)
  - Application: `SalesChatbot` orchestrates one turn
  - Domain: `SalesFlowEngine` (FSM) + `analysis.py` (signals)
  - Infrastructure: `SessionPersistence`, `SessionAnalytics`, `PerformanceTracker`, provider adapters
- **Benefit**: Clear examiner answer: "who decides what happens next?"

**6. Formal FSM Contract (States, Transition Rules, Guards)**
- **Explicit**:
  - `Stage` enum: INTENT, LOGICAL, EMOTIONAL, PITCH, OBJECTION, OUTCOME
  - `Strategy` enum: CONSULTATIVE, TRANSACTIONAL
  - Transitions: trigger, guard function, min_turns, max_turns
  - Priority overrides evaluated first (urgency signals, direct info requests)
- **Benefit**: FSM is testable and auditable, not a black box.

**7. Single Source of Truth for Seller FSM vs Prospect Simulation**
- **Boundary**: 
  - Seller mode: `SalesFlowEngine` owns stage progression
  - Prospect mode: `ProspectSession` manages simulated buyer readiness only
- **Why**: No conflicting decision engines. Clear ownership avoids ambiguity.

**8. Closed-Loop Decision Pipeline (Analysis → FSM → Prompt → Provider → FSM)**
- **Sequence per turn**:
  1. Request enters controller
  2. State analysis runs (intent, objection, commitment signals detected)
  3. FSM checks override rules then standard transition rules
  4. Prompt is assembled (overrides → adaptations → baseline)
  5. Provider router executes (Groq → OpenRouter fallback)
  6. Response is parsed and validated (guardrails check for rule violations)
  7. FSM writes turn event and applies advancement
  8. Session persisted; analytics recorded
- **Benefit**: Transforms architecture from static diagram to auditable runtime behavior.

**9. Provider Depth & Resilience as First-Class Design**
- **Pipeline**: Routing (`ProviderRouter`) → Fallback/retry (`FallbackStrategy`) → Normalization (`ResponseParser` + `LLMResponse`) → Unified error contract (`ErrorEnvelope`)
- **Concrete**: Groq has 99%+ uptime; fallback to OpenRouter on timeout or rate-limit. Response latency tracked per provider.
- **Why**: Reliability is not bolt-on; it's a core abstraction.

**10. Voice Path as Integrated Flow, Not Sidecar**
- **Model**: STT (`VoiceProvider.transcribe`) → same chat decision loop → TTS (`VoiceProvider.synthesize`)
- **State**: Shared session and FSM state with text chat
- **Benefit**: Voice is a transport mode over the same decision core, not an alternative architecture.

---

### Key Outcomes

- **Configuration-driven behaviour**: 350+ keyword entries and 12 tunable parameters live in YAML, editable by non-engineers. No code changes required for signal adjustments.
- **Provider flexibility**: Abstraction kept loose. Groq is primary; Lotus or other alternatives remain testable without refactor.
- **Empirical safety**: 15 bugs fixed (40%–94% accuracy gains measured in stage advancement, intent detection). Tests + analytics guard regressions.
- **Evaluation ready**: A/B assignment deterministic (session-locked hash). Analytics track stage transitions, objection types, strategy switches. Repeatable.

---

### Lessons Learned

- Test scenarios pay for themselves in week 2, not week 20. Build them early.
- Configuration-driven design + YAML make the system scale. Prompt engineering and signal tuning become non-engineers' work.
- Document decisions continuously. "Why did we do this?" is half the grade; commit messages and decision logs prove it.
- Circular dependencies and tight coupling reveal themselves fast in integration tests — catch them early and refactor hard.

---

### Full Evidence

- Commit history: `a16c9cd` (FSM hardening), `a9afd7b` (content refactor), technical audit outcomes in `Documentation/technical_audit.md`
- Architecture: See `Documentation/ARCHITECTURE_CONSOLIDATED.md` for layered design details and runtime sequence diagrams

