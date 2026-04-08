# DONT REMOVE THIS FILE

## Appendix C: Project Development Diary

**Project Overview:** Sales conversation AI chatbot with FSM-driven conversation routing, prompt-based behavioural control, and real-time coaching feedback for sales training.

**Timeline:** September 2025 – April 2026 (28 weeks)

---

### **Weeks 1-8 (Sep 28 – Nov 22): Initial Build — Local LLM, FastAPI, Exploratory Phase**

**What Was Built:**
- FastAPI-based web application with REST API endpoints (initial framework — later replaced by Flask)
- Local LLM integration using HuggingFace `transformers` + `torch` running on CPU
- Basic chat interface with message passing
- SQLite session management (`sessions.db`, `quality_metrics.db`) — later replaced by in-memory dict
- React frontend for chat interface
- Architecture diagrams (.mmd format) planned during Oct 3 sessions
- Iterative UI restructuring (Oct 27 frontend overhaul)

**Problems Encountered:**
- **Inference Latency:** Very high per-response latency on CPU; "slow speed, gonna be optimised" confirmed in commit Oct 2 (`48fb0c1e`). Unacceptable for real-time training tool.
- **Memory Pressure:** Local model consumed significant RAM; limited headroom on development machine
- **Context Window Limitation:** Model truncated conversation context after multiple turns; unable to maintain continuity in multi-turn sales conversations
- **High Latency Root Cause:** Each turn required full prompt assembly across all conversation history + system instructions, then fed through CPU-only inference pipeline
- **Conversational Quality:** Nov 5 commit message explicitly records "bad conversational ai is current" — model responses were unfocused and not sales-relevant
- **Scope Uncertainty:** Initial build had general/fitness coaching framing; sales-specific direction was being established in parallel

**Decisions Made:**
- Abandoned purely local inference approach as primary solution
- Identified cloud API as necessary path forward (Groq was evaluated as primary candidate)
- Accepted cloud API trade-off: responsiveness over offline privacy
- Nov 22: Repository cleaned — SQLite databases, large model files, and external data removed (`a843434106`)

**Why It Mattered:**
- [METRIC_REDACTED] Specific latency targets removed pending verification.
- **Learning:** Local open-source models insufficient for interactive training; cloud APIs mandatory for acceptable UX
- **Project Viability:** Without this pivot, entire tool would be unusable for training purposes
- **Architecture Implication:** Removing local model dependency early freed the stack to be rebuilt cleanly around a cloud provider

---

### **Weeks 9-16 (Nov 22 – Jan 19): Ethics Approval & Planning Phase**

**What Was Built:**
- Ethics approval documentation (GDPR compliance, data handling procedures)
- Data privacy impact assessment
- Security review: identified and documented known limitations (CORS permissive, no auth layer, no HTTPS)
- Project scoping refined: confirmed sales training as primary use case; consultative and transactional strategies as the two conversation modes
- Cloud provider selection finalised (Groq chosen for free tier, low latency, OpenAI-compatible API)

**Note on Commit Gap:** Git history shows no commits from Nov 22 to Jan 20. This period was used for ethics submission and architectural planning before the sales-specific build began.

**Problems Encountered:**
- **Ethics Approval Timing:** Training data collection and user testing required ethics clearance before proceeding
- **Security vs. Functionality:** Production-ready security (HTTPS, authentication, audit logging) time-prohibitive for training system; documented as known limitations

**Decisions Made:**
- Scope training system as development/evaluation tool, not production system
- Document security limitations honestly rather than attempting to close all gaps within FYP timescale
- Decision: **Honesty about limitations** (better to disclose than be caught in assessment)

**Why It Mattered:**
- **Met Module Requirements:** Ethics approval demonstrated responsible project conduct
- **Professional Integrity:** Assessors respect honesty about limitations; hiding them damages credibility

---

### **Week 17 (Jan 20-21): Cloud Migration — Flask + Groq API + Strategy Pattern**

