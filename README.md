# Sales Roleplay Chatbot

**An AI-powered sales assistant combining LLM fluency with explicit sales methodology control.**

Implements the IMPACT/NEPQ frameworks via FSM-based stage management; internal evaluations show up to 92% stage-appropriate progression without model fine-tuning. Built for training scenarios and conversational AI research.

---

## ⚡ Quick Start (5 Minutes)

### Prerequisites
- Python 3.10+ (recommended)
- Groq API key (cloud) or Ollama (local model)

### Setup (POSIX)
```bash
# Clone repository and create virtualenv
git clone <repo>
cd "Sales roleplay chatbot"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy example env and edit values
cp .env.example .env
# Edit .env: set GROQ_API_KEY or OLLAMA_BASE_URL (for Ollama)
```

### Setup (Windows PowerShell)
```powershell
git clone <repo>
cd "Sales roleplay chatbot"
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: set GROQ_API_KEY or OLLAMA_BASE_URL
```

### Run (development)
```bash
# From repository root
python src/web/app.py
# Open http://localhost:5000
```

### First Conversation
1. Open web interface
2. Select a product (or "general")
3. Chat with the bot

---

## 🎯 What This Does

### Core Features
✅ **Multi-Strategy Sales Flow** — Automatically detects strategy (consultative 5-stage or transactional 3-stage)
✅ **NEPQ Framework** — Consultative conversations follow Neuro-Emotional Persuasion Questioning
✅ **Objection Handling** — Classifies objections (fear, money, partner, logistical, indecision, smokescreen) + reframes
✅ **Tactical Ack** — Context-aware validation (full for vulnerability, light for guardedness, none for info requests)
✅ **Provider Abstraction** — Hot-switch between Groq (cloud) and Ollama (local) at runtime
✅ **Training Mode** — Generate coaching feedback and answer trainee questions
✅ **Custom Knowledge** — Web interface to add product data without code changes

### Academic Innovation
🔬 **Prompt Engineering as Behavioural Constraint** — Natural language specifications guide LLM output without fine-tuning (92% stage accuracy)
🔬 **Hybrid FSM + LLM** — Deterministic state transitions + probabilistic response generation = auditable methodology adherence
🔬 **Tactical Ack** — Conditional validation based on psychological readiness (emotional disclosure vs. guarded response)

---

## 📚 Documentation Map

