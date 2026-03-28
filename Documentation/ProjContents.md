# Project Contents, Section Boundaries, and Detailed Execution Plan

## Table of Contents (Aligned to Project-doc.md)

### Abstract [220 words]
Purpose: Summarise the problem, the FSM + LLM solution, and headline measured outcomes.

### 1. Context, Exploration & Rationale [1200 words]
Purpose: Establish the business problem, justify design choices, and define measurable objectives.

- 1.1 Problem Domain & Business Context [220 words]: Explain cost, scalability, and stakeholder pain points in sales training.
- 1.2 Technical Exploration & Previous Approaches [260 words]: Summarise hardware constraints, rejected prototypes, and model/provider choices.
- 1.3 Research Question & Architectural Hypothesis [160 words]: State the question and the FSM-for-control, LLM-for-generation hypothesis.
- 1.4 Sales Structure Foundation [260 words]: Link SPIN/NEPQ and conversation theory to concrete implementation decisions.
- 1.5 Critical Analysis & Competitive Differentiation [170 words]: Compare alternatives and define project USP.
- 1.6 Project Objectives [130 words]: Define SMART objectives and success criteria only.

### 2. Project Process & Professionalism [4500 words]
Purpose: Show how the project was engineered, managed, de-risked, and quality-controlled.

- 2.1 Requirements Specification [400 words]: Document FR/NFR derived from observed failures and constraints.
- 2.2 Architecture & Design [550 words]: Explain architectural evolution and rationale for FSM-centric control.
- 2.3 Iterative Development & Prompt Engineering [900 words]: Present major failure-to-fix cycles with before/after evidence.
- 2.4 Implementation Details [450 words]: Explain core abstractions, modules, and provider integration approach.
- 2.5 Risk Management [450 words]: Present risk register, mitigations, and outcomes.
- 2.6 Professional Practice [350 words]: Show standards for version control, testing discipline, documentation, and review.
- 2.7 Monitoring, Effort & Estimation [700 words]: Compare planned vs actual effort and explain deviations.
- 2.8 Ethics & Security [700 words]: Document data handling, threat analysis, controls, and residual risks.

### 3. Deliverable [1500 words]
Purpose: Describe what was built and demonstrate operational validity.

- 3.1 Implementation Outcomes [700 words]: Walk through system capabilities and architecture-level outcomes.
- 3.2 Testing & Validation (including UAT) [450 words]: Summarise testing strategy and cross-method evidence.
- 3.2.1 Automated Testing [120 words]: Report coverage snapshot, pass/fail distribution, and contract confidence.
- 3.2.2 Manual Scenario Testing [140 words]: Report scenario design and observed behavioural outcomes.
- 3.2.3 User Acceptance Testing (UAT) [190 words]: Report participant setup, dimensions, and validated findings/placeholders.
- 3.3 Known Limitations [350 words]: Describe technical boundaries and unresolved constraints.

### 4. Evaluation [1200 words]
Purpose: Judge requirement satisfaction and test whether theory matched observed outcomes.

- 4.1 Requirement Satisfaction [500 words]: Evaluate FR/NFR outcomes against targets.
- 4.1a Evaluation Methodology [180 words]: Explain evidence model, validity caveats, and governance of metrics.
- 4.1b Theoretical Validation [170 words]: Compare predicted theory effects to actual project evidence.
- 4.2 Strengths [170 words]: Highlight validated strengths with measurable backing.
- 4.3 Weaknesses & Trade-Offs [180 words]: Explain limitations, compromise decisions, and confidence boundaries.

### 5. Reflection [600 words]
Purpose: Capture personal/professional growth, lessons, and realistic next steps.

- 5.1 Personal Reflection [150 words]: Explain mindset and capability development.
- 5.2 Key Lessons [200 words]: State what changed in engineering judgement and method.
- 5.3 Future Work [150 words]: Propose practical, scoped extensions.
- 5.4 Research Directions [100 words]: Propose follow-on research questions.

### 6. References [Excluded from word count]
Purpose: Provide complete Harvard-style sources used in the report.

### 7. Appendices [Excluded from word count]
Purpose: Preserve supporting depth without overloading the main narrative.

- Appendix A: Iterative Case Studies [Excluded from word count]
- Appendix B: UAT Supporting Data [Excluded from word count]
- Appendix C: Project Development Diary [Excluded from word count]

---

## Detailed Execution Plan (Section, Subsection, and Sub-subsection Boundaries)

