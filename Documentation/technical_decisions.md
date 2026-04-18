# Documentation Status: ACTIVE
<!-- APPLICABILITY: Core architecture and design decisions. Keep this in Documentation root; update when changing architecture or analysis configs. -->

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

**Concrete measured failures** (Appendix C.2):
- **False Stage Advancement**: Intent keywords like "want", "need", "trying" fired on generic statements (e.g., "I want to make money"), triggering stage advancement regardless of context. Baseline: 40% false positives → 92% accuracy post-fix.
- **Premature Advancement (FSM Logic)**: FSM jumped LOGICAL → EMOTIONAL before prospect acknowledged any problem, rendering emotional questions (Future Pacing, Consequence of Inaction) semantically out of place. Baseline: 40% false advances → 94% accuracy post-fix.

Both failures documented across 25 developer-executed test scenarios. Regression test output (see `pytest_output.txt`, failing `_check_advancement_condition` tests) also captured these issues. Motion for hardening: commits `a16c9cd`, `a9afd7b`.

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

---

## Guardedness Scoring: Word-Boundary Matching Over Substring Search

### The Problem

`detect_guardedness()` scores a message by iterating over weighted guardedness categories (evasive, sarcasm, deflection, defensive) and checking whether any keyword in each category appears in the message. The original implementation used Python substring containment:

```python
if any(phrase in msg_lower for phrase in keywords):
    score += weight
```

This is a false-positive source. A keyword like `"no"` matches `"know"`, `"time"` matches `"sometime"`, `"risk"` matches `"brisk"`. A user saying "I know the timing is tight" would incorrectly accumulate guardedness score from both `"no"` (inside "know") and `"time"` (inside "timing").

### Decision

Replace substring containment with `text_contains_any_keyword()` — the same word-boundary regex function used by every other keyword check in `analysis.py` (intent, commitment, objection, emotional disclosure):

```python
if text_contains_any_keyword(msg_lower, keywords):
    score += weight
```

`text_contains_any_keyword()` compiles keywords into `\b{keyword}\b` patterns (cached via `lru_cache`), enforcing word boundaries. It also skips matches preceded by negation tokens — so "I'm not being defensive" correctly returns 0 score rather than triggering the defensive category.

### Rationale

Consistency matters here because guardedness detection feeds directly into acknowledgment tactic selection (`detect_acknowledgment_context()`) and the `guarded` flag on `ConversationState`. A false-positive guardedness score causes the bot to respond with light acknowledgment ("Got it") in situations where no acknowledgment is warranted — subtly but consistently degrading conversational naturalness. Word-boundary matching eliminates the entire class of partial-word false positives with no performance cost (patterns are cached).

### Trade-off

`text_contains_any_keyword()` performs negation detection, which changes behaviour for negated guardedness phrases: "I'm not being evasive" previously scored 0.5 (evasive category hit); now scores 0.0. This is the correct outcome semantically. No mitigation needed.

## LLM Input Processing

- Recommendation: Do not add Snowball stemming to the runtime LLM input; keep raw user text for generation.
- Rationale: External stemming can distort BPE/subword tokenization and remove semantic cues (tense/negation), reducing generation quality.
- Evidence: See Documentation/LLM_PREPROCESSING_RESEARCH.md for experiment notes and vendor guidance.

---

## Decision 4: Stage-gated objection handling (modularize and enforce at-callsite)

### Summary

Move objection classification and SOP injection out of inline prompt assembly and into a dedicated, stage-gated module so that objection detection and the injection of any scripted SOP steps only occur when the FSM (or caller) explicitly indicates the `objection` stage. This preserves stage isolation, reduces accidental SOP leakage across stages, and centralizes objection SOP data and guards for easier testing and review.

### Alternatives Considered

- Keep objection logic inline inside `content.py` (status-quo prior to modularization).
- Rely purely on LLM/system-prompt constraints to avoid leaking SOP into other stages (pure prompt enforcement).
- Use a decorator or event pipeline to guard objection handling at runtime rather than an explicit module API.

