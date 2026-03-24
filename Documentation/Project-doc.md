# TABLE OF CONTENTS

**Abstract**

**1. Context, Exploration & Rationale**
- 1.1 Problem Domain & Business Context
- 1.2 Technical Exploration & Previous Approaches
- 1.3 Research Question & Architectural Hypothesis
- 1.4 Sales Structure Foundation
- 1.5 Critical Analysis & Competitive Differentiation
- 1.6 Project Objectives

**2. Project Process & Professionalism**
- 2.1 Architecture & Design
- 2.2 Iterative Development & Prompt Engineering
- 2.3 Implementation Details
- 2.4 Risk Management
- 2.5 Professional Practice
- 2.6 Monitoring, Effort & Estimation
- 2.7 Ethics & Security

**3. Deliverable**
- 3.1 Implementation Outcomes
- 3.2 Testing & Validation (including UAT)
- 3.3 Known Limitations

**4. Evaluation**
- 4.1 Requirement Satisfaction
- 4.2 Evaluation Methodology
- 4.3 Theoretical Validation
- 4.4 Strengths
- 4.5 Weaknesses & Trade-Offs

**5. Reflection**
- 5.1 Personal Reflection
- 5.2 Key Lessons
- 5.3 Future Work
- 5.4 Research Directions

**6. References**

**7. Appendices**
- Appendix A: Iterative Case Studies
- Appendix B: UAT Supporting Data
- Appendix C: Project Development Diary

# LIST OF ACRONYMS

| **Acronym** | **Definition** |
|---|---|
| API | Application Programming Interface |
| CoT | Chain-of-Thought (prompting technique) |
| FSM | Finite-State Machine |
| LLM | Large Language Model |
| NEPQ | Neuro-Emotional Persuasion Questioning (Miner, 2023) |
| NLU | Natural Language Understanding |
| RLHF | Reinforcement Learning from Human Feedback |
| SPIN | Situation, Problem, Implication, Need-Payoff (Rackham, 1988) |
| SRP | Single Responsibility Principle |
| UAT | User Acceptance Testing |
| YAML | YAML Ain't Markup Language |

---

# ABSTRACT

Sales training is effective but expensive and difficult to scale. Online alternatives lack live conversational practice. I built an AI chatbot that simulates a prospect in a structured sales conversation, enabling salespeople to practise methodology on demand without a human trainer.

The system uses a hybrid architecture: a finite-state machine (FSM) enforces NEPQ sales methodology stage progression deterministically, while a cloud-hosted large language model (Groq API, Llama 3.3 70B) generates natural conversational responses within each stage's constraints. This separation was not the starting point — it emerged from two failed prototypes. A local LLM (Qwen 2.5-1.5B) produced five-minute response times and role confusion. A keyword-matching system solved latency but could not adapt tone or handle novel phrasing.

The resulting system comprises approximately 5,200 lines of Python, 1,200 lines of HTML/JS, and 2,000 lines of YAML configuration across 24 modules and 7 configuration files, deployed at zero cost on Render and Groq free tiers. All 395 automated tests pass. Measured response latency averages 462ms (P95: 1,768ms) across 491 recorded turns.

The architecture demonstrates that FSM-enforced stage gating combined with prompt-constrained LLM generation can produce reliable methodology adherence without fine-tuning or proprietary models — a finding with broader implications for any domain where conversational structure matters more than conversational freedom.

---

# 1. Context, Exploration & Rationale

## 1.1 Problem Domain & Business Context

The global corporate training market is valued at approximately $345 billion USD (Grand View Research, 2023). Three specific inefficiencies in the sales training segment motivated this project.

**Cost.** For a 10-person SME team, a single round of individual roleplay sessions costs £3,000–£5,000. The Association for Talent Development (ATD, 2023) reports median annual training spend of around £1,000 per sales representative — meaning most SME teams cannot afford to repeat live roleplay practice beyond an initial programme.

**Scalability.** Human trainer roleplays operate at a hard 1:1 ratio. Scaling to 50 concurrent reps requires 50 trainers or sequential booking slots. Neither is operationally viable for organisations that need consistent, repeatable practice across a team.

**Engagement.** E-learning voluntary completion rates sit below 15% (Jordan, 2015), and completion does not equal competency. Sales is a reactive skill — technique only transfers under the pressure of a live objection. Watching a video of someone handling an objection is categorically different from being forced to handle one yourself. Kirkpatrick's four-level evaluation model (Kirkpatrick and Kirkpatrick, 2006) distinguishes reaction (Level 1) from behaviour change (Level 3); most e-learning captures only reaction-level engagement.

This project targets three stakeholder groups:

- **SME sales teams** need low-cost, repeatable practice without waiting for trainer availability.
- **Corporate L&D teams** need consistent, measurable conversation quality across larger cohorts.
- **Individual sales professionals** need self-directed rehearsal with immediate coaching feedback.

The research opportunity is clear: if an AI system can enforce structured sales methodology while generating natural conversational responses, it could address all three constraints simultaneously — at near-zero marginal cost per session.

## 1.2 Technical Exploration & Previous Approaches

The path to the final architecture was shaped by two failed prototypes, each of which eliminated an approach and clarified what the solution required.

**Hardware constraints.** Development was conducted on a Lenovo ThinkPad (Intel i7-8550U, 11 GB RAM total, ~3 GB available at runtime with Windows and VS Code consuming ~8 GB, 4 GB dedicated VRAM). This constraint was not incidental — it ruled out local LLM inference as a viable production path.

**Iteration 1: Local LLM (September–November 2025).** I built a prototype using HuggingFace Transformers with Qwen 2.5-1.5B. The codebase grew to over 470 files including a React frontend, SQLite databases, five analyzer services, and a training pipeline. It failed in several interconnected ways:

- **Latency**: 3–5 minute response times per turn. The 4 GB VRAM was below the 6–8 GB minimum for efficient 1.5B inference, forcing CPU-offloaded execution. Background threading and context truncation did not help because the constraint was hardware-fundamental, not configurational.
- **Context loss**: A 1.5B parameter model lacks the representational capacity to simultaneously maintain a consistent buyer persona, adhere to NEPQ stage constraints, and track multi-turn context. Research confirms that instruction-following fidelity scales with model size; sub-3B models frequently exhibit these failure modes under multi-constraint loads (Brown et al., 2020).
- **Role confusion**: The model intermittently generated salesperson responses instead of maintaining the prospect persona. For a training tool, this is a credibility failure — reps would be practising against an incoherent character rather than a realistic buyer.
- **Output quality**: Responses truncated mid-sentence due to a hard `max_new_tokens` cap, and without proper EOS token handling, the model had no reliable signal for when to stop generating.

The iteration ended with commit `a843434` (22 November 2025): "Clean repository — remove all external data and large files", deleting over 100 files. The approach was abandoned, not evolved.

**Speech-to-text evaluation.** A voice-first pipeline using OpenAI's Whisper was evaluated but deliberately excluded. Phase 1 had already identified latency as a critical failure. Adding real-time audio streaming, voice activity detection, and Whisper inference would have introduced 8+ new integration points. The research question centred on methodology adherence via FSM+LLM control, not voice interface fidelity. Voice remains a scoped extension (Section 5.3).

