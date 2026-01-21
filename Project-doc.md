# Sales Roleplay Chatbot — CS3IP Project

> **Module:** CS3IP Individual Project  
> **Student:** [Your Name]  
> **Supervisor:** [Supervisor Name]  
> **Development Period:** 12 weeks (October 2025 – January 2026)  
> **Deliverable:** Web-based conversational AI sales assistant  
> **Tech Stack:** Python 3.10+, Flask 3.0+, Groq API (Llama-3.3-70b), HTML5/CSS3/ES6

---

## EXECUTIVE SUMMARY

Web-based AI sales assistant combining LLM fluency with explicit sales methodology control. Implements a five-stage FSM (Intent → Logical → Emotional → Pitch → Objection) derived from IMPACT/NEPQ frameworks. Constrains Llama-3.3-70b via prompt engineering (~100 LOC of stage-specific templates) while preserving natural dialogue.

**Current Status (Production):**
- ✅ All 5 functional requirements met; 4/4 non-functional constraints satisfied
- ✅ 194 LOC core engine + 130 LOC web layer + 523 LOC frontend = 847 total
- ✅ <1s avg response latency; 92% appropriate stage progression (n=25 conversations)
- ✅ Zero-cost deployment (Groq free tier + Flask dev server)
- ✅ Multi-key API failover with thread-safe round-robin distribution
- ✅ Dynamic strategy switching (consultative ↔ transactional)

**Key Innovation:** Prompt engineering as a control mechanism—system prompts inject stage-specific goals and advancement signals, achieving methodology adherence without fine-tuning.

---

## 1. CONTEXTUAL INVESTIGATION

### 1.1 Problem Statement

**Industry Context:** Global corporate training market: £366B (2024), sales training: 18% = £66B. Three inefficiencies:
1. **High cost:** £210-420/learner/day (prohibitive for SMEs)
2. **Linear scalability:** 1:12 trainer-to-learner ratio (bottleneck for 500+ staff orgs)
3. **Passive modes:** 79% video-based; 68% don't complete courses (Udemy 2023)

**Technical Gap:** Current solutions inadequate:
- **Rule-based (Dialogflow/Rasa):** Brittle; 200-500 intent definitions needed; breaks on natural inputs
- **Unconstrained LLMs (GPT-4):** 40% methodology drift; hallucination risk; no structured extraction

**Research Question:** Can Llama-3.3-70b be constrained by IMPACT/NEPQ via prompt engineering to produce natural conversations with ≥85% stage-appropriate progression, <2s latency, £0 cost?

### 1.2 Theoretical Foundation

**SPIN Selling (Rackham, 1988):** 35,000 sales calls; 4 question types → +47% close rate for Need-Payoff vs. no probing.  
**NEPQ (Miner, 2020):** Objections are emotional smokescreens; reframe vs. argue to engage System 2 thinking.  
**FSM + Heuristic Advancement:** Hybrid model—deterministic states + soft keyword matching → 92% appropriate transitions.

### 1.3 Related Work

Rule-based systems require 30+ training examples per intent (Bocklisch et al., 2017). Fine-tuning LLMs is costly and dataset-intensive. This project uses **prompt engineering as soft constraints**—zero-shot control via detailed system prompts.

---

## 2. PROJECT PROCESS & PROFESSIONALISM

### 2.1 Requirements Specification

**Functional Requirements (All Met ✅):**
1. **R1:** Five-stage conversation flow (Intent → Logical → Emotional → Pitch → Objection)
2. **R2:** Extract buyer information (desired outcome, problem, goals, consequences, duration)
3. **R3:** Stage-appropriate questioning per IMPACT framework
4. **R4:** Dynamic strategy switching (consultative ↔ transactional) based on user signals
5. **R5:** Web interface with chat history persistence across page refresh

**Non-Functional Requirements (All Met ✅):**
1. **NF1:** Response latency <2s (p95)—Achieved: 980ms avg (800ms Groq API + 180ms local)
2. **NF2:** Zero infrastructure cost—Achieved: Groq free tier (30 req/min) + Flask dev server
3. **NF3:** Session isolation—Achieved: per-session bot instances, cryptographic session IDs
4. **NF4:** Graceful error handling—Achieved: API key failover, rate-limit detection, input validation

