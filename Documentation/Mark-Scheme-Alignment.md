# Mark Scheme Alignment Analysis
**Date**: 2026-03-30
**Purpose**: Map Sales Roleplay Chatbot project documentation to CS3IP Mark Scheme requirements

---

## CS3IP Mark Scheme Overview

The mark scheme assesses 5 aspects. Each aspect has grade descriptors from <40% (fail) to >80% (excellent).

### Assessment Aspects & Weights

| Aspect | Description | Typical Weight | Target Grade |
|--------|-------------|----------------|--------------|
| **1. Contextual Investigation** | Problem justification, literature review, objectives | ~20% | 65-70% |
| **2. Project Process** | Requirements, design, SDLC, professionalism | ~25% | 65-70% |
| **3. Deliverable** | Working system, functionality, testing | ~25% | 65-70% |
| **4. Evaluation & Reflection** | Goal achievement, limitations, learning | ~20% | 60-65% |
| **5. Exposition** | Report quality, presentation, demo | ~10% | 65-70% |

**Target Overall**: 65-70% (2:1 grade)

---

## Aspect 1: Contextual Investigation / Background Research

### Mark Scheme Requirements (60-69% descriptor):
> "Substantial evidence of systematic investigation and critical thought... How the results of contextual investigation relate to and influence the development of the deliverable is clearly established."

### Your Current Coverage

| Requirement | Document(s) | Status | Gap Analysis |
|-------------|-------------|--------|--------------|
| **Problem Definition** | Project-doc.md §1.1 | ✅ Complete | Cost/scalability in sales training |
| **Literature Review** | MISSING | ❌ **CRITICAL GAP** | Need academic sources on:<br>• Conversational AI in education<br>• FSM vs pure LLM approaches<br>• Sales methodology frameworks<br>• Prompt engineering techniques |
| **Previous Work** | Project-doc.md §1.2 | ⚠️ Partial | Technical exploration exists, but lacks **academic citations** |
| **Business Case** | Project-doc.md §1.1 | ✅ Complete | Market size, pain points documented |
| **Objectives (SMART)** | Project-doc.md §1.6 | ✅ Complete | Defined with measurable criteria |
| **Competitive Analysis** | Project-doc.md §1.5 | ⚠️ Partial | Need comparison with:<br>• Roleplay.ai, Yoodli, Second Nature AI<br>• ChatGPT roleplay (text-based)<br>• Traditional methods |

### Action Items
1. **Add Literature Review Section** (~600 words)
   - Academic papers on conversational AI in training
   - Research on FSM + LLM hybrid architectures
   - Sales training effectiveness studies
   - Prompt engineering research

2. **Expand Competitive Analysis** (~300 words)
   - Feature comparison table (5-6 competitors)
   - Unique selling points with evidence

3. **Citations**: Aim for **15-20 academic sources** total (Harvard style)

### Target Grade: 65% (meets "substantial investigation" threshold)

---

## Aspect 2: Project Process and Professionalism

### Mark Scheme Requirements (60-69% descriptor):
> "Recognised development processes have been proficiently applied. Artefacts are in good style... There is clear evidence that processes and artefacts accurately reflect theoretical material."

### Your Current Coverage