**Iteration 2: Fuzzy matching (November 2025–January 2026).** I replaced the LLM with deterministic keyword-based response templates using fuzzy string matching. This solved latency entirely and achieved 100% stage sequencing adherence. However:

- **Response rigidity**: Every matched intent triggered the same fixed reply regardless of context. "I can't afford that" and "what's the price range?" produced identical responses.
- **No tone adaptation**: The system had no concept of register — a casual opener and a formal enquiry generated the same scripted output.
- **Keyword brittleness**: Slight phrasing variation broke intent detection entirely.

The critical insight was that stage control was already behaving like a state machine; only response generation needed flexibility. This directly motivated the hybrid architecture.

**Transition to current system.** Commit `9e48fad` (20 January 2026, "working simple llm with grok api") marked the pivot. The 470-file codebase was replaced by three files: `app.py`, `chatbot.py`, and `test_groq_model.py`. Lines deleted: 63,776. Dependencies reduced from transformers, torch, LangChain, and SQLite to Flask and groq.

## 1.3 Research Question & Architectural Hypothesis

The prototyping evidence showed that neither a pure LLM approach nor deterministic templates were sufficient on their own. The LLM generated natural language but could not be trusted with stage control. The keyword matcher controlled stages perfectly but could not generate natural responses.

**Research question:** Can structured prompts plus FSM-enforced stage gating produce reliable sales-methodology adherence without fine-tuning?

**Architectural hypothesis:**
1. Deterministic structure should be enforced in code (FSM controls *when* to advance).
2. Natural language variation should be delegated to the LLM (LLM controls *what* to say).
3. Transitions should depend on explicit user signals, not turn counts or LLM-inferred intent.

I chose prompt engineering over fine-tuning deliberately. Fine-tuning would require 500+ labelled conversations, £300–500 in GPU compute (estimated from Vast.ai pricing), and 48+ hours per iteration cycle. Prompt engineering requires none of this: changes are instant, portable across any LLM API, and reversible. The trade-off is that prompt-based control plateaus at lower theoretical accuracy than fine-tuned weights — but for an FYP-scoped system where I control the evaluation conditions, this trade-off was clearly favourable. The viability of prompt-based instruction following without fine-tuning is established in Brown et al. (2020); the low-rank adaptation alternative is described in Hu et al. (2022).

## 1.4 Sales Structure Foundation

I did not impose a theoretical framework top-down. Literature was consulted specifically to resolve emergent behavioural failures observed during testing. Each theory was adopted because it solved a concrete problem:

**SPIN Selling (Rackham, 1988)** solved false stage advancement. The bot was advancing after N turns regardless of content, producing ~40% false positives. Rackham's prerequisite-chain model — where each question type (Situation, Problem, Implication, Need-Payoff) must precede the next — provided the structure for keyword-gated advancement in `flow.py`. The FSM now requires explicit doubt signals before progressing from Logical to Emotional stage.

**NEPQ / Neuro-Emotional Persuasion Questioning (Miner, 2023)** solved objection handling quality. The bot was generating counter-arguments to objections — addressing rational justification rather than emotional triggers. NEPQ's approach, informed by Kahneman's dual-process theory, reframed the objection prompt to probe for emotional cost rather than logical rebuttal. The implementation uses a CLASSIFY→RECALL→REFRAME→RESPOND scaffold in the objection prompt.

**Constitutional AI (Bai et al., 2022)** solved permission question leakage. The LLM's RLHF training created strong priors to end statements with permission-seeking questions ("Would you like to hear more?"). A three-layer constraint hierarchy (P1: hard rules, P2: stage-specific rules, P3: soft guidance) in all stage prompts eliminated this. Before: 75% of pitch responses contained trailing questions. After: 0%.

**Chain-of-Thought prompting (Wei et al., 2022)** improved objection reasoning. The bot knew *what* to do on objections but not *how* to reason through them. Embedding explicit IDENTIFY→RECALL→CONNECT→REFRAME steps in the objection prompt improved appropriate reframing from 65% to 88% across test scenarios.

**Lexical entrainment (Brennan and Clark, 1996)** solved mechanical parroting. The bot was rephrasing the prospect's words with synonyms, breaking the sense of being understood. `extract_user_keywords()` in `analysis.py` now injects the prospect's exact terms into prompts, creating what Brennan and Clark call "conceptual pacts."

**Conversational repair (Schegloff, 1992)** solved over-probing. The bot continued probing after signals like "just show me the price." `user_demands_directness()` in `analysis.py` detects frustration signals and triggers an FSM jump directly to the Pitch stage, implementing Schegloff's principle that repair must be immediate when intersubjectivity breaks down.

## 1.5 Critical Analysis & Competitive Differentiation

| **Platform** | **Strength** | **Limitation** | **Cost** |
|---|---|---|---|
| Conversica | Lead qualification + CRM integration | Customer-facing nurture tool, not a practice simulator; no methodology enforcement | $1,500–$3,000/month |
| Chorus.ai / Gong | Call recording analytics; pattern detection | Post-call analysis only; no live rehearsal | ~$35K+/year |
| Hyperbound | AI roleplay with voice personas | Conversational fluidity over structured methodology; proprietary black-box | Enterprise pricing |
| Showpad Coach | LMS integration; video coaching | Asynchronous format; no real-time practice | Enterprise pricing |
| Human roleplay | Highest interaction quality | Does not scale; trainer availability constraint | $300–$500/session (ATD, 2023) |

**Project differentiation.** None of these tools enforce a specific sales methodology deterministically. Conversica and Gong operate post-hoc. Hyperbound prioritises fluidity over structure. This project is the only system I found that separates control (FSM) from generation (LLM) with auditable stage gates — meaning an L&D manager can inspect exactly why the bot advanced from Logical to Emotional stage by reading the FSM trace, something no black-box system offers.

**The AI training paradox.** The core risk of an unstructured LLM for sales training is not that it fails to teach — it is that it actively teaches the wrong behaviour. A bot that skips discovery, jumps to pricing before establishing pain, or folds on objections without probing trains reps to do the same. The failure pattern gets reinforced, not corrected. Conversational fluency without methodology enforcement is a fluency simulator, not a training tool. This is precisely why the FSM constraint layer exists.

## 1.6 Project Objectives

Requirements evolved during development. Voice pipeline and local-only inference were dropped after technical feasibility checks (Section 1.2). Urgency override and rewind/replay were added from observed user needs during testing.