### Abstract
Purpose: Deliver a concise, evidence-led snapshot of problem, approach, and outcome.
Must include: problem statement, architectural approach, and top-level measured result.
Must not include: implementation chronology, deep theory review, or reflection narrative.

### 1. Context, Exploration & Rationale
Purpose: Justify why the project exists and why this architecture is credible.
Must include: stakeholder problem, exploration outcomes, theory linkage, competitor comparison, SMART objectives.
Must not include: build chronology, full testing results, or final grading-style judgement.

### 1.1 Problem Domain & Business Context
Purpose: Define the practical training problem and who is affected.
Must include: cost/scalability challenge, stakeholder groups, and impact framing.
Must not include: implementation details or competitive table depth.

### 1.2 Technical Exploration & Previous Approaches
Purpose: Show how constraints and prototypes shaped the final direction.
Must include: hardware/latency constraints, discarded options, and pivot rationale.
Must not include: final architecture deep dive or requirement scoring.

### 1.3 Research Question & Architectural Hypothesis
Purpose: State the research focus and expected mechanism of improvement.
Must include: explicit research question and clear hypothesis logic.
Must not include: outcome claims that belong to Evaluation.

### 1.4 Sales Structure Foundation
Purpose: Ground implementation in established sales/conversation theory.
Must include: theory-to-failure and theory-to-implementation linkage.
Must not include: process narrative or retrospective judgement.

### 1.5 Critical Analysis & Competitive Differentiation
Purpose: Position the project against alternatives and justify uniqueness.
Must include: comparison criteria, market alternatives, and explicit USP.
Must not include: feature implementation detail.

### 1.6 Project Objectives
Purpose: Define what success means before presenting results.
Must include: objective IDs, measurable criteria, and thresholds.
Must not include: achieved values or pass/fail discussion.

### 2. Project Process & Professionalism
Purpose: Demonstrate disciplined delivery, technical governance, and engineering quality.
Must include: requirement derivation, architecture rationale, iterative fixes, risk handling, standards, monitoring, ethics.
Must not include: repeated theory exposition from Section 1 or final verdict scoring from Section 4.

### 2.1 Requirements Specification
Purpose: Translate observed failures and constraints into FR/NFR statements.
Must include: traceable requirements, rationale, and stakeholder mapping.
Must not include: results tables that belong to Evaluation.

### 2.2 Architecture & Design
Purpose: Explain architecture decisions and why FSM was selected.
Must include: alternatives considered, trade-offs, and final model justification.
Must not include: full test outcomes or reflection narrative.

### 2.3 Iterative Development & Prompt Engineering
Purpose: Show evidence-led iteration from failure to fix.
Must include: problem, hypothesis, change, implementation artifact, validation.
Must not include: generic claims without before/after evidence.

### 2.4 Implementation Details
Purpose: Explain the main technical building blocks and interfaces.
Must include: module responsibilities, provider abstraction, and integration points.
Must not include: repeated architecture debate already covered in 2.2.

### 2.5 Risk Management
Purpose: Show proactive risk identification and mitigation execution.
Must include: risk probability/impact, mitigation actions, and residual status.
Must not include: unrelated theory or raw logs without interpretation.

### 2.6 Professional Practice
Purpose: Demonstrate engineering standards and discipline.
Must include: source control practice, testing workflow, review/documentation habits.
Must not include: narrative unrelated to process quality.

### 2.7 Monitoring, Effort & Estimation
Purpose: Evidence planning quality and control during delivery.
Must include: planned vs actual effort, variances, and corrective actions.
Must not include: unsupported productivity claims.

### 2.8 Ethics & Security
Purpose: Define data, safety, and abuse-resistance posture for project scope.
Must include: threat model summary, controls, and residual risk boundaries.
Must not include: enterprise-security claims beyond demonstrated scope.

### 3. Deliverable
Purpose: Present what was delivered and whether it works in practice.
Must include: implementation outcomes, testing evidence, and known limitations.
Must not include: process history or architecture decision debates.

### 3.1 Implementation Outcomes
Purpose: Describe final system capabilities and user-facing functionality.
Must include: architecture snapshot, module roles, and delivered features.
Must not include: detailed failure history from iteration phase.

### 3.2 Testing & Validation (including UAT)
Purpose: Present evidence that the deliverable behaves as intended.
Must include: automated, manual, and UAT methods with outcome summary.
Must not include: requirement pass/fail judgement language from Section 4.