### Rationale

Evidence from the codebase and recent work shows the project benefits from centralizing stage-sensitive behavior:

- Objection classification and SOP assembly are implemented (currently in `src/chatbot/content.py` via `build_objection_context()`), and driven by `objection_flows.yaml`.
- Tests were added to lock the behavior: `tests/test_objection_sop.py` includes `TestStagePromptInjectsSopSteps` and `TestObjectionIsolation` which assert SOP steps are injected only during the objection stage and that the objection builder is not invoked outside the objection stage.
- The FSM and prompt assembly have been hardened in recent commits (see commits such as `a16c9cd` "fix(fsm): harden LOGICAL/EMOTIONAL stages against premature pitching" and `a9afd7b` "refactor(content.py): align to NEPQ methodology, remove prompt redundancies") which demonstrates a repo-level focus on stage correctness and deterministic flow. Centralizing objection handling aligns with this engineering direction.

Centralization improves auditability (single place to inspect how objections are classified and which SOP flows are used), reduces duplication (no multiple inline implementations), and makes it straightforward to add regression tests that prevent accidental behavioral regressions.

### Trade-offs

- Slight indirection: callers must call `build_objection_context()` rather than relying on implicit inline behavior; this increases the number of module boundaries to reason about.
- Risk of circular imports if the caller/import pattern is naive — mitigated by explicit, runtime imports or simple API design (the codebase already uses deferred imports in some places to avoid cycles).
- Requires maintainers to keep the `SOP_FLOWS` YAML and `objection.py` in sync; this is manageable with the existing `load_objection_flows()` loader and tests.

### Implementation Notes / Evidence

- Files: `src/chatbot/content.py` (provides `build_objection_context()` used in `_get_stage_specific_prompt()`), `tests/test_objection_sop.py` (regression tests ensuring isolation), and `src/config/objection_flows.yaml` (SOP data).
- Tests: `TestStagePromptInjectsSopSteps`, `TestObjectionIsolation` — these are the canonical regression guards for this decision.
- Relevant recent commits (context and rationale): `a16c9cd` (FSM hardening), `a9afd7b` (content refactor), `0aad6a1` (initial documentation and decisions scaffold).

### Recommendation

Keep the modular, stage-gated approach. Enforce this with the following practices:

- Maintain `tests/test_objection_sop.py` and expand it when new objection types or SOP steps are added.
- Keep `SOP_FLOWS` data YAML-driven and version-controlled so non-engineers can update SOP language without touching code.
- Add a short note in developer onboarding (README or `ARCHITECTURE_CONSOLIDATED.md`) describing the contract: "Objection classification and SOP injection must only occur via `src/chatbot/content.py` (`build_objection_context()`) and only when the FSM stage == 'objection'."

---

## Consolidated configuration map and intent-summary

Below is a single, concise table linking runtime subsystems to their YAML sources, handlers, and a plain-language description of why each exists.

| Subsystem | YAML source | Handler(s) | Purpose (plain) |
|---|---|---|---|
| Keyword detection | `signals.yaml` | `analysis.py`, `flow.py` | Curated keyword lists used to detect intent, objections and signals so FSM transitions are deterministic and auditable. |
| Objection handling | `objection_flows.yaml` | `content.py` | Centralized objection SOPs that are injected only during the `objection` stage to avoid scripted responses leaking into other stages. |
| Prompt assembly | `adaptations.yaml`, `overrides.yaml` | `loader.py`, `overrides.py` | Layer prompt instructions in a fixed order (overrides → adaptations → baseline) to resolve conflicts and prevent prompt contamination. |
| Prospect simulation | `product_config.yaml`, `prospect_config.yaml` | `prospect.py`, `chatbot.py` | Present product data differently per role (bot: spec; simulated prospect: buyer-research) to avoid ground-truth leakage and preserve realistic discovery. |
| A/B variant assignment | `variants.yaml` | `loader.py` | Deterministic, session-locked variant selection (hash session ID) so users see the same variant across reconnects without a database. |