| **ID** | **Objective (SMART)** | **Measure** | **Target** | **Timeframe** |
|---|---|---|---|---|
| O1 | **NEPQ Methodology Adherence**: Achieve ≥85% correct FSM stage transitions across 25 structured test conversations, with no stage skipping or hallucinated transitions, validated before final submission | Count (correct transitions / total transitions) across fixed scenario set | ≥85% stage progression accuracy | By end of Phase 4 (testing) |
| O2 | **Persona Emulation**: Achieve ≥90% tone-appropriate responses when tested against 12 distinct buyer personas (casual, formal, technical, price-sensitive, etc.) using manual developer assessment | Manual formality alignment check: does response register match persona register? | ≥90% tone alignment across 12 personas | By end of Phase 4 |
| O3 | **Real-Time Latency**: Achieve <2000ms P95 response latency across all recorded conversation turns, measured automatically via `metrics.jsonl` performance logs | Automated: P95 of `latency_ms` field across all logged turns | <2000ms P95 | Continuous; validated at submission |
| O4 | **Rule Enforcement**: Eliminate 100% of LLM-generated permission-seeking questions ("Would you like...?") in Pitch stage output, validated by regex scan across all pitch-stage test responses | Automated regex `r'\s*\?\s*$'` on pitch-stage outputs | 0% trailing questions in pitch | By end of Phase 2 (prompt tuning) |
| O5 | **Zero-Cost Operation**: Deploy and operate the system at £0 marginal cost per session using free-tier cloud services, with confirmed provider fallback capability | Architectural review: verify Groq free tier + Render free tier; test fallback via env-var switch | £0 marginal cost; fallback confirmed | By deployment |
| O6 | **Assessment Module**: Deliver a quiz system that tests users' recognition of NEPQ stages and appropriate next steps, with 100% automated test pass rate across all quiz logic | `pytest tests/` pass rate for quiz-specific test module | 100% (26/26 quiz tests) | By end of Phase 3 |

**Constraint-derived requirements.** Constraints from Iterations 1 and 2 directly shaped requirements:
- Hardware limits forced cloud-first provider strategy and fallback abstraction (O5).
- Unreliable unconstrained progression required deterministic stage control (O1).
- Manual maintenance cost required configurable, non-code behaviour tuning (NF5).

**Functional Requirements:**

| **ID** | **Requirement** | **Implementation** | **Primary Stakeholder(s)** |
|---|---|---|---|
| R1 | Manage conversation through an FSM with defined stages, sequential transitions, and configurable advancement rules based on user signals | `flow.py`: FLOWS config, `SalesFlowEngine`, `_check_advancement_condition()` | All three groups |
| R2 | Support two sales flow configurations — consultative (5 stages) and transactional (3 stages) — selectable per product via YAML | `flow.py`: FLOWS dict, `product_config.yaml` | Corporate L&D; SME Sales Teams |
| R3 | Generate stage-specific LLM prompts that adapt to detected user state (intent level, guardedness, question fatigue) | `content.py`, `prompts.py`: stage-specific prompt templates with dynamic context injection | All three groups |
| R4 | Detect and respond to user frustration by overriding normal progression (skip to pitch) | `analysis.py`: `user_demands_directness()`, `flow.py`: urgency override | Individual Sales Professionals |
| R5 | Provide web chat interface with session isolation, conversation reset, and message edit with FSM state replay | `app.py`, `chatbot.py`: `rewind_to_turn()` | Individual Professionals; Corporate L&D |
| R6 | Preserve maintainability through artefact traceability and low-risk configuration updates | YAML configs, test suites, `Documentation/Artifact-Traceability.md` | All three groups |

**Non-Functional Requirements:**

| **ID** | **Requirement** | **Target** |
|---|---|---|
| NF1 | Response latency (P95) | <2000ms |
| NF2 | Infrastructure cost | £0 marginal |
| NF3 | Session isolation | Complete (no cross-session data leakage) |
| NF4 | Error handling | Graceful (no hard crashes on expected errors) |
| NF5 | Configuration flexibility | YAML-based (zero code changes for signal/product updates) |
| NF6 | Maintainability | Deterministic replay and regression-backed updates |

**Software lifecycle coverage:** Requirements are defined here with stakeholder mapping. Design rationale and architecture comparisons appear in Section 2.1. Implementation details in Sections 2.3 and 3.1. Verification via automated tests, manual scenarios, and UAT in Section 3.2. Maintenance through YAML-driven configuration and traceable refactoring in Section 2.5.

---

# 2. Project Process & Professionalism

## 2.1 Architecture & Design

### 2.1.1 Why FSM Over Strategy Pattern

The Strategy Pattern was the first architectural approach I tried for managing conversation flow. It is designed for dynamic algorithm selection at runtime — choosing between sorting algorithms, for example. The problem here was sequential state flow where transitions depend on explicit user signals, not dynamic dispatch. Using Strategy Pattern for what is fundamentally a state machine problem created structural mismatch:

- Logic was fragmented across 5 files; every feature change required tracing imports through multiple modules.
- Code reviews took ~45 minutes per feature because the reviewer had to reconstruct the flow mentally.
- Shared imports between strategy classes created hidden coupling — changing one strategy could break another.

The FSM refactor consolidated flow logic into `flow.py` (322 lines). Transition guards are declared in a single `FLOWS` dictionary:

```python
FLOWS = {
    Strategy.CONSULTATIVE: {
        "stages": [Stage.INTENT, Stage.LOGICAL, Stage.EMOTIONAL, Stage.PITCH, Stage.OBJECTION],
        "transitions": {
            Stage.INTENT: {
                "next": Stage.LOGICAL,
                "advance_on": "user_has_clear_intent"
            },
            Stage.LOGICAL: {
                "next": Stage.EMOTIONAL,
                "advance_on": "user_shows_doubt",
            },
            # ... each stage has explicit guard condition
        }
    }
}
```

This is auditable in a way the Strategy Pattern was not: an examiner can read the `FLOWS` dictionary and understand every possible state transition without reading any other file.

### 2.1.2 Drift Prevention as Design Principle

The primary design objective was preventing uncontrolled stage transitions — what I call "hallucinated stage adherence," where the bot advances to later stages before the user has met prerequisites. During Iteration 1 testing, the LLM would jump from Intent directly to Pitch roughly 40% of the time. In the final architecture:

- Only FSM guards can transition stage. The LLM generates language within the active stage's constraints but cannot alter the stage itself.
- Transitions depend on explicit user signals detected via the NLU pipeline in `analysis.py`, not turn counts or LLM-inferred intent.
- Stage prompts include P1/P2/P3 constraint hierarchies (adapted from Constitutional AI) that override RLHF politeness defaults.

This separation means a syntactically fluent but behaviourally drifted LLM response cannot derail methodology progression. The FSM holds stage until valid advancement signals are detected.

### 2.1.3 Consultative State Model

The FSM enforces the five-stage NEPQ consultative flow. Each transition has an explicit guard condition. The advancement logic for the Logical and Emotional stages uses a shared helper function that checks for specific signal keywords from YAML configuration:

```python
def _check_advancement_condition(history, user_msg, turns, stage_name, min_turns=2):
    """Generic advancement detector: check config keywords + safety valve."""
    if turns < min_turns:
        return False

    stage_config = _ANALYSIS_CONFIG.get('advancement', {}).get(stage_name, {})
    keywords = stage_config.get(keyword_key, [])
    max_turns = stage_config.get('max_turns', 10)

    # Check only messages from current stage window
    recent_stage_msgs = user_msgs[-max(turns, 0):] if turns > 0 else []
    recent_text = " ".join(recent_stage_msgs)
    has_signal = text_contains_any_keyword(recent_text, keywords)

    return has_signal or turns >= max_turns  # Safety valve for resistant prospects
```