### 3.2.1 Automated Testing
Purpose: Quantify deterministic reliability.
Must include: test totals, pass/fail breakdown, and key confidence statement.
Must not include: subjective quality commentary without metrics.

### 3.2.2 Manual Scenario Testing
Purpose: Validate conversational behaviour in realistic paths.
Must include: scenario categories, intent of each set, and observed outcomes.
Must not include: UAT participant analysis.

### 3.2.3 User Acceptance Testing (UAT)
Purpose: Capture external user judgement and usability signal.
Must include: participant profile, method, dimensions, and result status.
Must not include: invented numbers before data lock.

### 3.3 Known Limitations
Purpose: State system boundaries and unresolved weaknesses.
Must include: technical limitations, operational constraints, and risk implications.
Must not include: mitigation plans that are not realistic within scope.

### 4. Evaluation
Purpose: Make a rigorous judgement on success against defined targets.
Must include: objective-by-objective evaluation, method caveats, theoretical consistency review.
Must not include: new implementation narratives.

### 4.1 Requirement Satisfaction
Purpose: Judge each requirement against target criteria.
Must include: target, observed result, and supporting evidence references.
Must not include: unrelated process detail.

### 4.1a Evaluation Methodology
Purpose: Explain why the evidence supports the conclusions.
Must include: evidence layers, validity caveats, and metric governance.
Must not include: repeated requirement table content.

### 4.1b Theoretical Validation
Purpose: Test whether chosen theories predicted outcomes.
Must include: claim, expected effect, observed effect, and validation status.
Must not include: broad literature survey detached from project evidence.

### 4.2 Strengths
Purpose: Highlight what worked best and why.
Must include: strongest validated outcomes with concrete evidence.
Must not include: generic praise without data.

### 4.3 Weaknesses & Trade-Offs
Purpose: Define confidence boundaries and compromises.
Must include: key weaknesses, trade-offs, and implications.
Must not include: defensive language that hides risk.

### 5. Reflection
Purpose: Show learning maturity and practical forward planning.
Must include: personal/professional growth, lessons, and forward direction.
Must not include: re-evaluating Section 4 metrics.

### 5.1 Personal Reflection
Purpose: Describe mindset and capability changes over the project timeline.
Must include: concrete shifts in judgement and working practice.
Must not include: technical deep dives.

### 5.2 Key Lessons
Purpose: Distill reusable lessons from successes and setbacks.
Must include: what would be repeated and what would be changed.
Must not include: broad statements without project grounding.

### 5.3 Future Work
Purpose: Propose realistic, scoped continuation work.
Must include: feasible extensions tied to known limitations.
Must not include: speculative roadmap without dependency awareness.

### 5.4 Research Directions
Purpose: Identify academically meaningful next questions.
Must include: testable follow-up questions linked to findings.
Must not include: implementation backlog details.

### 6. References
Purpose: Ensure verifiable academic attribution.
Must include: complete Harvard entries and citation consistency.
Must not include: uncited sources.

### 7. Appendices
Purpose: Store supplementary evidence and raw materials.
Must include: only support material referenced by the report.
Must not include: new arguments required for understanding the main report.

### Appendix A: Iterative Case Studies
Purpose: Provide detailed failure-to-fix traces and supporting snippets.
Must include: representative case chronology and validation notes.
Must not include: duplicate narrative already fully covered in main text.

### Appendix B: UAT Supporting Data
Purpose: Provide instruments, raw responses, and summary tables.
Must include: questionnaire, sample characteristics, and raw-to-summary mapping.
Must not include: privacy-sensitive personal identifiers.

### Appendix C: Project Development Diary
Purpose: Provide chronological evidence of project progress.
Must include: dated milestones, pivots, and key decisions.
Must not include: rewritten retrospective entries that change historical record.

---

## Control Rules for Drafting and Editing

- Budget tolerance: +/- 10% per subsection is allowed, but section totals must remain fixed.
- Reallocation rule: if one subsection exceeds budget, reduce another within the same section.
- Evidence-density rule (Sections 2 and 4): include at least one concrete evidence item every 120 to 180 words.
- Placeholder rule: only UAT numerical placeholders are allowed before final data lock.
- Metric governance rule: all metrics are point-in-time and may be refreshed during final validation without structural changes.

---

## Rationale for This Alignment

- The structure now matches Project-doc section names and numbering exactly.
- Section boundaries now prevent overlap between rationale, process, deliverable, evaluation, and reflection.
- Sub-subsections are explicitly defined in both the contents and execution plan for cleaner drafting control.