| SDLC Stage | Requirement | Document(s) | Status | Evidence Quality |
|------------|-------------|-------------|--------|------------------|
| **Requirements** | FR/NFR spec | Project-doc.md §2.1 | ✅ Complete | Derived from failures + constraints |
| **Design** | Architecture rationale | ARCHITECTURE_CONSOLIDATED.md<br>Project-doc.md §2.2 | ✅ Complete | FSM rationale, alternatives considered |
| **Implementation** | Module structure | CLAUDE.md<br>Project-doc.md §2.4 | ✅ Complete | Provider abstraction, core modules |
| **Testing** | Test strategy | Project-doc.md §3.2<br>tests/* | ✅ Complete | Unit, integration, load, UAT |
| **Maintenance** | Monitoring, logging | performance.py<br>session_analytics.py | ✅ Complete | JSONL logging, metrics rotation |

#### Professionalism Evidence

| Aspect | Document(s) | Status | Evidence |
|--------|-------------|--------|----------|
| **Version Control** | Git history | ✅ Excellent | 60+ commits, branching, meaningful messages |
| **Risk Management** | Project-doc.md §2.5 | ✅ Complete | Risk register with mitigations |
| **Ethics & Security** | Security-Analysis.md<br>Project-doc.md §2.8 | ✅ Complete | Threat model, XSS/injection protection |
| **Project Diary** | Diary.md | ✅ Complete | Dated entries, pivots documented |
| **Iteration Evidence** | Iteration1-LLM.md<br>Iteration2-Matching.md<br>RDF-Phase*.md | ✅ Excellent | 3 major phases + RDF iterations |
| **Code Quality** | test suite, CLAUDE.md | ✅ Complete | 92% stage accuracy, test-driven |
| **Effort Tracking** | Project-doc.md §2.7 | ⚠️ Partial | **Need**: planned vs actual hours table |

### Action Items
1. **Add Effort Estimation Table** (Project-doc.md §2.7)
   - Planned hours per phase
   - Actual hours (from diary)
   - Variance explanation

2. **Formalize Artefact Traceability**
   - Already have Artifact-Traceability.md, but ensure it maps:
     - Requirements → Design decisions
     - Design → Implementation modules
     - Tests → Requirements (coverage)

### Target Grade: 70% (shows "insight and consistent quality")

---

## Aspect 3: The Deliverable

### Mark Scheme Requirements (60-69% descriptor):
> "A deliverable that substantially meets the objectives of the work, with only minor flaws."

### Your Current Coverage

| Deliverable Component | Status | Evidence | Quality Assessment |
|----------------------|--------|----------|-------------------|
| **Working Software** | ✅ Deployed | Render URL functional | Handles 100+ concurrent users |
| **Core Features** | ✅ Complete | • FSM (2 strategies)<br>• LLM integration (Groq/OpenRouter)<br>• Analytics tracking<br>• Session management | Meets FR1-FR8 |
| **Testing Evidence** | ✅ Complete | • 40+ unit tests<br>• Integration tests<br>• Load test profiles<br>• UAT planned | Pass rate >95% |
| **Documentation** | ✅ Complete | • User-facing (README)<br>• Developer (CLAUDE.md)<br>• Architecture (CONSOLIDATED) | Professional quality |
| **Demo-Ready** | ✅ Ready | • Web UI functional<br>• Debug panel<br>• Analytics dashboard | 40-min demo feasible |

#### Known Limitations (Documented in Project-doc.md §3.3)
- In-memory sessions (single-server limit ~100 users)
- YAML config requires restart
- Cold-start metrics scan (<5k lines, acceptable)
- Groq latency ~900-1000ms (cloud provider constraint)

### Action Items
1. **Prepare Demo Script** (~10 min presentation + 30 min Q&A)
   - Scenario walkthrough (consultative flow)
   - Strategy switch demonstration
   - Analytics dashboard tour
   - Code architecture explanation

2. **Complete UAT** (Project-doc.md §3.2.3)
   - Currently has placeholders
   - Need 5-8 participants (sales professionals or students)
   - Measure: usability, stage appropriateness, feedback quality

### Target Grade: 68% (substantial functionality + minor limitations acknowledged)

---

## Aspect 4: Evaluation and Reflection

### Mark Scheme Requirements (60-69% descriptor):
> "Evaluation is systematic and evidence-based... includes user or client feedback... reflection on project processes and outcomes."

### Your Current Coverage

| Evaluation Component | Document(s) | Status | Evidence Quality |
|---------------------|-------------|--------|------------------|
| **Objective Achievement** | Project-doc.md §4.1 | ✅ Complete | Requirement satisfaction table |
| **Evidence-Based Analysis** | Project-doc.md §4.1a | ✅ Complete | Multi-layer evidence model |
| **Theoretical Validation** | Project-doc.md §4.1b | ✅ Complete | NEPQ alignment verified |
| **Strengths Analysis** | Project-doc.md §4.2 | ✅ Complete | With metrics (92% accuracy, etc.) |
| **Weaknesses Analysis** | Project-doc.md §4.3 | ✅ Complete | Honest limitations documented |
| **User Feedback** | Project-doc.md §3.2.3 (UAT) | ⚠️ **PENDING** | **Critical**: Need real UAT data |
| **Personal Reflection** | Project-doc.md §5.1 | ✅ Complete | Growth narrative |
| **Key Lessons** | Project-doc.md §5.2 | ✅ Complete | What worked, what didn't |
| **Future Work** | Project-doc.md §5.3 | ✅ Complete | Realistic extensions |

### Action Items
1. **Complete UAT Study** (URGENT - mark scheme explicitly requires this)
   - Recruit 5-8 participants
   - Run 15-20 min sessions per participant
   - Collect: usability ratings, stage appropriateness feedback, open comments
   - Document in Appendix B

2. **Add Client/Stakeholder Perspective** (if possible)
   - If any sales trainers or managers reviewed the system, document their feedback
   - If no real client, explicitly state "academic project, no commercial client"

### Target Grade: 65% (systematic evaluation with evidence, pending UAT completion)

---

## Aspect 5: Exposition

### Mark Scheme Requirements (60-69% descriptor):
> "Substantial reasoned argument... style appropriate to formal scientific communication... examples and diagrams employed systematically... formal references appropriate."

### Your Current Coverage

| Exposition Aspect | Status | Quality | Improvement Needed |
|------------------|--------|---------|-------------------|
| **Report Structure** | ✅ Complete | Professional, logical flow | Ensure abstract is <250 words |
| **Language Quality** | ✅ Good | Formal, third-person | Proofread for consistency |
| **Diagrams** | ⚠️ Partial | Architecture diagrams exist | **Add**:<br>• FSM state diagrams<br>• Data flow diagrams<br>• Deployment diagram |
| **Code Snippets** | ✅ Good | Used appropriately in technical sections | Ensure syntax highlighting |
| **Citations** | ❌ **WEAK** | Few academic references | **Target 15-20 sources** |
| **References Section** | ⚠️ Placeholder | Needs population | Harvard style, alphabetical |
| **Appendices** | ✅ Good | Iterative cases, diary | Add UAT instruments |
| **40-Min Demo** | 📅 Future | Not yet prepared | Need rehearsal script |

### Action Items
1. **Add Visual Diagrams** (5-7 diagrams total)
   - FSM state machine (consultative + transactional)
   - Message flow sequence diagram
   - Deployment architecture
   - Data persistence model
   - Provider switching flow

2. **Populate References Section**
   - Academic papers on conversational AI
   - NEPQ/SPIN methodology sources
   - LLM research (prompt engineering, chain-of-thought)
   - Software engineering (FSM patterns, testing)

3. **Prepare Demo Presentation**
   - 10-min slide deck (problem → solution → results)
   - Live demo script (3 scenarios)
   - Q&A prep (anticipate 10 common questions)

### Target Grade: 65% (clear, well-structured, with minor gaps in citations)

---

## Overall Grade Projection

| Aspect | Weight | Target Grade | Weighted Score |
|--------|--------|--------------|----------------|
| Contextual Investigation | 20% | 65% | 13.0 |
| Project Process | 25% | 70% | 17.5 |
| Deliverable | 25% | 68% | 17.0 |
| Evaluation & Reflection | 20% | 65% | 13.0 |
| Exposition | 10% | 65% | 6.5 |
| **Overall** | **100%** | - | **67%** |

**Projected Grade**: **Upper 2:1** (67%)

**To Reach 70% (First Class threshold)**:
- Strengthen literature review (+3-5%)
- Complete high-quality UAT with 8+ participants (+2-3%)
- Add comprehensive diagrams (+1-2%)

---

## Critical Path to Submission

### Phase 1: Fill Documentation Gaps (1 week)
1. ✅ Write Literature Review section (~600 words)
   - 15-20 academic sources
   - Critical analysis, not just summary

2. ✅ Expand Competitive Analysis (~300 words)
   - Feature comparison table
   - USP justification

3. ✅ Add Visual Diagrams (5-7 diagrams)
   - FSM states, data flow, deployment

4. ✅ Create Effort Estimation Table
   - Planned vs actual hours with variance

### Phase 2: User Testing (1 week)
1. 📅 Recruit 5-8 UAT participants
   - Sales students or junior salespeople ideal

2. 📅 Conduct UAT sessions (15-20 min each)
   - Record: usability, stage appropriateness, feedback quality

3. 📅 Analyze and document results
   - Appendix B: raw data
   - Section 3.2.3: summary findings

### Phase 3: Final Polish (3-5 days)
1. 📅 Populate References section (Harvard style)
2. 📅 Proofread entire report
3. 📅 Generate final metrics snapshot
4. 📅 Prepare demo presentation + script

### Phase 4: Demo Preparation (2-3 days)
1. 📅 Create 10-min slide deck
2. 📅 Rehearse demo (3 scenarios, 15 min)
3. 📅 Prepare Q&A responses

**Total Time Needed**: ~3 weeks to submission-ready state

---

## Risk Register (Documentation Completion)

| Risk | Impact | Mitigation |
|------|--------|------------|
| **UAT recruitment fails** | High | Use friends/classmates as fallback; document limitations |
| **Literature review takes too long** | Medium | Start with 10 sources, prioritize quality over quantity |
| **Diagram creation delays** | Low | Use existing PlantUML tools, simple diagramming.net |
| **Demo technical failure** | High | Pre-record backup video, test on multiple browsers |

---

## Summary: What The Mark Scheme Tells You

### Strengths (Already Strong)
- ✅ **Project Process**: Excellent iteration evidence, SDLC compliance
- ✅ **Deliverable**: Working system with testing
- ✅ **Professionalism**: Git discipline, risk management, security

### Weaknesses (Need Attention)
- ❌ **Literature Review**: Critical gap for Contextual Investigation
- ❌ **UAT**: Essential for Evaluation aspect (mark scheme explicitly requires user feedback)
- ⚠️ **Citations**: Too few academic references hurts Exposition

### Action Priority
1. **URGENT**: Complete UAT (1-2 weeks)
2. **HIGH**: Write literature review (3-5 days)
3. **MEDIUM**: Add diagrams (2-3 days)
4. **LOW**: Polish references and proofread

---

**Next Steps**:
- [ ] Confirm project status (Sales Roleplay Chatbot vs VoiceCoach AI)
- [ ] Begin literature review research
- [ ] Schedule UAT participants
- [ ] Create diagram drafts