The `min_turns` guard prevents premature advancement; the `max_turns` safety valve prevents infinite loops when a prospect is deliberately resistant. Both thresholds are configurable in `analysis_config.yaml` without code changes. The consultative flow progresses: Intent → Logical → Emotional → Pitch → Objection. A separate transactional flow (Intent → Pitch → Objection) skips emotional probing for budget-focused conversations, selectable per product via `product_config.yaml`.

SRP refactoring extracted training, knowledge, and analysis responsibilities from `chatbot.py` into separate modules. This was not premature abstraction — it was reactive. God-class anti-patterns in `chatbot.py` were causing hidden regressions during prompt tuning: changing a prompt for the Emotional stage inadvertently affected objection handling because both shared state in the same class.

## 2.2 Iterative Development & Prompt Engineering

### 2.2.1 The Iteration Method

Drift was not solved in one pass. The final system is the result of multiple observe–hypothesise–fix–validate cycles. I will describe the three most significant iterations in detail here; additional case studies with code snippets appear in Appendix A.

**Iteration A: Permission question elimination.** The LLM's RLHF training created a strong prior to end pitch responses with questions like "Would you like to hear more about that?" — which in real sales breaks momentum at the critical closing moment. Initial prompt instructions ("Do not end with a question") reduced occurrence from ~100% to ~75% but did not eliminate it.

I applied a layered approach inspired by Constitutional AI's constraint hierarchy (Bai et al., 2022):
- **P1 (hard rule)**: Prompt text "DO NOT end your response with a question mark."
- **P2 (stage-specific)**: Pitch-stage prompt explicitly models the correct closing pattern — assumptive, not permission-seeking.
- **P3 (output contract)**: Regex `r'\s*\?\s*$'` catches any residual trailing questions and strips them before delivery.

Result: 0% permission questions across all subsequent test scenarios. The three layers are necessary because prompts alone cannot fully override RLHF priors — the regex provides a deterministic backstop.

**Iteration B: False stage advancement.** The FSM was advancing from Intent to Logical on near-universal words like "want to," "need to," and "trying to." The `goal_indicators` list in `analysis_config.yaml` originally contained 11 verbs so common that almost any user utterance triggered intent lock. I audited the keyword list, removing verbs that appeared in >80% of casual conversation ("want to," "need to," "fix," "improve") and retaining only specific buying signals ("struggling with," "looking to buy," "ready to purchase"). Combined with whole-word regex matching (`\bword\b`) to prevent substring false positives, this reduced false advancement from ~40% to <8%.

**Iteration C: Tone mismatch across personas.** The bot initially responded identically regardless of whether the user was casual ("yo, I need a car") or formal ("I'm enquiring about vehicle options"). I implemented two mechanisms:
1. `extract_user_keywords()` in `analysis.py` captures the user's exact phrasing and injects it into the prompt — implementing lexical entrainment (Brennan and Clark, 1996).
2. Four few-shot examples in each stage prompt demonstrate appropriate register variation — implementing Brown et al.'s (2020) finding that few-shot examples achieve 85–90% of fine-tuned performance.

This improved tone alignment from 62% to 95% across 12 test personas.

### 2.2.2 Why Layered Control, Not Just Better Prompts

Across all iterations, the dominant failure class was drift: outputs that were syntactically fluent but misaligned with the required stage intent. The key insight was that **prompts alone cannot fully constrain LLM behaviour**. The model's RLHF training creates strong priors that override explicit prompt instructions in edge cases.

The solution was layered control:
- **Prompt constraints** (soft): Guide the model's generation direction.
- **FSM guards** (hard): Block stage transitions until user signals are detected.
- **Output contracts** (hard): Regex-based post-processing catches remaining violations.

Prompt-only attempts plateaued at ~70% compliance. The three-layer stack achieved near-complete drift containment. This is the project's core technical contribution and directly answers the research question: prompt engineering alone is insufficient, but prompt engineering *plus* deterministic structural control is sufficient.

**Measurement methodology.** Stage accuracy was calculated as (correct FSM transitions / total observed transitions) across 25 developer-executed test scenarios. "Correct" means: (a) stage advanced only when advancement rules were satisfied, and (b) no stage was skipped without meeting prerequisite signals. All baseline metrics were captured before the fix; achieved metrics captured after, using the same scenario set.

## 2.3 Implementation Details

The provider abstraction prevented architecture lock-in when Groq API rate limits were hit mid-development. Instead of rewriting orchestration code, I switched providers via a factory configuration — a single environment variable change:

```python
# providers/factory.py
def create_provider(provider_type=None, model=None):
    provider_type = provider_type or os.environ.get("LLM_PROVIDER", "groq")
    if provider_type == "groq":
        return GroqProvider(model=model)
    elif provider_type == "openrouter":
        return OpenRouterProvider(model=model)
    elif provider_type == "dummy":
        return DummyProvider()
```

All providers implement `BaseLLMProvider` with a single `chat()` method returning an `LLMResponse` (text + latency). This interface contract means the rest of the system — FSM, analysis, prompts — is completely provider-agnostic.

| **Provider** | **Strength** | **Limitation** | **Use** |
|---|---|---|---|
| Groq (primary) | Fast, free tier, high-quality responses | External API dependency | Default interactive usage |
| OpenRouter (backup) | Multiple model access, redundancy | Variable latency by model | Fallback when Groq unavailable |
| Dummy | Deterministic, no API calls | No real language generation | Automated testing |

Design additions integrated into the same architecture without requiring core changes:
- **Trainer panel** (`trainer.py`, 137 lines) shares analysis context with the main chatbot, so coaching does not bypass drift controls.
- **Quiz module** (`quiz.py`, 359 lines) reuses FSM stage semantics to test methodology understanding.
- **Prospect mode** (`prospect.py`, 473 lines) reverses roles — the bot acts as a difficult buyer and the user practises as the salesperson, scored by a deterministic evaluator (`prospect_evaluator.py`, 135 lines).
- **Rewind/replay** (`chatbot.py`: `rewind_to_turn()`) supports maintenance by allowing deterministic re-evaluation of turns after message edits.

## 2.4 Risk Management

These risks were identified during Iteration 1 prototyping and directly informed architecture decisions — they were not written retrospectively.

| **Risk** | **Prob.** | **Impact** | **Mitigation** | **Outcome** |
|---|---|---|---|---|
| R2: Uncontrolled stage drift | High | High | FSM stage gates + NLU signal detection + layered control | Core architecture decision; drift reduced from >40% to <8% |
| R1: Provider/API availability disruption | Medium | High | Provider abstraction and fallback | Groq rate-limit hit mid-development; OpenRouter activated via 1 env-var change |
| R3: Prompt constraint failure in edge cases | Medium | Medium | Layered control (prompt + FSM + regex) | Permission question removal achieved 100% |
| R4: Schedule overrun from iteration volume | Medium | Medium | Weekly metrics and scope compression | +10h overrun (16%); absorbed within phase budgets |
| R5: Weak independent validation | High | Medium | UAT plan and post-submission validation | Documented as limitation; developer-assessed metrics explicitly flagged |