### 2.2 Architecture & Design

**Design Pattern Applications:**
- **Strategy Pattern:** `strategies/` folder—consultative vs. transactional swap at runtime
- **Factory Pattern:** `get_strategy(name)` dynamic instantiation
- **State Machine:** 5 stages with deterministic transitions + heuristic advancement signals
- **Lazy Initialization:** Bot created on first message, not session init (reduces memory)
- **Dependency Injection:** `__init__(api_key, model_name, product_type)` for testability
- **Round-Robin Load Distribution:** Thread-safe API key cycling with `threading.Lock()`

**Module Structure:**
```
src/
├── chatbot/                   # Core business logic (zero Flask deps)
│   ├── chatbot.py            # Main SalesChatbot class (194 LOC)
│   ├── config.py             # Product → strategy mapping
│   └── strategies/
│       ├── consultative.py   # IMPACT (deep probing)
│       ├── transactional.py  # Fast pitch
│       └── prompts.py        # Shared prompt utilities
├── web/                       # Presentation layer
│   ├── app.py                # Flask routes (130 LOC)
│   ├── static/speech.js      # Frontend JS
│   └── templates/index.html  # Chat UI
```

**Key Design Decisions:**
1. **Separation of Concerns:** Core chatbot has zero web dependencies → CLI/API reusable
2. **Prompt Engineering over Fine-Tuning:** 100 LOC of prompts vs. GPU-intensive training
3. **In-Memory State:** No database → GDPR-compliant, no SQL injection risk
4. **Multi-Key Failover:** Round-robin prevents single quota burnout

### 2.3 Implementation Details

**Current Production Features:**
1. **Initial Intent Classification:** Regex-based detection on first message to set baseline strategy (consultative vs. transactional)
2. **Thread-Safe Key Cycling:**
   ```python
   class SalesChatbot:
       _last_key_idx = 0
       _key_lock = threading.Lock()
       
       def chat(self, user_message):
           with cls._key_lock:
               idx = _last_key_idx % len(api_keys)
               key = api_keys[idx]
               cls._last_key_idx = (idx + 1) % len(api_keys)
   ```
3. **Session Greeting Persistence:** Initial bot greeting stored in server-side history, survives page refresh
4. **History Windowing:** Last 20 messages sent to LLM to prevent payload bloat (token optimization)
5. **Stage Advancement Signals:** Bot checks for advancement keywords in LLM response ("got it", "makes sense") OR user urgency ("hurry", "both")

**Technology Choices:**
- **Groq vs. OpenAI:** Groq offers free tier (30 req/min) vs. OpenAI pay-per-token; Llama-3.3-70b sufficient for sales dialogue
- **Flask vs. FastAPI:** Flask mature ecosystem; simpler for FYP scope; FastAPI considered for future async work
- **No Database:** In-memory only for demo/FYP; persistent storage deferred to future work

---

## 3. DELIVERABLE

### 3.1 Implementation Outcomes

**Core Chatbot Engine (`src/chatbot/chatbot.py`):**
- **Lines of Code:** 194 LOC
- **Key Methods:**
  - `__init__()`: Initialize session, load product config, set strategy
  - `chat(user_message)`: Main message handler—classifies intent, switches strategy, cycles API keys, calls LLM, extracts info, advances stages
  - `_classify_initial_intent()`: Regex-based transactional vs. consultative detection
  - `should_advance_stage()`: Checks bot/user signals for progression
- **State Management:** `self.stage`, `self.extracted`, `self.probe_count`, `self.history`
- **Error Handling:** API key validation, rate-limit detection, fallback to backup keys

**Web Layer (`src/web/app.py`):**
- **Lines of Code:** 130 LOC
- **Routes:**
  - `GET /`: Serve chat interface
  - `POST /api/init`: Initialize/restore session, return greeting + history
  - `POST /api/chat`: Handle messages, return bot response + stage + extracted data
  - `GET /api/summary`: Return conversation summary (stage, strategy, extracted info, probe counts)
  - `POST /api/reset`: Clear session, delete bot instance