**What Was Built:**
- Complete framework switch: FastAPI replaced by **Flask** (`flask>=3.0.0`); `torch` and `transformers` removed from requirements
- **Groq Cloud API** integrated (`groq>=0.11.0`) — commit Jan 20 (`9e48fad6`): "working simple llm with grok api"
- Offline Vosk speech module removed (commit Jan 20 `1ccf1efdb`)
- **Strategy Pattern architecture** introduced (commit Jan 21 `96770322`):
  - `src/chatbot/chatbot.py` (193 lines) — new sales-specific orchestrator
  - `src/chatbot/strategies/consultative.py` (157 lines) — IMPACT framework stages
  - `src/chatbot/strategies/transactional.py` (82 lines) — budget-focused direct flow
  - `src/chatbot/strategies/prompts.py` — shared base prompt assembly
- `Project-doc.md` created with initial technical report content

**Problems Encountered:**
- **Dataset Parsing Failures:** Open-source sales conversation JSON datasets had inconsistent schema:
  - Some used `"speaker": "agent"/"customer"` while others used `"role": "bot"/"user"`
  - Message content nesting varied: raw text vs. `{"text": "...", "metadata": {...}}`
  - **Impact:** Training data cleaning cost was high; scraping failed on a significant portion of datasets
- **API Rate Limits:** Groq free tier had quota constraints; needed awareness of limits during development

**Decisions Made:**
- Accepted Groq as primary cloud provider; Ollama flagged as potential fallback
- Decided against fine-tuning on open-source datasets due to parsing inconsistency
- Pivoted to: **Prompt engineering over fine-tuning** (zero cost, immediate iteration, cleaner data handling)

**Why It Mattered:**
- [METRIC_REDACTED] Provider latency figures removed pending verification.
- **Learning:** Dataset parsing is a hidden cost; don't assume "open-source = clean"
- **Architecture Resilience:** Separating provider from logic via dependency injection enables future supplier swap

---

### **Week 21 (Feb 15): Architecture Refactoring — Strategy Pattern → FSM**

**What Was Built (single commit `72308ff4`, Feb 15):**
- **Finite State Machine engine** in `src/chatbot/flow.py` (301 lines) — replaces strategy class hierarchy
- Declarative `FLOWS` configuration dictionary with pure-function advancement rules
- `src/chatbot/analysis.py` (389 lines) — complete NLU signal detection layer:
  - `text_contains_any_keyword()` with negation-aware `finditer` loop (`_NEGATIONS` frozenset)
  - `classify_intent_level()` (HIGH/MEDIUM/LOW)
  - `detect_guardedness()`, `detect_acknowledgment_context()`
  - `analyze_state()` including question fatigue detection
- `src/chatbot/content.py` (709 lines) — full prompt assembly with `_SHARED_RULES` P1/P2/P3 hierarchy, STATEMENT-BEFORE-QUESTION table, contrastive tone examples
- `src/chatbot/providers/` — provider abstraction layer (Factory Pattern):
  - `groq_provider.py`, `ollama_provider.py` (both implementing `BaseLLMProvider`)
  - `factory.py` for environment-driven provider selection
- `src/chatbot/performance.py` — latency tracking to `metrics.jsonl`
- `src/config/signals.yaml`, `analysis_config.yaml`, `product_config.yaml` — YAML-driven configuration
- Test suite: `tests/test_all.py`, `tests/test_priority_fixes.py`, `tests/test_human_flow.py`, `tests/test_groq_provider.py`
- `src/chatbot/strategies/` deleted entirely

**Problems Encountered:**
- **High Coupling in Strategy Pattern:** Three strategy files (consultative.py, transactional.py, prompts.py) with tight interdependencies
  - Each stage change required modifying multiple files
  - Test setup required multiple mocks per test case