Risk R2 (drift) was the highest-impact risk and received the most significant mitigation investment. The FSM architecture, NLU pipeline, and layered control stack exist because this risk was identified early and taken seriously. Risk R5 (validation gap) is the primary remaining weakness — see Section 4.5.

## 2.5 Professional Practice

Three practical lessons shaped implementation discipline during the project:

**SRP extraction prevented hidden regressions.** When `chatbot.py` was simultaneously handling orchestration, analysis, and prompt generation, changing a prompt for one stage could silently affect another. Extracting analysis into `analysis.py` (466 lines, pure functions with no side effects) and prompt templates into `prompts.py` (473 lines) meant each module could be tested in isolation.

**Pure-function style reduced test complexity.** `analysis.py` contains no class state — every function takes input and returns output with no side effects. This made unit testing straightforward: no mocking of database connections, no setup/teardown of session state.

**Configuration-over-code improved adaptability.** Signal keywords, advancement thresholds, product configurations, and tactical rules all live in YAML files under `src/config/`. A non-developer can edit `signals.yaml` to add a new objection keyword and see the effect immediately after server restart. This is deliberately lower-tech than a database-driven admin panel, but it is version-controlled and auditable via git.

| **Practice** | **Applied Standard** | **Evidence** |
|---|---|---|
| Task management | Trello board with phase-level columns and per-task cards; used to track feature progress, bug fixes, and documentation milestones | Trello board (screenshot in Appendix C) |
| Version control | 72 commits across 6 months; atomic commits with descriptive messages | Git history |
| Code quality | Technical audit identifying and fixing 15 issues (3 P0 bugs, 6 P1 dedup, 3 P2 bugs, 3 P3 operational) | `Documentation/technical_audit.md` |
| Testing | 395 automated tests (100% pass rate) + 25 manual scenarios | Section 3.2 |
| Documentation | Architecture consolidation, decision records, traceability matrix | `Documentation/` directory |
| Security | STRIDE threat model, input sanitisation, session isolation | Section 2.7 |
| Deployment | Environment-driven provider/config setup; zero-downtime provider switching | `.env` + factory pattern |

**Task tracking via Trello.** I used a Trello board throughout development to manage work across phases. Cards were organised by phase columns (Scoping, FSM+Prompts, Quality, Testing, Documentation) with individual cards for features, bugs, and documentation tasks. Cards were moved from "To Do" through "In Progress" to "Done" as work progressed. This provided visibility into what remained at each phase boundary and helped with the weekly scope reviews that kept the +10h overrun from growing further. The board is evidenced by screenshot in Appendix C.

**Demo-readiness practice.** Each milestone included an "explainability pass" where I had to justify each implementation choice against requirements, lifecycle stage, and observed evidence. This directly supported preparation for the oral exposition component of CS3IP assessment.

## 2.6 Monitoring, Effort & Estimation

### 2.6.1 Phase Summary

| **Phase** | **Planned** | **Actual** | **Deviation** | **Root Cause & Response** |
|---|---|---|---|---|
| Phase 1: Scoping | 4 weeks; Groq integration, YAML scaffold | 4 weeks (on time) | None | — |
| Phase 2: FSM + Prompts | 6 weeks; NEPQ alignment, output bug fixes | 6 weeks; Strategy Pattern replaced mid-phase | Architecture replaced rather than extended | Strategy Pattern revealed as mismatched (Section 2.1.1); FSM rebuilt |
| Phase 3: Quality | 4 weeks; cleanup, SRP extractions | 4 weeks; +2 unplanned module extractions | `trainer.py`, `prospect_evaluator.py` not in original plan | God-class anti-pattern in `chatbot.py` identified |
| Phase 4: Testing | 8 weeks; scenario validation, UAT | 8 weeks; 5 prompt revision cycles vs. 2 planned | +12h prompt engineering effort | Behavioural constraint tuning is empirical, not analytical |
| Phase 5: Documentation | 6 weeks; report, technical docs | 6 weeks; additional architecture diagrams | Extra FSM state diagrams, STRIDE threat model | Supervisor feedback emphasised technical evidence |
| **Overall** | **~60h estimated** | **~70h actual** | **+10h overrun (16%)** | Prompt iteration underestimated |

### 2.6.2 Key Estimation Insight

Prompt engineering consumed approximately 31% of total effort but was initially estimated at ~14%. This was the project's only significant estimation failure.

The initial estimate used analogical reasoning — comparing prompt tuning to code debugging. Both involve observing unexpected behaviour and making targeted changes. However, the analogy breaks down because prompt engineering is fundamentally stochastic: the same prompt can produce different outputs across runs, failures cannot be isolated to a specific line, and fixes require validation across multiple runs and scenarios. Code debugging is deterministic: same input produces same output, failures isolate to specific lines, and fixes are verifiable in one run.

This is a transferable lesson. Prompt engineering effort in LLM projects behaves more like experimental research than software development — each hypothesis requires a full test cycle. Future prompt-heavy projects should estimate prompt tuning at 2–3× initial expectation.

## 2.7 Ethics & Security

Data handling follows data-minimisation principles: session data is held in memory only and not persisted as user PII records. Sessions expire after 6 hours of inactivity and are cleaned up lazily on subsequent requests.

I used STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) as a structured threat modelling framework. This is appropriate for academic scope — it ensures systematic coverage without implying enterprise-grade hardening.

| **STRIDE Category** | **Main Threat** | **Mitigation** | **Residual Risk** |
|---|---|---|---|
| Spoofing | Session token abuse | Cryptographic session IDs (`secrets.token_hex(16)`) + TLS | Low |
| Tampering | Prompt injection | Input sanitisation + pattern filtering in `security.py` | Low–Medium |
| Repudiation | Limited audit trail | Basic request/rate-limit logs | Medium |
| Information Disclosure | Cross-session leakage | Session isolation (separate `SalesChatbot` instance per session) | Low |
| Denial of Service | Request/session flooding | Rate limiting + 200-session cap in `SessionSecurityManager` | Low |
| Elevation of Privilege | No auth layer | Scope-constrained access; debug endpoints gated behind env var | Medium |

**AI ethics boundary.** The system is intended for training simulation, not undisclosed live customer-facing deployment. The bot explicitly simulates a prospect persona for practice purposes. Prompt injection remains partially mitigated — pattern-based filters cannot guarantee full adversarial resistance, which is acknowledged as a known limitation (Section 3.3).

---

# 3. Deliverable

## 3.1 Implementation Outcomes

### 3.1.1 System Architecture

The architecture separates control from generation across four layers:

1. **Web layer** (`app.py`, 890 lines): Flask API routing, session lifecycle, security hooks.
2. **Orchestration** (`chatbot.py`, 371 lines): Thin orchestrator per SRP — delegates logic to specialised modules.
3. **Control plane** (`flow.py` + `analysis.py` + `content.py`, ~945 lines combined): FSM definitions, signal detection, prompt assembly.
4. **Generation** (`providers/`, ~280 lines): Provider abstraction with factory pattern for Groq/OpenRouter/Dummy.

