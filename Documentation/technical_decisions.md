# DONT REMOVE THIS FILE

# Technical Decisions: Rationale and Trade-offs

This document evaluates three critical architectural choices that distinguish this system from generic LLM-augmented chatbots.

---

## Decision 1: YAML Configuration Over Relational Database

### What is stored
Signal keywords (intent, objection, commitment, etc.), FSM advancement thresholds, product metadata, and prospect preference categories—approximately 350 keyword entries and 12 tunable parameters across three YAML files: `signals.yaml`, `analysis_config.yaml`, `product_config.yaml`.

### Alternatives Considered

| Alternative | Advantages | Disadvantages |
|---|---|---|
| **SQLite / PostgreSQL** | CRUD at runtime; queryable; schema versioning | Binary diffs unreadable; migration scripts required; requires DBA mindset; overkill for read-only config |
| **JSON** | Lightweight; queryable via jq | No comments; no multiline strings for documentation; indentation-based line breaks are fragile |
| **YAML** | Readable by non-engineers; comment-rich; multiline strings; versionable diffs | No runtime write validation; no schema enforcement |

### Rationale (Why YAML)

Configuration is **read-only at runtime** (loaded once via `lru_cache` in `config_loader.py:37`). Signal keywords and thresholds do not change between chatbot interactions—they reflect the methodology (NEPQ signal keywords are fixed by framework, not tuned per user). Sales trainers (non-engineers) need to modify keyword lists and preference categories directly: "add 'hesitant' to doubt_keywords" is a one-line YAML edit, not a SQL migration.

Version control diffs on YAML are human-interpretable: adding a doubt keyword shows as a line addition, not a serialized delta. This enables the sales team to review and approve changes before deployment.

### Trade-off

No runtime write validation. Mitigated by `_REQUIRED_SIGNAL_KEYS` guard in `config_loader.py:14-18`, which enforces that all mandatory signal categories are present on load. If a key is deleted or misnamed, `load_signals()` raises a validation error immediately.

---

## Decision 2: Hybrid FSM + LLM Over Pure LLM Stage Management

### The Failure Mode

**Before this system was built**: Assume stage management is encoded entirely in the system prompt. The bot reads "You are in the Logical stage. Use questions to establish doubt" and the LLM infers what that means. If the user says "I'm happy with my current approach," does the LLM stay in the logical stage or advance?

The **failure observed** in this system's precursor (documented in `ARCHITECTURE.md`, Phase 4): the advancement rule `user_shows_doubt` previously read `return True if turns >= 5 else False`—equivalent to "advance after 5 turns, regardless of conversational content." A user stating "I'm perfect, don't need improvement" would trigger advancement to the emotional stage, rendering Future Pacing and Consequence of Inaction questions semantically incoherent (the bot would ask "what would be different if we solved your problem?" when no problem was verbalized).

### Alternative: Pure LLM
Inject stage instructions into the system prompt and trust the model to advance itself based on conversational quality. Example: "Determine if sufficient doubt has been established. If yes, respond as if advancing to the emotional stage. If no, stay in logical."

**Problem**: The model's judgement of "sufficient doubt" is implicit and unauditable. Two conversations with similar doubt-level might yield different outcomes if the model's context window or temperature changes.

### Rationale (Why Hybrid FSM + LLM)

The FSM provides three guarantees that prompt instructions alone cannot:

1. **Observable state**: `flow_engine.current_stage` is queryable and determinis tic. Trainee coaches can inspect the FSM state and explain to the trainee why the bot advanced: "The FSM detected the keyword 'struggling' in your response, which is in the doubt_keywords list for this stage."

2. **Deterministic transitions**: Same signals → same state, always. The `_check_advancement_condition()` function (lines 92–117 in `flow.py`) explicitly reads keyword lists from `analysis_config.yaml:advancement.logical.doubt_keywords` (25 specific terms: "not working", "struggling", "problem", "difficult", "frustrated", etc.). If the user says "I'm struggling," the bot advances. If the user says "everything is fine," the bot does not advance, regardless of turn count or model state.

3. **Auditability**: ADVANCEMENT_RULES registry (lines 152–158 in `flow.py`) maps rule names to functions, making it possible to inspect, test, and version each advancement condition independently.

**Evidence**: The old `turns >= 5` rule is a counterexample. It is completely decoupled from conversational content—a test case would show it fails. The new hybrid FSM enforces methodology semantics.

### Trade-offs