- **Poor Extensibility:** Non-code users couldn't modify flow without developer involvement
- **Methodology Mismatch:** Strategy Pattern designed for behaviour selection; sales conversation is inherently state-driven (stages, transitions, guards)
- **Permission Question Problem:** Bot ending pitch with permission-seeking questions ("Would you like to hear more?")
  - Root cause: LLM naturally generates polite questions; prompt instructions alone insufficient
  - Attempted fix #1 (prompt only): reduced frequency but remained common
  - Attempted fix #2 (code check): improvement observed but introduced false negatives
  - Final fix: 3-layer enforcement (P1 `_SHARED_RULES` + `check_override_condition()` + regex guardrail)
- **Stage Advancement False Positives:** Keywords like "want", "need", "trying" fired on generic statements
  - Fixed: whole-word boundary regex `\b{keyword}\b` via `_build_union_pattern()`; 11 near-universal verbs removed from `goal_indicators`
- **Tone Mismatches:** Bot used formal register with casual users
  - Fixed: `extract_user_keywords()` rolling lexicon; P2 tone-locking rule; contrastive BAD/GOOD examples in prompt
- **Over-Probing:** Bot asked 2–3 questions per turn during consultative stages
  - Fixed: STATEMENT-BEFORE-QUESTION table in `get_base_prompt()`; P3 max 1–2 questions rule

**Decisions Made:**
- Complete architecture pivot: discard Strategy Pattern; rebuild using FSM
- Move advancement logic to YAML configuration (enable non-technical modification)
- Make advancement rules pure functions (stateless, isolated testing)
- Decision: **Configuration Over Code** + **Layered Enforcement** (prompt for direction, code for guarantees, regex for safety net)

**Why It Mattered:**
- [METRIC_REDACTED] Code size and accuracy deltas removed pending verification.
- **Learning:** Pattern selection must match problem domain; Strategy Pattern added complexity without benefit for state-driven problems
- **Operational Impact:** Non-programmers can now modify sales flow by editing YAML; no developer required
- **Quality Gate:** Test suite created in same commit — established regression baseline immediately

---

### **Weeks 22-23 (Feb 15 – Mar 7): Testing, Polish & Knowledge Base**

**What Was Built:**
- Iterative fixes to FSM advancement logic (commits Feb 15-17)
- Mobile compatibility + CSS polish (Mar 2 commits)
- `src/chatbot/knowledge.py` — custom product knowledge CRUD (commit Mar 1, `7d10fe41`)
- Gunicorn added to requirements for Render deployment (Mar 1)
- Training component introduced (commit Mar 6, `b148013c`): coaching feedback generation
- `analysis.py` heavily refactored (Mar 6): aligned to YAML-driven config patterns
- `flow.py` refactored (Mar 6): tightened advancement rules

**Problems Encountered:**
- **Guardedness Detection Edge Cases:** A small number of cases where bot couldn't distinguish user being polite vs. genuinely interested; user being cautious vs. objecting
  - Documented as **accepted technical debt** (requires discourse analysis beyond FYP scope)
- **Test Infrastructure Brittleness:** Some tests required LLM provider mocks; refactored to pure functions to reduce mock surface area

**Decisions Made:**
- Fixed false positives: whole-word regex + context-window guard (keywords tested only against current-stage messages)
- Documented known edge cases honestly — professional engineering acknowledges limitations
- Decision: **Measure ruthlessly** (test suite became quality baseline; can't improve what you don't measure)

**Why It Mattered:**
- [METRIC_REDACTED] Accuracy and pass-rate numbers removed pending verification.
- **Regression Prevention:** Comprehensive test coverage prevents accidental breakage during future changes

---

### **Weeks 24-25 (Mar 8 – Mar 21): NEPQ Alignment, Documentation & Evaluation Infrastructure**