Message flow: User input → `analysis.py` classifies intent/guardedness/signals → `flow.py` checks advancement conditions → `content.py` assembles stage-appropriate prompt → Provider generates response → Output contracts validate → Response returned.

### 3.1.2 Module Responsibilities

| **Module** | **LOC** | **Responsibility** |
|---|---|---|
| `chatbot.py` | 371 | Session orchestration, turn handling, provider dispatch |
| `flow.py` | 322 | FSM engine: stage definitions, transition guards, advancement rules |
| `prompts.py` | 473 | Prompt templates: P1/P2/P3 constraints, stage-specific scaffolds |
| `analysis.py` | 466 | NLU pipeline: intent classification, guardedness detection, keyword extraction |
| `content.py` | 157 | Prompt assembly: calls `prompts.py`, injects dynamic context |
| `prospect.py` | 473 | Role-reversal mode: bot-as-buyer with difficulty levels |
| `prospect_evaluator.py` | 135 | Deterministic scoring for prospect mode responses |
| `quiz.py` | 359 | Methodology assessment: stage identification, direction scoring |
| `trainer.py` | 137 | Coaching: context-aware Q&A, hint generation |
| `security.py` | via `app.py` | `SessionSecurityManager`: rate limiting, CORS, input sanitisation |
| `loader.py` | 613 | YAML loading, product matching, A/B variant assignment |
| `providers/*` | ~280 | Factory pattern for Groq/OpenRouter/Dummy providers |
| `app.py` | 890 | Flask routes, session lifecycle, frontend serving |

### 3.1.3 Key Delivered Features

**Core features:**
- FSM-driven consultative (5-stage) and transactional (3-stage) flows with explicit stage gating.
- Stage-aware prompt generation with P1/P2/P3 constraint hierarchy.
- NLU signal pipeline for deterministic progression.
- Provider abstraction (Groq primary, OpenRouter backup) with hot-swapping.
- Browser-based chat UI with session reset and message rewind/replay.

**Training features:**
- **Prospect mode** (`prospect.py`): Reverses roles — the system acts as a difficult buyer while the user practises as the salesperson, scored deterministically by `prospect_evaluator.py`.
- **Training coach panel** (`trainer.py`): Context-aware coaching assistant providing stage goals, next-step guidance, and free-text Q&A.
- **Quiz assessment** (`quiz.py`): Stage identification questions, next-move evaluation, and direction assessment with LLM output validation and score clamping.
- **Knowledge management** (`knowledge.py` + web UI): CRUD interface for uploading custom product context.

**Drift-containment stack (core technical contribution):**

| **Layer** | **Mechanism** | **Drift Type Addressed** |
|---|---|---|
| FSM Guards | Stage transitions only on explicit user signals | Stage drift |
| Intent Gating | LOW/MEDIUM/HIGH classification blocks premature pitch | Intent drift |
| Objection Scaffold | CLASSIFY→RECALL→REFRAME→RESPOND structure | Topic drift during objection |
| Lexical Entrainment | `extract_user_keywords()` injects prospect's terms | Mechanical parroting |
| Constraint Hierarchy | P1/P2/P3 rules override RLHF politeness | Permission question drift |
| Output Contracts | Regex post-processing catches residual violations | Edge-case cleanup |

## 3.2 Testing & Validation

### 3.2.1 Automated Testing

The test suite contains **395 tests across 9 active modules, all passing** (verified by running `pytest tests/ -v` on 23 March 2026). Tests are organised by concern:

- **FSM contract tests**: Verify that stage transitions only occur when advancement conditions are met.
- **Analysis unit tests**: Verify intent classification, guardedness detection, and keyword extraction against known inputs (pure functions, no mocking required).
- **API endpoint tests**: Verify Flask routes return correct status codes, session isolation, and error handling.
- **Security contract tests**: Verify rate limiting, input sanitisation, and session cap enforcement.
- **Quiz tests** (26 tests): Verify stage identification, score clamping, enum validation, and LLM output fallback.
- **Prospect mode tests**: Verify role reversal, scoring accuracy, and difficulty scaling.

Automated tests protect deterministic contracts — they verify that the FSM, analysis pipeline, and API behave as specified. They cannot assess conversational quality, which requires the manual and UAT layers below.

### 3.2.2 Manual Scenario Testing

25 structured scenarios were executed across five categories, deliberately including drift triggers (topic pivots, ambiguous intent turns, directness demands) to test whether stage control remained deterministic under realistic pressure.

| **Category** | **Purpose** | **Outcome** |
|---|---|---|
| Consultative progression | Validate staged prerequisite chain | Stable progression; occasional edge-case drift in ambiguous intent |
| Objection handling | Validate classify/reframe quality | Strong on common objection types (price, time, partner) |
| Directness/urgency | Validate frustration override | Urgency detection behaved consistently across test scenarios |
| Tone/persona | Validate entrainment and register alignment | Strong overall; one boundary case between "casual" and "informal" |
| Session operations | Validate rewind/reset/isolation | Functional across all tested workflows |

### 3.2.3 User Acceptance Testing (UAT)

UAT data collection is in progress. The methodology is finalised:

- **Participants**: Non-professional contacts and classmates (final count to be reported after data lock).
- **Format**: Guided roleplay conversation plus post-session Likert-scale questionnaire.
- **Scenarios**: Consultative flow, transactional flow, and mixed-intent path.

Questionnaire dimensions (Likert 1–5): Naturalness (Q1), Topic adherence (Q2), Flow appropriateness (Q3), Objection handling quality (Q4), Methodology adherence perception (Q5), Perceived training utility (Q6).

Results will be inserted after data lock. Qualitative themes (what felt realistic, what felt unnatural, where the bot lost the thread) will be grouped from participant free-text responses.

**UAT limitations**: Sample is small, participants are not all sales professionals, and no formal control condition exists. These are acknowledged as confidence boundaries, not hidden.

## 3.3 Known Limitations

**Inherent limitations (LLM behaviour):**
1. **LLM non-determinism**: The same prompt can produce different outputs across runs. Staged constraints reduce variance but do not eliminate it.
2. **Residual drift in long-horizon dialogue**: Drift frequency is reduced by design but not mathematically guaranteed to be zero over extended, mixed-intent exchanges.

**Scope-bounded limitations (addressable with more time/resources):**
3. **No robust retry orchestration**: Provider failures can surface as user-visible interruptions.
4. **Prompt injection partially mitigated**: Pattern-based filters cannot guarantee full adversarial resistance.
5. **Single-instance deployment**: Architecture is not designed for distributed multi-node state management.
6. **Regression coverage gap**: Some behavioural quality is validated only through manual scenarios.
7. **In-memory session lifecycle**: Sessions do not persist across server restarts. Intentionally lightweight for current scope.

---

# 4. Evaluation

This section assesses whether the deliverable achieved its stated objectives. I distinguish between deterministic claims (verifiable by code inspection or automated test) and behavioural claims (requiring human judgement).

## 4.1 Requirement Satisfaction

### 4.1.1 Functional Requirements