**Rigidity**: The FSM enforces a fixed stage sequence (intent → logical → emotional → pitch → objection). An atypical conversation that explores consequences before naming a problem cannot express that non-linear path.

**Mitigations**:
- `should_advance()` checks `user_demands_directness` and `direct_info_requests` signals first—if the user says "just tell me the options," the FSM jumps directly to pitch, bypassing logical/emotional stages
- `urgency_skip_to` in the transitions dict: impatience signals in consultative sales skip to pitch immediately (`flow.py:45`)
- The transactional strategy uses a different stage sequence entirely (intent → pitch → objection, no emotional stage)

**Hidden dependencies**: The FSM depends on signal keywords being accurate. If `doubt_keywords` is missing "unsure" and the user says "I'm unsure," the bot will not advance. Mitigated by extensive keyword list curation and testing (see `signals.yaml`; 25+ doubt terms verified against NEPQ framework).

---

## Decision 3: Inline Imports to Break Circular Dependency

### The Problem

- `content.py` defines prompts and needs to call `analyze_state()` from `analysis.py` to make adaptive prompt decisions (e.g., is the user guarded? has question fatigue occurred?)
- `analysis.py` needs signal keywords from `load_signals()` to detect intent, objection, etc.
- Prior design: `analysis.py` imported SIGNALS directly from `content.py`
- **Result**: Circular import at module load time — `content.py` → `analysis.py` → `content.py`

### Alternative: Restructure Dependency Graph
Create a new `prompt_builder.py` module that holds all adaptive prompt logic, freeing `content.py` to focus purely on prompt templates. This would eliminate the circular import cleanly.

**Why not chosen**: Requires significant refactoring; delays implementation. Documented as future work in `ARCHITECTURE.md` (Future Recommendations, section 1).

### Rationale (Why Deferred/Inline Imports)

The chosen solution breaks the circular import at module load time:

1. `analysis.py` (line 12) calls `load_signals()` directly from `config_loader.py` instead of importing from `content.py`
2. `content.py` imports `analyze_state`, `classify_objection`, etc. **inside the function body** of `generate_stage_prompt()` (line 707), not at module load time

This allows both modules to load successfully. The import occurs at function execution, not at module initialization, so the circular reference is never encountered.

### Trade-offs

**Dependency graph opacity**: The true dependencies between `content.py` and `analysis.py` are hidden inside function bodies. A developer reading the module-level imports will not immediately see that `generate_stage_prompt()` depends on `analysis.py`.

**Deferred errors**: If `analysis.py` has a syntax error, the error will not be caught until `generate_stage_prompt()` is first called, not at startup.

**Mitigations**:
- Documented in `ARCHITECTURE.md` (Circular Dependency Fixes, Phase 2)
- Planned extraction to `prompt_builder.py` in Future Recommendations
- Runtime testing covers the happy path, so deferred import errors would surface immediately in testing

### Information Density Check (Rules of Engagement)

This section anchors each decision to:
- **Specific frameworks/terms**: Mealy/Moore FSM (decision 2), YAML/JSON/SQLite (decision 1), circular import pattern (decision 3)
- **Exact metrics**: 350 keywords, 12 parameters (decision 1); 25 doubt_keywords in config (decision 2); `lru_cache` and line numbers (decision 3)
- **Synthesis vs. listing**: Trade-offs are evaluated with explicit mitigation strategies, not just listed

---

## Question Fatigue Detection (Technical Clarification)

Included here to eliminate vagueness in `analysis_config.yaml:thresholds:question_fatigue_threshold`.

**Definition**: `question_fatigue` is `True` if the number of question marks ("?") in the last 4 bot messages is ≥ 2 (the threshold value).

**Code location**: `analysis.py:176-179`
```python
question_fatigue = False
if history:
    recent_bot = [m["content"] for m in history[-4:] if m["role"] == "assistant"]
    question_fatigue = sum(1 for msg in recent_bot if "?" in msg) >= _T["question_fatigue_threshold"]
```

**Rationale**: This detects interrogation overload. If the bot asks 2+ questions in the last 4 messages, the user may be overwhelmed or defensive. When `question_fatigue=True`, `generate_stage_prompt()` injects `_build_tactic_guidance()` guidance: "Do NOT interrogate. Switch to statements that invite correction (elicitation)."

**Not detected**: This threshold does NOT distinguish between a single multi-part question ("What's been the main thing holding you back, and how long has that been an issue?") and two separate questions. It counts message boundaries, not logical question units. This is intentionally simple to avoid over-engineering; in practice, the bot's prompt already constrains it to one question per turn.