**What Was Built:**
- NEPQ (Neuro-Emotional Persuasion Questioning) methodology fully aligned to stage prompts in `content.py` (commit Mar 10, `a9afd7bb`)
- `Project-doc.md` expanded massively: ASPECT 2 completion, project timeline, FSM bug fix snippet, appendices (commits Mar 10-14)
- Security layer added: `security.py`, `SessionSecurityManager`, `_DEBUG_ENABLED` guard on `/api/debug/*` (Mar 12)
- Dummy provider for testing added (Mar 12)
- Dev panel added (Mar 14)
- Session analytics module `src/chatbot/session_analytics.py` (234 lines) — stage transitions, intent distribution, objection types (Mar 21, `313978bc`)
- `Documentation/ARCHITECTURE_CONSOLIDATED.md` (1473 lines) — full architectural reference (Mar 21)
- `Documentation/technical_audit.md` — 10-issue external audit with fix/defer/reject decisions (Mar 21)
- Quiz engine + prospect mode (Mar 21)
- A/B variant infrastructure (`variants.yaml`, `assign_ab_variant()`) for controlled evaluation (Mar 21)

**Problems Encountered:**
- **Documentation Lag:** Code completed before documentation; hard to recall rationale months later
- **Demo Preparation:** Translating technical decisions into 40-minute narrative for non-technical assessors
- **Dual Session Management Bug:** Two separate session dicts + lock + cleanup thread found; unified under `SessionSecurityManager` (technical audit fix #1)
- **Double LLM Call in Prospect Mode:** LLM-based rating per turn replaced with deterministic `_score_sales_message()` using keyword signals (technical audit fix #2)

**Decisions Made:**
- Narrative-first documentation: decisions recorded as problem → solution → why it matters
- Technical audit conducted; 3 issues fixed, 4 deferred (low ROI), 2 rejected (out of scope)
- Decision: **Exposition matters as much as implementation** (mark scheme: 40-minute demo significant portion of grade)

**Why It Mattered:**
- **Learning:** Professional software engineering includes communication; coding skill insufficient without ability to articulate decisions
- **Evaluation Support:** Session analytics provides empirical data for evaluation chapter; A/B infrastructure enables controlled comparison

---

### **Weeks 26-28 (Mar 22 – Apr 6): Voice Mode, Final Features & Submission Preparation**

**What Was Built:**
- Voice mode: prospect, session, and voice routes (`voice.py`) — commit Mar 28 (`f6e8c167`)
- Evaluation modules fully integrated — commit Apr 1 (`789f21622`)
- `src/chatbot/prospect/prospect.py` refactored into dedicated submodule (Apr 1)
- `src/chatbot/analytics/session_analytics.py` moved to dedicated analytics subpackage (Apr 1)
- Architecture diagram suite refined: 10 Mermaid diagrams corrected and semantically validated (Apr 2-6)
- User feedback collection finalised (structured questionnaire; friends, classmates, non-professionals)
- Final demo rehearsal + Q&A preparation

**Problems Encountered:**
- **User Feedback Gap:** Initial evaluation relied only on personal testing; lacked external validation
- **Scope Creep:** Temptation to keep optimising vs. knowing when to lock scope

**Decisions Made:**
- Recruited real testers; structured evaluation with tone, topic adherence, naturalness scales
- Locked scope at Week 26; final weeks for documentation polish and diagram cleanup only
- Decision: **Evidence-based Evaluation** (mark scheme requires "user feedback obtained systematically")

**Why It Mattered:**
- **Mark Scheme Requirement:** 60-69% Evaluation band explicitly requires systematically obtained user feedback; developer-only testing insufficient
- **Learning:** Systematic evaluation transforms "I think it works" to "users confirmed it works"

---

## **Risk Incidents**

**2025-10-02 — R1 (first occurrence):** Local model latency confirmed unacceptable. Every turn was taking several seconds on CPU; couldn't demo or evaluate it at that speed. Decided to move to a cloud API — Groq was the obvious choice given the free tier. Resolved Jan 20 when the full local stack (torch, transformers, accelerate) was replaced with groq + flask in one commit.

**2026-01-21 — R7:** Strategy Pattern was already causing problems after one session. Any stage change meant touching consultative.py, transactional.py, and prompts.py in parallel; adding a test meant mocking all three. Decided to scrap it and rebuild as an FSM with a declarative config instead. Took about 25 days (resolved Feb 15). No deadline impact.

**2026-02-15 — R2:** When writing the test suite, caught that "I want to make money" was advancing the FSM to pitch — the word "want" matched regardless of context. Same issue with negations: "I don't need this" was still triggering intent signals. Fixed the same day: whole-word regex, negation-aware matching, and removed 11 near-universal verbs from the keyword config. Negation false positives dropped to zero across targeted test cases.

**2026-03-24 — R1 (second occurrence):** Groq free-tier rate limit hit during testing. Added a second API key and automatic rotation on 429 — the provider abstraction from Feb meant this was a single-file change in groq_provider.py, nothing else needed touching.

**2026-03-21 — R4 (partial):** Quiz, prospect mode, session analytics, and voice scaffolding all landed in the same week — late in the project. Useful for the evaluation chapter but meant documentation and testing were running in parallel with delivery. Locked scope after Mar 28; last two weeks were diagrams and polish only.

---

## **Key Themes Across Project Lifecycle**

| Phase | Problem Type | Approach | Learning |
|-------|------|----------|---------|
| **Weeks 1-8** | Technical Constraint | Pragmatic Pivot | Local CPU inference insufficient; cloud APIs necessary for interactive tools |
| **Weeks 9-16** | Process & Ethics | Planning Phase | Ethics clearance gates evaluation work; plan for the gap |
| **Week 17** | Data Quality | Config-Driven Design | Open datasets often inconsistent; prompt engineering more reliable than fine-tuning |
| **Week 21** | Architectural Fit | Pattern Selection + Layered Control | FSM matches state-driven domain; single-layer prompt fixes insufficient |
| **Weeks 22-23** | Measurement | Systematic Testing | Testing reveals assumptions; metrics-driven refinement mandatory |
| **Weeks 24-25** | Maintainability + Communication | SRP + Narrative-First Docs | Architectural clarity + exposition skill both required for high marks |
| **Weeks 26-28** | Evaluation | Evidence-Based Feedback | External tester data converts subjective claims to measurable evidence |

---

## **Reflection: What I Would Do Differently**

1. **Establish test scenarios on Day 1** — Would have saved significant iteration cycles; early regression detection would have caught FSM false-positive bugs before they compounded
2. **Allocate significant time to prompt engineering from start** — Discovered late that this was the highest-leverage effort; the 3-layer enforcement system should have been designed upfront
3. **Use configuration-driven design from beginning** — Would have avoided the Strategy Pattern intermediate step entirely (Jan 21 – Feb 15 could have gone straight to FSM)
4. **Document decisions as they happen** — Harder to recall rationale months later; diary should be written weekly alongside commits, not reconstructed at end
5. **Start ethics submission earlier** — The ~8-week gap (Nov 22 – Jan 20) was partly caused by ethics clearance timing; earlier submission would have allowed earlier build start

---

## **Estimated Grade Impact by Phase**

[METRIC_REDACTED] Specific grade-impact percentage estimates removed pending verification.

---

**Timeline Notes (Git-Verified):**
- All dates above are verified against git commit history (`git log --oneline --format="%ad %s" --date=short`)
- Key reference commits: `5afe843e` (Sep 28 first commit), `9e48fad6` (Jan 20 Groq), `967703220` (Jan 21 Strategy Pattern), `72308ff4` (Feb 15 FSM), `7d10fe41` (Mar 1 knowledge.py), `b148013c` (Mar 6 training), `313978bc` (Mar 21 analytics/quiz), `b561339` (Apr 6 final diagrams)