| **Requirement** | **Target** | **Result** | **Evidence Type** | **Evidence** |
|---|---|---|---|---|
| R1/O1: Stage progression | ≥85% accuracy | Met | Mixed: FSM traces (deterministic) + scenario judgement (developer-assessed) | 25-scenario test set |
| R2: Dual flow support | Functional | Met | Deterministic | Consultative + transactional paths in `flow.py` FLOWS config |
| R3: Adaptive prompting | Functional | Met | Deterministic | Prompts vary by intent/guardedness/directness in `prompts.py` |
| R4: Urgency override | Functional | Met | Deterministic | `user_demands_directness()` triggers skip logic |
| R5: Session operations | Functional | Met | Mixed | Rewind/reset/isolation verified in automated + manual tests |
| R6: Maintainability | Traceable | Met | Deterministic | YAML configs, test suites, artefact traceability matrix |

### 4.1.2 Non-Functional Requirements

| **NFR** | **Target** | **Achieved** | **Evidence** |
|---|---|---|---|
| NF1: Latency | <2000ms P95 | 1,768ms P95 (462ms mean) | `metrics.jsonl`: 491 recorded turns |
| NF2: Cost | £0 marginal | Met | Groq free tier + Render free tier |
| NF3: Isolation | Complete | Met | Separate `SalesChatbot` instance per session; 395 tests pass |
| NF4: Graceful handling | No hard crashes | Largely met | Endpoint fallback handling; some edge cases remain |
| NF5: Configurability | YAML-driven | Met | 7 YAML config files, ~2,000 lines |

### 4.1.3 Objective-Level Interpretation

| **Objective** | **Evidence** | **Interpretation** |
|---|---|---|
| O1: NEPQ adherence (≥85%) | Stage accuracy across 25-scenario test set | **Met.** Core drift controls are effective. Exact percentage is developer-assessed — see Section 4.2.3 for bias caveat. |
| O2: Persona emulation (≥90%) | Tone matching across 12 personas | **Met.** Few-shot examples + entrainment work as designed. |
| O3: Latency (<2000ms P95) | 1,768ms P95 across 491 turns | **Met.** Groq provider meets real-time target. |
| O4: Permission question elimination | 0 trailing questions in pitch-stage test responses | **Met.** P1/P2/P3 hierarchy fully effective. |
| O5: Zero-cost scalability | £0 infrastructure cost | **Met.** |
| O6: Quiz assessment | 26/26 quiz-specific tests pass | **Met.** |

O1 is the strongest indicator that the core thesis holds: deterministic structure + LLM generation works without fine-tuning in this domain.

## 4.2 Evaluation Methodology

### 4.2.1 Evidence Layers

| **Layer** | **What It Tests** | **Strength** | **Limitation** |
|---|---|---|---|
| Automated tests (395) | Deterministic behaviour: FSM guards, API contracts, input validation | Objective, repeatable | Cannot assess conversational quality |
| Manual scenarios (25) | Behavioural quality: tone, methodology adherence, drift containment | Can assess subjective quality | Developer bias; not independently validated |
| UAT (in progress) | External perception: naturalness, utility, methodology adherence | Independent signal | Small sample; participants not all sales professionals |

### 4.2.2 Validity Controls

- **Separation of evidence types**: Deterministic verification is distinguished from behavioural verification throughout this report to avoid over-claiming.
- **Requirement-linked evidence**: Each claim in Section 4.1 traces to specific artefacts or test families (see `Documentation/Artifact-Traceability.md`).
- **Point-in-time metric governance**: Values are versioned by validation cycle. Later test runs can supersede them without changing the evaluation method.

### 4.2.3 Key Caveat: Developer Bias

The biggest gap in this evaluation is independent user testing. Every behavioural accuracy metric was produced by the developer evaluating a system they built. I know the system's edge cases and may unconsciously avoid them during testing. Until independent UAT data exists, every behavioural metric should be read as **developer-assessed, not independently validated**.

I have chosen to be explicit about this rather than present developer-assessed figures as though they carry the weight of independent evaluation. The UAT methodology is in place (Section 3.2.3) and results will strengthen or qualify these claims once collected.

## 4.3 Theoretical Validation

Six academic theories were applied to solve specific observed failures. This section tests whether those interventions produced the predicted effects:

| **Claim** | **Source** | **Predicted Effect** | **Observed** | **Validated?** |
|---|---|---|---|---|
| Need-Payoff questions improve progression | Rackham (1988) | Higher stage progression via keyword-gated advancement | Stage progression reliable across test scenarios (vs. ~40% false advances without gating) | **Partial** — progression achieved; downstream close rate unmeasured |
| CoT reasoning improves accuracy | Wei et al. (2022) | Structured objection handling outperforms generic | Appropriate reframing improved from baseline with explicit IDENTIFY→RECALL→CONNECT→REFRAME scaffold | **Yes** |
| Lexical entrainment builds rapport | Brennan and Clark (1996) | Keyword injection reduces mechanical feel | Mechanical parroting eliminated in test scenarios with anti-parroting rule + keyword injection | **Yes** |
| Constitutional constraints reduce violations | Bai et al. (2022) | P1/P2/P3 hierarchy eliminates permission questions | 100% removal in pitch-stage tests | **Yes** |
| Repair signals require system accommodation | Schegloff (1992) | Directness detection triggers urgency override | 100% detection in frustration-signal test scenarios | **Yes** |
| Few-shot examples approach fine-tuned performance | Brown et al. (2020) | Tone examples enable persona-specific responses | Tone alignment improved substantially after adding 4 examples per stage prompt | **Yes** |

Five of six theoretical claims were validated within project scope. The partial validation (SPIN close rates) requires external sales outcome data that was outside this project's validation scope.

## 4.4 Strengths

**1. Maintainability under change.** The architecture supported major flow and module changes without destabilising the system. The FSM refactor reduced logic fragmentation from 5 files to 2 while improving review clarity. Subsequent feature additions (prospect mode, quiz, trainer) plugged into the architecture without modifying core FSM logic.

**2. Separation of concerns under pressure.** When `chatbot.py` became a god-class during prompt iteration, SRP extraction into `analysis.py`, `prompts.py`, and `trainer.py` improved testability while preserving behaviour. This demonstrates the architecture can absorb quality improvements without full rewrites.

**3. Core thesis support.** The stage adherence results support the central claim: deterministic structure + LLM generation is workable without fine-tuning in this domain. This has broader implications for LLM-powered conversational systems where methodology adherence matters more than conversational freedom.

## 4.5 Weaknesses & Trade-Offs

**Primary weakness: Independent validation gap.** See Section 4.2.3. Until UAT data is collected, every behavioural metric carries developer bias. This is the single most important limitation of the current evaluation.

[UAT pain points, unexpected behaviours, and missed edge cases will be inserted here after data lock to strengthen independent validity.]

**Additional trade-offs:**

| **Trade-Off** | **What Was Gained** | **What Was Lost** |
|---|---|---|
| Security posture | Adequate for academic scope | Below production expectations |
| Intent/guardedness boundaries | Deterministic classification | Some ambiguous cases misclassified |
| Residual drift | Substantially reduced from baseline | Cannot guarantee zero drift in long dialogues |
| Observability | Metrics file + developer panel | No structured end-to-end tracing |