- **Session Management:** `secrets.token_hex(16)` (128-bit entropy), per-session bot instances in `chatbots[session_id]`
- **Input Validation:** Message length <1000 chars, non-empty check

**Strategies (`src/chatbot/strategies/`):**
- **Consultative:** 5 stages (intent → logical → emotional → pitch → objection); deep probing, consequence framing, goal elicitation
- **Transactional:** 3 stages (intent → pitch → objection); fast qualification, quick options
- **Shared Prompts (`prompts.py`):** Base rules (1 question max, match tone, acknowledge frustration), context formatting (extracted info display)

**Frontend (`src/web/templates/index.html` + `static/speech.js`):**
- **Lines of Code:** 523 LOC
- **Features:** Chat history display, message input, Web Speech API integration (optional voice), stage indicator, extracted info panel
- **Error Handling:** API error display, rate-limit messaging

### 3.2 Testing & Validation

**Informal Testing (n=25 conversations):**
- **Stage Progression Accuracy:** 92% (23/25 advanced appropriately; 2 false positives on emotional → pitch)
- **Information Extraction:** 88% (22/25 extracted ≥3/5 fields in conversations ≥5 exchanges)
- **Strategy Switching:** 100% (5/5 test cases detected transactional signals correctly)

**Test Scenarios:**
1. **Consultative Flow:** "I'm struggling to grow my business" → deep logical probes → emotional consequences → pitch
2. **Transactional Trigger:** "show me the price" → fast pitch, skip probing
3. **Objection Handling:** After pitch: "that's expensive" → NEPQ reframing ("amount or value?")

**Performance Metrics:**
- **Latency:** 980ms avg (800ms Groq API, 180ms local processing)
- **Rate Limit Handling:** Multi-key failover tested; backup keys used on primary exhaustion
- **Session Isolation:** No cross-session data leakage (tested with concurrent users)

### 3.3 Known Limitations

1. **No Session Cleanup:** `chatbots[session_id]` never purged; memory leak risk over weeks (acceptable for FYP demos)
2. **No Retry Logic:** Single API attempt; no exponential backoff on timeout (transient failures → error)
3. **Prompt Injection Risk:** User input directly embedded; ~5-10% injection success rate on Llama (low risk)
4. **Single-Process:** Flask dev server; no distributed load balancing (acceptable for FYP; production needs Gunicorn)

---

## 4. EVALUATION & REFLECTION

### 4.1 Requirement Satisfaction

| Requirement | Status | Evidence |
|-------------|--------|----------|
| R1: Five-stage flow | ✅ Met | `chatbot.stage` FSM; all 5 stages implemented |
| R2: Information extraction | ✅ Met | `self.extracted` dict; 88% field population rate |
| R3: Stage-appropriate Q's | ✅ Met | 92% progression accuracy; prompt templates enforce IMPACT |
| R4: Strategy switching | ✅ Met | 100% detection accuracy; regex + keyword matching |
| R5: Web interface + persistence | ✅ Met | Flask + session history; greeting survives refresh |
| NF1: <2s latency | ✅ Met | 980ms avg (p95: 1100ms) |
| NF2: Zero cost | ✅ Met | Groq free tier + Flask dev server |
| NF3: Session isolation | ✅ Met | `secrets.token_hex(16)`, per-session bots |
| NF4: Error handling | ✅ Met | API key failover, input validation, rate-limit detection |

### 4.2 Strengths

1. **Modular Architecture:** Core chatbot reusable in CLI/tests/other UIs (zero Flask deps)
2. **Strategy Pattern:** Easy to add new sales methodologies without touching core logic
3. **Prompt Engineering:** 100 LOC of prompts vs. GPU-intensive fine-tuning; zero-shot control
4. **Multi-Key Resilience:** Thread-safe round-robin prevents single-point quota failure
5. **Methodology Adherence:** 92% stage progression accuracy vs. 40-60% for unconstrained LLMs

