# DEMO PREP — Sales Roleplay Chatbot (40-Minute Closed Demo)

---

## NUMBERS TO MEMORISE (cite these confidently)

| Metric | Value | Evidence |
|---|---|---|
| Stage progression accuracy | **92%** (23/25 conversations) | Manual validation |
| Tone matching | **95%** (11/12 personas) | Persona testing |
| Objection resolution | **88%** (7/8 objections) | Reframe testing |
| Permission question removal | **100%** (0 violations) | Regex validation |
| Response latency (avg) | **980ms** | Performance logs |
| Response latency (p95) | **1,100ms** | Performance logs |
| Automated tests | **395 passing, 100%** | pytest suite |
| Code reduction (FSM refactor) | **−63%** (855 → 319 LOC flow engine) | Git diff |
| Infrastructure cost | **£0** | Groq free + Render free |

---

## 40-MINUTE STRUCTURE

### Minutes 0–5: Problem Statement
> "Sales training costs £10,000+ per employee. Most companies can't afford realistic, repeatable practice. This chatbot provides 24/7 objection-handling practice at near-zero marginal cost. The challenge: how do you make an AI follow a structured sales methodology without fine-tuning a model?"

**Land this:** it solves a real economic problem. Assessors want to know *why* this exists.

---

### Minutes 5–12: Architecture Walkthrough
Open `flow.py`, `content.py`, `chatbot.py` in editor tabs.

> "The system has three separable concerns:
> 1. **FSM (flow.py)** — deterministic stage control. Enforces consultative (5-stage NEPQ) or transactional (3-stage) flow. Advancement only triggers on keyword signals, not turn count.
> 2. **Prompt Engine (content.py)** — assembles stage-appropriate system prompts with adaptive tactics injected based on user signals (guarded, intent level, question fatigue).
> 3. **Provider Abstraction (providers/)** — Factory Pattern. Groq is primary; SambaNova and OpenRouter are fallbacks. Swap with one environment variable."

**Key points to hit:**
- "I initially built a Strategy Pattern (5 files, 855 LOC). Through testing I identified it was architecturally wrong — Strategy Pattern is for swappable algorithms, sales flows are deterministic sequences. I discarded it and rebuilt with FSM: −63% code, cleaner transitions, testable advancement rules."
- "Configuration-driven design: all keyword signals, thresholds, and advancement rules live in YAML. A sales trainer can modify behaviour in 2 minutes with zero code changes."

---

### Minutes 12–22: Live Demo

**Scenario 1 — Consultative flow (low-intent user):**
Start with: *"Hi, I'm looking at CRM options."*

Walk through each stage transition as it happens:
- INTENT → bot discovers need, doesn't pitch yet
- LOGICAL → bot probes current pain ("What's breaking first?")
- EMOTIONAL → future-pacing question ("If that was fixed, what changes for you?")
- PITCH → bot presents solution tied to their stated problem
- OBJECTION → user says "it's expensive" → bot reframes using their own words

**Emphasise:**
- "Notice the FSM prevents jumping to pitch. It gates on keyword signals."
- "Each stage uses a different prompting strategy — elicitation vs probing vs identity framing vs assumptive close."

**Scenario 2 — Urgency override (if time):**
Mid-conversation, type: *"Just show me the price."*
> "The FSM detects `user_demands_directness()` and skips straight to pitch. This is the fast-path override — consultative rigor without frustrating decisive buyers."

**Show rewind (if time):**
Edit a previous message → click Re-run from here.
> "The FSM replays conversation history to that turn. Useful for iterative practice — users can try a different objection response without restarting."

---

### Minutes 22–27: Technical Innovation

**Permission question fix (3-layer architecture):**
> "Initial problem: the bot ended pitches with permission questions 75% of the time — 'Would you like to consider this?' — which kills sales momentum. I fixed it with three layers:
> - Layer 1 (Prompt): explicit rule 'DO NOT end with ?'
> - Layer 2 (Predictive logic): pre-response check when advancing to pitch stage
> - Layer 3 (Regex enforcement): strips trailing ? as final guardrail
> Result: 100% elimination. Each layer addresses a specific failure mode."

**Objection handling (4-step Chain-of-Thought):**
> "Standard chatbots use generic objection responses. I implemented a 4-step reasoning scaffold: CLASSIFY the objection type (money, fear, partner, smokescreen, logistical, time, unknown) → RECALL the user's stated goals from conversation history → REFRAME using their own language → RESPOND. This follows Wei et al. (2022) Chain-of-Thought prompting. Result: 88% effective reframe rate."

---

### Minutes 27–30: Test Suite

Run in terminal:
```bash
pytest tests/ -v --tb=no -q
```

> "395 automated tests, 100% passing. Coverage includes: FSM transitions, intent detection, objection classification, session isolation, prompt injection defence, quiz evaluation, provider fallback. The test suite is the regression baseline — any code change that breaks behaviour gets caught immediately."

Show one specific test if asked:
> "For example, `test_consultative_flow_integration.py` validates that the bot cannot advance from LOGICAL to PITCH without a doubt keyword in the user's message. That's the determinism guarantee."