These are stated explicitly because they materially affect confidence boundaries and inform future work priorities.

---

# 5. Reflection

## 5.1 Personal Reflection

The most important shift was from "using recommended patterns" to "measuring whether a pattern fits the problem."

I initially valued architectural style over outcome clarity. The Strategy Pattern implementation looked academically sophisticated, but its maintenance burden was measurable: ~45 minutes per feature review, fragmented logic across 5 files, shared imports creating hidden coupling. The FSM refactor was not an aesthetic preference — it was a response to measured costs.

Before this project, I would have said "my design follows textbook best practices." Now I ask "what does this design cost to maintain?" That distinction — between theoretical correctness and practical cost — is the single biggest thing I learned. The Strategy Pattern is not wrong. It is wrong *for this problem*, because the problem is sequential state flow, not dynamic algorithm dispatch. Knowing when a pattern does not fit is more valuable than knowing the pattern itself.

## 5.2 Key Lessons

**Lesson 1: The first fix is usually incomplete.** Early drift fixes addressed individual symptoms (permission questions, tone mismatches) without understanding the common cause. The insight that these were all instances of drift — outputs that were fluent but misaligned with stage intent — enabled a unified solution: layered control. In future projects, I will resist the temptation to close issues with symptom-level patches and look for the underlying pattern first.

**Lesson 2: Prompt engineering is not a hack.** Prompt engineering consumed 31% of total effort. Treating prompt tuning as a "quick fix" rather than disciplined engineering caused the only significant schedule overrun. In projects involving behavioural LLM control, prompt engineering should be planned like experimental research — each hypothesis requires a full test cycle — not like code debugging.

**Lesson 3: Pivot decisions should be based on measured cost.** The architectural pivot from Strategy Pattern to FSM felt like failure initially. The measured outcome was the opposite: reduced fragmentation, faster reviews, and zero coupling-related bugs post-refactor. The sunk cost of the original implementation was far smaller than the ongoing cost of maintaining a poor fit. Future projects should have explicit "stop and measure" checkpoints before committing to significant refactors.

## 5.3 Future Work

| **Priority** | **Work Item** | **Why It Matters** |
|---|---|---|
| High | Complete independent UAT with practising sales professionals | Addresses the primary weakness: developer bias in evaluation |
| High | Validate whether training with this system improves downstream sales behaviour | Current metrics measure chatbot behaviour, not learner improvement |
| Medium | Test methodology portability (e.g., implement BANT or MEDDIC frameworks) | Demonstrates that FSM architecture is genuinely methodology-agnostic |
| Low | Revisit voice pipeline with realistic latency and budget assumptions | Deferred from Iteration 1; would significantly improve user experience |

## 5.4 Research Directions

The project raises several questions worth systematic investigation:

**1. Comparative methodology study.** Does NEPQ-constrained prompting outperform SPIN, BANT, or unconstrained baselines under identical evaluation conditions? The FSM architecture supports arbitrary methodology definitions via YAML — a controlled comparison would require only configuration changes, not code changes.

**2. Prompt-constraint optimisation.** What is the relationship between constraint specificity, constraint length, and LLM compliance? Are shorter constraints more or less effective than detailed instructions? The three-layer control stack provides a natural experimental framework for isolating each layer's contribution.

**3. Adversarial reliability.** How well do layered controls hold under deliberately adversarial inputs designed to trigger drift? What is the minimum control stack required for acceptable reliability in a training context?

These questions are empirically testable with the current architecture and would contribute to broader understanding of LLM behaviour control in structured conversational domains.

---

# 6. References

Acuff, D. and Miner, J. (2023) *The NEPQ Sales Methodology*. 7th Level HQ. Available at: https://7thlevelhq.com/our-methodology/ (Accessed: 15 January 2026).

Association for Talent Development (ATD) (2023) *State of the Industry Report*. Alexandria, VA: ATD Press.

Bai, Y., Jones, A., Ndousse, K., Askell, A., Chen, A., DasSarma, N., Drain, D., Fort, S., Ganguli, D., Henighan, T. and Joseph, N. (2022) 'Constitutional AI: Harmlessness from AI Feedback', *arXiv preprint arXiv:2212.08073*. Available at: https://arxiv.org/abs/2212.08073.

Brennan, S.E. and Clark, H.H. (1996) 'Conceptual Pacts and Lexical Choice in Conversation', *Journal of Experimental Psychology: Learning, Memory, and Cognition*, 22(6), pp. 1482–1493.

Brown, T.B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., Dhariwal, P., Neelakantan, A., Shyam, P., Sastry, G., Askell, A. and Amodei, D. (2020) 'Language Models are Few-Shot Learners', *Advances in Neural Information Processing Systems*, 33. Available at: https://arxiv.org/abs/2005.14165.

Grand View Research (2023) *Corporate Training Market Size, Share & Trends Analysis Report*. San Francisco: Grand View Research.

Hu, E.J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L. and Chen, W. (2022) 'LoRA: Low-Rank Adaptation of Large Language Models', *International Conference on Learning Representations*. Available at: https://arxiv.org/abs/2106.09685.

Jordan, J. (2015) 'Engagement in E-Learning: The Role of Motivation and Design', *Journal of Corporate Learning*, 12(3), pp. 45–58.

Kirkpatrick, D.L. and Kirkpatrick, J.D. (2006) *Evaluating Training Programs: The Four Levels*. 3rd edn. San Francisco: Berrett-Koehler.

Liu, J., Liu, A., Lu, X., Welleck, S., West, P., Le Bras, R., Choi, Y. and Hajishirzi, H. (2022) 'Generated Knowledge Prompting for Commonsense Reasoning', *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics*, pp. 3154–3169.

Rackham, N. (1988) *SPIN Selling*. New York: McGraw-Hill.

Schegloff, E.A. (1992) 'Repair After Next Turn: The Last Structurally Provided Defense of Intersubjectivity in Conversation', *American Journal of Sociology*, 97(5), pp. 1295–1345.

Wei, J., Wang, X., Schuurmans, D., Bosma, M., Xia, F., Chi, E., Le, Q.V. and Zhou, D. (2022) 'Chain-of-Thought Prompting Elicits Reasoning in Large Language Models', *Advances in Neural Information Processing Systems*, 35. Available at: https://arxiv.org/abs/2201.11903.

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K. and Cao, Y. (2023) 'ReAct: Synergizing Reasoning and Acting in Language Models', *International Conference on Learning Representations (ICLR)*. Available at: https://arxiv.org/abs/2210.03629.

---

# Appendices

**Appendix A: Iterative Case Studies**

Detailed failure-to-fix traces and code snippets supporting Section 2.2. Each case study follows the format: observed failure → hypothesis → implementation change → before/after evidence → validation outcome.

**Appendix B: UAT Supporting Data**

Questionnaire instrument, raw responses, summary statistics, and transcript excerpts. To be completed after data lock.

**Appendix C: Project Development Diary**

Chronological development log with dated milestones, pivots, and key decisions. Source: git history (72 commits, September 2025–March 2026) supplemented by development notes.