| Document | Purpose | For Whom |
|----------|---------|----------|
| [Documentation/ARCHITECTURE_CONSOLIDATED.md](Documentation/ARCHITECTURE_CONSOLIDATED.md#L1) | System design, module responsibilities, FSM details | Developers, architects |
| [Documentation/technical_decisions.md](Documentation/technical_decisions.md#L1) | Design rationale and trade-offs | Technical leads |
| [Documentation/Security-Analysis.md](Documentation/Security-Analysis.md#L1) | STRIDE threat model & controls | Security reviewers |
| [Documentation/UAT/UAT-Strategy-and-Execution.md](Documentation/UAT/UAT-Strategy-and-Execution.md#L1) | Ethics-approved testing protocol & learning outcome metrics | Evaluators |
| [Documentation/Appendix-Iteration-Log.md](Documentation/Appendix-Iteration-Log.md#L1) | Measured improvements by iteration with academic grounding | Reviewers |
| [Documentation/_archive/Quiz-Feature-Development.md](Documentation/_archive/Quiz-Feature-Development.md#L1) | Quiz assessment feature: TDD approach & test cases | Educators |
| [Documentation/_archive/Training-Feature-Roadmap.md](Documentation/_archive/Training-Feature-Roadmap.md#L1) | Active feature prioritisation (F1–F12) | Product owner |
| [Documentation/_archive/technical_audit.md](Documentation/_archive/technical_audit.md#L1) | Code quality audit: 3 bugs fixed, 4 deferred, rationale | Maintainers |

---

### Canonical Diagrams for Submission

For final reports and thesis submissions we recommend including only the three canonical diagrams that together cover system design, control flow, and runtime execution (this reduces redundancy and improves clarity):

- `Documentation/diagrams/01_chatbot_big_picture.mmd` — System architecture overview.
- `Documentation/diagrams/02_fsm_state_flow.mmd` — FSM state transitions (corrected; no "NEGOTIATION" sub-stage).
- `Documentation/diagrams/02_sequence_full_flow.mmd` — Runtime execution sequence for a single chat turn.

Other diagrams remain in the repository for developer reference and are archived in `Documentation/_archive/` where appropriate.


## 🏗 Architecture Overview

```
┌─────────────────────────────────────────┐
│        Flask Web Application            │
│    (app.py: Sessions, Routing)          │
└────────────────┬────────────────────────┘
                 │
         ┌───────▼────────┐
         │ SalesChatbot   │ (Orchestrator)
         │ (chatbot.py)   │
         └───────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐  ┌─────▼──────┐  ┌──▼───────┐
│ FSM   │  │ LLM        │  │ Trainer  │
│(flow) │  │ Providers  │  │(coaching)│
└───┬───┘  └─────┬──────┘  └──────────┘
    │            │
    │    ┌───────▼────────┐
    └───▶│ Analysis       │
         │ Content        │
         │ (Prompts)      │
         └────────────────┘

Flow: User Message → FSM Decision → Content Generation → LLM Call → Response
```

**Key Design Principle**: FSM (state machine) manages *what stage* the conversation is in. Content generation (prompts) and LLM ensure *how* we talk. This separation enforces methodology adherence without needing to fine-tune the model.

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v --cov=src/chatbot

# Run specific test suite
pytest tests/test_ack_tactics.py -v

# Run with coverage report
pytest tests/ --cov=src/chatbot --cov-report=html
open htmlcov/index.html
```

**Test Coverage**: 198 tests (59 Phase 1 + 139 planned)
- Unit tests (pure logic, <1ms each)
- Integration tests (FSM + analysis, no LLM)
- Behavioural tests (NEPQ framework verification)

See [TESTING_STRATEGY.md](TESTING_STRATEGY.md) for full framework.

---

## 🚀 Deployment

### Local Development
```bash
# POSIX / macOS
export GROQ_API_KEY="your-key-here"
python src/web/app.py  # Runs on localhost:5000

# Windows (PowerShell)
setx GROQ_API_KEY "your-key-here"
python src\web\app.py
```

### Production (Example: Heroku)
```bash
# Set environment variables
heroku config:set GROQ_API_KEY="..."

# Deploy
git push heroku main
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for details on Docker, systemd, scaling.

---

## 📋 Requirements & Dependencies

```
Python 3.10+
flask>=3.0
flask-cors>=4.0
groq>=0.4.0 (or: ollama for local)
pyyaml>=6.0
pytest>=8.0 (dev)
```

Full list: [requirements.txt](requirements.txt)

---

## 🔧 Configuration

### Environment Variables
```bash
GROQ_API_KEY          # Groq API key (get free at groq.com)
SAFE_GROQ_API_KEY     # Alternative name (checked first)
OLLAMA_BASE_URL       # Local Ollama endpoint (e.g., http://localhost:11434)
FLASK_ENV             # development | production
DEBUG                 # true | false
```

### YAML Configuration
- `src/config/signals.yaml` — Intent, objection, commitment, guardedness keywords
- `src/config/analysis_config.yaml` — Thresholds, advancement rules, question patterns
- `src/config/product_config.yaml` — Product metadata, strategy assignments

See [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for modification patterns.

---

## 💡 Usage Examples

### Example 1: Consultative Strategy (NEPQ)
```
User: "I need a car"
Bot: "What brings you here today?"
→ [Intent stage] Question to discover purpose

User: "My old car breaks down constantly"
Bot: "How long has that been happening?"
→ [Logical stage] Question to establish doubt

User: "It's affecting my family"
Bot: "If you could change one thing about the situation..."
→ [Emotional stage] Future pacing question

User: "They'd feel safer"
Bot: "Here's what would solve this..."
→ [Pitch stage] Present solution

User: "That's expensive"
Bot: "What's actually holding you back?"
→ [Objection stage] Handle concern via reframe
```

### Example 2: Transactional Strategy
```
User: "Need a fragrance, budget £50"
Bot: "Perfect! Here are 3 options in that range:"
→ [Intent → Pitch] Direct to options (no emotional stage)

User: "Which one?"
Bot: "Which of these fits best?"
→ [Pitch → Commitment/Objection]
```

### Example 3: Training Mode
```
User: Chat normally...
(After exchange)
User: "Coach me"
Bot: [Generates coaching feedback on that exchange]

User: "How do I build rapport?"
Bot: [Answers training question with techniques]
```

---

## 🎓 Academic Contributions

This project synthesizes six research domains into a unified framework:

| Domain | Key Paper | Application |
|--------|-----------|-------------|
| **Sales Methodology** | Rackham (1988): SPIN Selling | Stage progression logic |
| **Emotional Persuasion** | Acuff & Miner (2023): NEPQ | Objection handling, future pacing |
| **LLM Constraint Theory** | Bai et al. (2023): Constitutional AI | Prompt engineering for behaviour control |
| **Reasoning Quality** | Wei et al. (2022): Chain-of-Thought | Structured objection reframing |
| **Conversational Rapport** | Brennan & Clark (1996): Lexical Entrainment | User keyword injection |
| **Pragmatic Repair** | Schegloff (1992): Conversational Repair | Frustration detection + urgency override |

**Innovation**: No prior work integrates all six domains. This project demonstrates how prompt engineering, FSM logic, and psychological theory combine to achieve commercial-viable methodology adherence without fine-tuning.

---

## 🐛 Troubleshooting

### "GROQ_API_KEY not found"
```bash
# Check your .env file
cat .env

# Or set directly
export GROQ_API_KEY="gsk_..."
```

### "ModuleNotFoundError: chatbot"
```bash
# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
python -m pytest tests/
```

### "Ollama connection refused"
```bash
# Start Ollama
ollama serve

# In another terminal, pull a model
ollama pull llama3.2:3b

# Set environment variable
export OLLAMA_BASE_URL="http://localhost:11434"
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

## 📊 Current Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Stage Accuracy | Up to 92% (internal evaluation) | ≥85% ✅ |
| Avg Response Latency | <1s | <2s ✅ |
| Unit Test Pass Rate | 100% | ≥95% ✅ |
| Code Coverage | 78% | ≥70% ✅ |
| Permission Questions (Removed) | 100% | 100% ✅ |

---

## 🤝 Contributing

Want to improve the system?

1. **Report Bugs**: [Open an issue](https://github.com/...issues) (not yet public)
2. **Suggest Features**: Discuss in [Discussions](https://github.com/.../discussions)
3. **Submit Code**: See [CONTRIBUTING.md](CONTRIBUTING.md)

Code reviews follow standards in [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md).

---

## 📜 Licence

This repository is licensed under the MIT License. See LICENSE.

---

## 📧 Contact

- **Project Supervisor**: [Supervisor Name]
- **Student**: [Your Name]
- **Institution**: Aston University
- **Module**: CS3IP Individual Project

---

## 🔗 Related Links

- **Live Demo**: [Link if available]
- **Project Paper**: [Link to full thesis/paper]
- **GitHub**: [Repository link]
- **Documentation**: Start with [Project-doc.md](Documentation/Project-doc.md)

---

**Last Updated**: April 18, 2026
**Version**: 1.1
**Status**: ✅ Active Development & Maintenance