---

### Minutes 30–34: Evaluation Results

> "I evaluated across three methods:
>
> **1. Automated tests** — 395 unit + integration tests, 100% pass rate
>
> **2. Manual scenario testing** — 25 conversations across 12 buyer personas, measuring stage accuracy (92%), tone matching (95%), objection resolution (88%)
>
> **3. User Acceptance Testing** — [N] external participants rated the system on naturalness, stage adherence, and coaching usefulness. [Insert your results here]
>
> Known limitations: sample sizes appropriate for FYP scope; production deployment would require 100+ conversation validation. I document 4 guardedness edge cases honestly — the system can't distinguish polite disengagement from genuine interest using keyword matching alone. That's a discourse analysis problem beyond FYP scope."

---

### Minutes 34–38: Reflection

> "Three things I'd do differently:
>
> **1. Test from Day 1.** I established test scenarios mid-project. Having them upfront would have caught the Strategy Pattern mismatch 3 weeks earlier.
>
> **2. Prompt engineering budget.** I underestimated how much time this takes. It was the highest-leverage work — I'd allocate 30% of development time to it from the start.
>
> **3. Configuration-driven design from the beginning.** I did a refactor to move signals to YAML. Building it that way originally would have saved a sprint.
>
> The biggest lesson: LLM prompt engineering has a compliance ceiling around 60–70%. You need code-level enforcement (the regex layer) to close the remaining gap. That's a finding transferable to any LLM-integrated system."

---

### Minutes 38–40: Q&A

| Question | Answer |
|---|---|
| "Why prompt engineering vs fine-tuning?" | 92% accuracy at £0 cost vs £300–500 + 48h training time. For a moving target (sales methodology can change), fine-tuning creates maintenance debt. |
| "Why Flask and not FastAPI?" | Response cycles are <2s. Async overhead irrelevant at this scale. Flask has simpler deployment on Render with no additional config. |
| "How does the FSM prevent false advances?" | Keyword gating from `analysis_config.yaml`. Same signals → same state, always. I can show you the `_check_advancement_condition()` function — it's deterministic and unit-tested. |
| "What's your security model?" | STRIDE threat model applied. Cryptographic session tokens, rate limiting, prompt injection pattern matching, debug endpoints gated by env var. Known gaps: no auth layer, no audit logging — appropriate for academic scope, documented honestly. |
| "Did real users test it?" | Yes — [N] participants, [your UAT summary]. |
| "What's the biggest technical challenge?" | Stage advancement without false positives. The original turn-count rule advanced regardless of conversational content. FSM with keyword gating solved it: 40% → 92% stage accuracy. |
| "Why not use Dialogflow or Rasa?" | Evaluated both. Dialogflow requires intent labelling for every utterance — labour-intensive and brittle for open-ended sales conversations. Rasa requires training data at scale. Building from first principles with FSM + LLM gives full control over methodology enforcement with zero training data dependency. |
| "How does provider fallback work?" | `_try_switch_to_provider()` in `chatbot.py`. If Groq returns rate_limit_exceeded or any error, it tries SambaNova, then OpenRouter. One environment variable switches the primary provider. The chatbot core has zero LLM-specific imports — that's the Factory Pattern benefit. |

---

## BEFORE THE DEMO — CHECKLIST

- [ ] Flask server running locally (`python -m flask run`)
- [ ] Groq API key set in `.env`
- [ ] Two browser tabs: chat interface + `/knowledge` page
- [ ] `pytest tests/ -q` run — confirm 395 passing
- [ ] 2–3 example conversation transcripts ready (printed or browser tab)
- [ ] Code editor open: `flow.py`, `content.py`, `chatbot.py`
- [ ] Git log visible (`git log --oneline`) to show timeline if asked
- [ ] Know your UAT numbers (participant count, scores)

---

## KEY CONCEPTS TO BE ABLE TO EXPLAIN (if asked to go deeper)

**FSM vs Strategy Pattern:** Strategy Pattern = select algorithm at runtime (sorting, compression). FSM = manage state transitions over time. Sales conversations are state-driven — FSM is the correct abstraction.

**NEPQ framework:** Neuro-Emotional Persuasion Questioning (Jeremy Miner). 5 stages: intent → logical → emotional → pitch → objection. Each stage uses a different psychological mechanism. The consultative flow maps directly to this.

**Lexical entrainment:** Brennan & Clark (1996). People unconsciously match each other's vocabulary. The system extracts the user's keywords and injects them into the prompt — bot mirrors the user's register. This is why tone matching reaches 95%.

**Chain-of-Thought prompting:** Wei et al. (2022). Explicit reasoning steps in the prompt improve LLM output quality on multi-step tasks. Applied to objection handling: CLASSIFY → RECALL → REFRAME → RESPOND forces structured reasoning rather than generic responses.

**Constitutional AI hierarchy:** Prompt rules organised into P1 (absolute), P2 (default), P3 (contextual). P1 rules (like no trailing ?) cannot be overridden by lower-priority instructions. This is the layered enforcement model.