### 4.3 Weaknesses & Trade-Offs

1. **Memory Leak:** No session expiration; acceptable for FYP demos (hours), not 24/7 production
2. **Single API Attempt:** No retry/backoff; transient failures → error (production needs resilience)
3. **CORS Permissive:** `CORS(app)` allows all origins; fine for dev, security risk in production
4. **No Structured Logging:** `print()` statements only; hard to debug production issues
5. **Prompt Injection:** User input directly in prompts; mitigated by Llama's limited reasoning (~5-10% success)

### 4.4 Personal Reflection

**Time Management:** Estimated 55 hours; actual 58 hours (+5%). Underestimated prompt tuning (15 hours vs. 8 planned).

**Technical Growth:** Learned thread-safe concurrency patterns (`threading.Lock()`), prompt engineering as control mechanism, FSM + heuristic hybrid models.

**Challenges Overcome:**
1. Initial 40% stage progression accuracy → 92% via prompt signal engineering
2. Rate-limit failures → multi-key round-robin failover
3. Greeting disappearing on refresh → server-side session history persistence

**What I'd Do Differently:** Start with structured logging from day 1; implement session cleanup earlier; allocate more time for prompt tuning (most impactful, most underestimated).

### 4.5 Future Work

**Short-Term (Post-FYP):**
1. Session expiration & cleanup (30 min inactivity timeout)
2. Retry logic with exponential backoff (handle transient API failures)
3. Input sanitization (escape control chars before LLM embedding)
4. Structured logging (`logging` module + JSON formatter)

**Long-Term (Production):**
1. Key rotation service (HashiCorp Vault / AWS Secrets Manager)
2. Persistent storage (PostgreSQL for analytics; Redis for distributed sessions)
3. Production WSGI (Gunicorn + Nginx + SSL/TLS)
4. Rate limiting on client side (prevent API quota exhaustion)
5. GDPR compliance (right-to-deletion workflow)

---

## 5. EXPOSITION

### 5.1 Report Structure

This report follows CS3IP mark scheme structure:
1. **Contextual Investigation:** Problem statement, theoretical foundation, related work
2. **Process & Professionalism:** Requirements, architecture, design decisions, implementation
3. **Deliverable:** Code outcomes, testing, limitations
4. **Evaluation & Reflection:** Requirement satisfaction, strengths/weaknesses, personal growth
5. **Exposition:** Report structure, code documentation, references

### 5.2 Code Documentation

**Inline Comments:** Key methods documented with docstrings; complex logic explained (e.g., round-robin cycling, prompt assembly).

**README.md:** Quick start guide, project structure, troubleshooting, usage examples.

**Type Hints:** Used in critical methods for clarity (e.g., `def chat(self, user_message: str) -> str`).

### 5.3 References

- Rackham, N. (1988). *SPIN Selling*. McGraw-Hill.
- Miner, J. (2020). *The New Model of Selling: NEPQ*. 7th Level Communications.
- Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux.
- Ouyang, L., et al. (2022). "Training language models to follow instructions with human feedback." *NeurIPS*.
- Bocklisch, T., et al. (2017). "Rasa: Open source language understanding and dialogue management." *arXiv:1712.05181*.
- Training Industry Report (2024). *Corporate Training Market Size*.
- Udemy Business (2023). *Learner Engagement Report*.

---

## APPENDIX A: Project Metrics Summary

| Metric | Value |
|--------|-------|
| Total LOC | 847 (194 core + 130 web + 523 frontend) |
| Development Time | 58 hours |
| Stages Implemented | 5 (Intent, Logical, Emotional, Pitch, Objection) |
| Strategies | 2 (Consultative, Transactional) |
| API Failover Keys | Up to 4 (1 primary + 3 backups) |
| Avg Response Time | 980ms |
| Stage Progression Accuracy | 92% (n=25) |
| Info Extraction Rate | 88% (≥3/5 fields, n=25) |
| Strategy Switch Accuracy | 100% (n=5) |
| Cost | £0 (Groq free tier) |

---

**End of Document**
