# Documentation Index

**Last Updated:** 31 March 2026
**Status:** Clean — redundant files archived, essential docs consolidated

---

## 📋 Quick Navigation

### **Essential Architecture** (Start Here)
- **ARCHITECTURE_CONSOLIDATED.md** — Complete system design
  - FSM (Finite State Machine) framework with 3 strategies (Intent/Consultative/Transactional)
  - NLU analysis pipeline with signal detection
  - 4-tier prompt assembly system
  - All 26 core modules with responsibilities
  - Provider abstraction (Groq/OpenRouter/SambaNova)
  - Session lifecycle and persistence
  - Configuration architecture (9 YAML files)
  - Design patterns used (Factory, Strategy, FSM, Decorator, Observer)

### **FYP Submission Documents**
- **../Project-doc.md** — Full thesis/FYP report (parent directory)
  - Problem statement and research question
  - Architecture and design rationale
  - Implementation outcomes with evidence
  - Testing & validation results
  - Evaluation against requirements
  - Reflection and lessons learned

- **Mark-Scheme-Alignment.md** — How project satisfies marking criteria
  - Requirement coverage matrix
  - Module breakdown and complexity analysis
  - Quality evidence (testing, security, documentation)
  - Professional practice demonstration

### **Quality & Security**
- **technical_audit.md** — Code quality findings
  - 3 bugs fixed (dead code, strategy overlap, FSM logic)
  - 4 optimizations implemented
  - 3 known limitations documented
  - No high-risk issues

- **Security-Analysis.md** — Threat model and mitigations
  - Authentication & session management
  - Input validation and injection prevention
  - API rate limiting and access control
  - Data security and compliance

- **technical_decisions.md** — Architectural choices and rationale
  - Why FSM + LLM hybrid (not pure fine-tuning)
  - Why YAML configuration (not database)
  - Why in-memory sessions (not redis)
  - Why provider factory pattern

### **Feature Documentation**
- **Training-Feature-Roadmap.md** — Coaching & training system
  - Real-time feedback generation
  - NEPQ technique validation
  - Rubric-based scoring

- **Quiz-Feature-Development.md** — Assessment system
  - Stage identification quizzes
  - Next-move evaluation logic
  - Direction understanding quizzes

### **User Acceptance Testing (UAT)**
- **UAT/** folder — Ethics-approved study materials
  - Participant information sheets
  - Consent forms
  - Test protocols (locked from modifications)
  - Results and findings

---

## 📊 Diagrams

All 9 diagrams located in `diagrams/`:

| # | Name | Purpose |
|---|------|---------|
| 01 | System Architecture | Full C4 context, containers, components, data flow |
| 02 | FSM State Machine | All 3 strategy flows with transitions and rules |
| 03 | Chat Turn Sequence | 8-step execution: prompt → analysis → LLM → FSM → training |
| 04 | Prompt Assembly Pipeline | 4-tier system: override → ack → tactics → stage assembly |
| 05 | NLU Analysis Pipeline | Intent lock, guardedness scoring, objection classification |
| 06 | Class Diagram (Core) | SalesChatbot, SalesFlowEngine, providers, observability |
| 07 | Class Diagram (Features) | ProspectSession, Quiz, Trainer, Analysis, Content modules |
| 08 | Session Lifecycle | 5 initialization paths + restore/reset flows |
| 09 | Prospect Mode + Training | Buyer simulation + per-turn coaching loops |

---

## 🗂️ File Organization

```
Documentation/
├── README_DOCS.md (this file)
├── ARCHITECTURE_CONSOLIDATED.md ✅ Keep
├── Mark-Scheme-Alignment.md ✅ Keep
├── Security-Analysis.md ✅ Keep
├── technical_audit.md ✅ Keep
├── technical_decisions.md ✅ Keep
├── Training-Feature-Roadmap.md ✅ Keep
├── Quiz-Feature-Development.md ✅ Keep
├── diagrams/ (9 Mermaid files) ✅ Keep
├── UAT/ (ethics-approved testing) ✅ Keep
└── _archive/ (obsolete/superseded docs)
    ├── RDF-Phase1-LocalLLM.md
    ├── RDF-Phase2-FuzzyMatching.md
    ├── RDF-Phase3-FSMCloudLLM.md
    ├── Iteration1-LLM.md
    ├── Iteration2-Matching.md
    ├── Initial plan.md
    ├── Master-Implementation-Plan.md
    ├── ProjContents.md
    ├── Diary.md
    ├── What i did strat.md
    ├── Sylvia meetings.txt
    ├── failed_example_conversation.md
    └── Artifact-Traceability.md
```

---

## 🎯 Which Document Should I Read?

**I want to understand the system architecture**
→ Read `ARCHITECTURE_CONSOLIDATED.md` + review the 9 diagrams

**I want to know if this satisfies the FYP marking rubric**
→ Read `Mark-Scheme-Alignment.md`

**I want to assess code quality and technical debt**
→ Read `technical_audit.md`

**I want to understand security posture**
→ Read `Security-Analysis.md`

**I want design rationale for major decisions**
→ Read `technical_decisions.md`

**I want to understand training/coaching features**
→ Read `Training-Feature-Roadmap.md` + `../Project-doc.md` (Section 3)

**I want to understand quiz system**
→ Read `Quiz-Feature-Development.md`

**I want to see the full FYP report**
→ Read `../Project-doc.md` (parent directory)

**I want to understand a specific module's code**
→ Read the diagram for that module + check `ARCHITECTURE_CONSOLIDATED.md` section 5.3

---

## 📦 Archive Contents

The `_archive/` folder contains:

- **Superseded approach docs** (RDF-Phase 1/2/3) — These document earlier prototypes using local LLMs, now replaced by cloud LLM approach
- **Outdated planning docs** (Initial plan.md, Master-Implementation-Plan.md) — Pre-development plans, superseded by actual shipped implementation
- **Process notes** (Diary.md, Sylvia meetings.txt, What i did strat.md) — Personal project diary entries, not part of formal documentation
- **Meta-documentation** (ProjContents.md) — Old chapter outline, replaced by Project-doc.md structure
- **Historical artifacts** (Artifact-Traceability.md, failed_example_conversation.md) — Supporting evidence from development, now archived

**Recovery:** If you need to reference historical decisions, recover from `_archive/` as needed.

---

## 📈 Documentation Statistics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Active MD files | 20 | 7 | -65% |
| Total lines | 6,539 | ~2,000 | -69% |
| Archived (recoverable) | 0 | 13 | For safety |
| File clutter | High | Low | ✅ Cleaner |

---

## 🔧 How to Use This Index

1. **New reader?** Start with `ARCHITECTURE_CONSOLIDATED.md` (5 min read of sections 1–5)
2. **Need a quick ref?** Use the table above to jump to the right document
3. **Reviewing code?** Check the relevant diagram + module notes in `ARCHITECTURE_CONSOLIDATED.md`
4. **Submitting FYP?** Ensure `../Project-doc.md` and `Mark-Scheme-Alignment.md` are up-to-date
5. **Need historical context?** Check `_archive/RDF-Phase-*.md` for earlier design decisions

---

**Questions?** Refer to `ARCHITECTURE_CONSOLIDATED.md` section 15 (Glossary) for terminology, or check `technical_decisions.md` for design rationale.
