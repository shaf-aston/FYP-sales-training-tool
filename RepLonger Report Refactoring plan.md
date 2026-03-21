# Implementation Prompt: Rewrite Project-doc.md from 41k → 10k Words

## SYSTEM PROMPT FOR THE IMPLEMENTING MODEL

You are rewriting a Final Year Project (FYP) report for a Computer Science student at Aston University. The current document (`Documentation/Project-doc.md`) is 41,214 words. The hard limit is 10,000 words (excluding code snippets, references, and appendices). You must produce a rewrite that maximises marks across five assessment aspects defined in the CS3IP mark scheme.

---

## SECTION 0: ANTI-WAFFLE RULES — READ BEFORE WRITING ANYTHING

1. **No buzzwords.** Do not write "leveraging", "holistic", "robust solution", "comprehensive framework", "seamless integration". Say what the thing does in plain English.
2. **No restating what you're about to say.** Do not write "This section will describe..." — just describe it.
3. **No filler transitions.** Do not write "Moving on to the next topic" or "Having established the above". Start the next paragraph.
4. **State each metric ONCE.** The numbers 92%, 95%, 100%, 88%, 980ms appear in the current doc ~15 times each. State them in Section 4.1 (Evaluation). Earlier sections should say "measured outcomes are reported in Section 4.1" — not repeat the numbers.
5. **Tables over prose.** If you can say it in a table, use a table. Tables convey 3x the information per word. The mark scheme rewards "examples and diagrams employed as a systematic aid to effective communication."
6. **No explaining what the mark scheme wants.** The current doc has internal notes like "(Mark scheme purpose: ...)". Remove ALL meta-commentary. The report IS the answer to the mark scheme; it should not discuss the mark scheme.
7. **Every paragraph must pass the "so what?" test.** If removing a paragraph changes nothing about the reader's understanding, remove it.
8. **Cross-reference supporting docs instead of repeating content.** The project has extensive supporting documentation. Use "see Appendix A" or "see ARCHITECTURE_CONSOLIDATED.md §6" instead of inlining 500 words of detail.
9. **No duplicate content across sections.** Each fact, metric, or explanation appears in ONE section. If it's needed elsewhere, cross-reference — don't re-explain. See the OVERLAP PREVENTION RULES below.

---

## SECTION 1: OVERLAP PREVENTION RULES

These are the specific overlap hotspots identified in the current 41k document. The implementing model MUST enforce these boundaries.

| Content | BELONGS IN | MUST NOT appear in |
|---------|-----------|-------------------|
| Prototyping phases, abandoned approaches, hardware constraints | Section 1.2 (context for WHY this approach) | Section 2 (which covers HOW the project was managed/built) |
| Theory-to-code table (SPIN, NEPQ, etc.) | Section 1.4 | Sections 2, 3, 4, 5 |
| Metric values (92%, 88%, 95%, 980ms, etc.) | Section 4.1 (FR/NFR tables) | Sections 1, 2, 3 (use "see §4.1" instead) |
| Strategy→FSM pivot narrative + metrics | Section 2.2 | Sections 1, 3, 5 |
| How each module works internally | Section 3.1 | Section 2 (which covers *why* decisions were made, not *how* modules work) |
| Personal growth / mindset shift | Section 5.1 | Sections 2, 4 |
| Technical lessons ("first fix was wrong") | Section 5.2 | Section 2 |
| Stakeholder-specific feature descriptions | Section 1.1 (brief, 1 sentence each) | NOT re-described in Section 3.1 — just list features |
| Risk register + outcomes | Section 2.5 | NOT repeated in Section 4 |
| Testing results (pass/fail counts) | Section 3.2 | NOT repeated in Section 4.1 (reference "evidence in §3.2") |
| Code snippets | Appendix A only | NOT inline in Sections 2 or 3 (reference them) |
| UAT methodology + results | Section 3.2 (methodology + results table) | Section 4 references UAT findings but does NOT re-describe the methodology |

**Estimated word savings from overlap prevention: ~3,000 words** — this is what makes 10k achievable.

---

## SECTION 2: MARK SCHEME ASPECTS AND WHAT SCORES 70-79%

For each aspect, the exact 70-79% descriptor from the mark scheme. Write to hit THESE descriptors specifically.

### Aspect Weights (from mark scheme analysis):

| Aspect | Mark Scheme Weight | Target Grade Band | Report Sections |
|--------|-------------------|-------------------|-----------------|
| Contextual Investigation | 15-20% | 70-79% | Section 1 |
| Project Process & Professionalism | 20-25% | 70-79% | Section 2 |
| **The Deliverable** | **25-30%** (highest) | 70-79% | Section 3 |
| Evaluation & Reflection | 20-25% (combined) | 70-79% | Sections 4 + 5 |
| Exposition | 10-15% | 70-79% | Entire report quality |

**Critical insight:** Section 3 (Deliverable) carries the highest weight. But the deliverable is assessed partly by THE SOFTWARE ITSELF, not just the report section. Section 3 needs to concisely demonstrate what was built and that it works — the assessor will also see the live system. Don't waste words on walkthrough prose; use tables and diagrams.

---

**1. Contextual Investigation (Section 1) — Budget: 1,500 words**
> 70-79%: "Evidence of both thoroughness (attention to detail and scope) and depth of insight into the problems raised by the development of the deliverable and the range of objectives that the development pursued."

What this means: Show DEPTH, not breadth. Section 1 now includes the prototyping journey and abandoned approaches (moved from old Section 2.0) because these are *context for why the approach was chosen* — they establish the problem space. The narrative flow is: business problem → what was tried → why it failed → hypothesis → theory → objectives. Every theory needs: (a) what the system would have done wrong without it, (b) what it does right because of it, (c) exact code location.

**2. Project Process (Section 2) — Budget: 3,700 words**
> 70-79%: "The development or research/experimental process shows insight and innovation. There is strong evidence of consistent attention to quality."

What this means: Show DECISIONS, not just activities. Section 2 no longer includes initial scope/prototyping (moved to Section 1). It starts at Requirements and covers how the project was managed, iterated, and built. Every subsection should answer "why did you do X instead of Y, and what evidence drove that choice?" The Strategy→FSM pivot is the best example: concrete metrics (855→430 LOC, 45→10 min review time) drove the decision.

**3. Deliverable (Section 3) — Budget: 1,800 words**
> 70-79%: "The deliverable shows insight and innovation. There is strong evidence of consistent attention to quality."

What this means: Describe what was BUILT and show it WORKS. Architecture diagram, module table, key features, test results, UAT results, known limitations. Do not re-explain the process (Section 2).

**4. Evaluation (Section 4) — Budget: 1,200 words**
> 70-79%: "Evaluation processes show evidence of careful design. There is substantial evidence of reflection on the processes and outcomes of the work, leading to exposition of insights gained."

What this means: THIS is where metrics go. Requirements table with target vs achieved. Theory validation table. Honest weaknesses. Developer-bias caveat. All metrics must state WHO measured, HOW, and WHEN (Rule 5 in feedback_writing_best_practices.md).

**5. Reflection (Section 5) — Budget: 600 words**
> 70-79%: Report "very well written: all the expected material is expounded in a well organised manner."

What this means: Personal growth narrative ONLY. First person. No technical rehash. The Week 8 mindset shift is the strongest story. This section must be COMPLETELY REWRITTEN — the current version contains ~800 words of technical detail that belongs in Sections 2-3.

---

## SECTION 3: WORD COUNT BUDGET — SECTION + SUBSECTION LEVEL

### Budget Summary

| Section | Max Words | % of Total |
|---------|-----------|------------|
| Front matter + Abstract | 200 | 2% |
| Section 1 (Context + Exploration) | 1,500 | 16% |
| Section 2 (Process) | 3,700 | 39% |
| Section 3 (Deliverable) | 1,800 | 19% |
| Section 4 (Evaluation) | 1,200 | 12.5% |
| Section 5 (Reflection) | 600 | 6% |
| **Total** | **~9,000** | **Buffer: ~1,000 words for tables/transitions** |

### Subsection-Level Budgets

```
ABSTRACT                                          ~150 words

1. CONTEXT, EXPLORATION & RATIONALE              ~1,500 words total
   1.1 Problem Domain & Business Context           300 words
       - Cost/scalability/engagement gap             150 words
       - 3 stakeholder groups (1 sentence each)      100 words
       - The technical problem: LLM drift             50 words
   1.2 Technical Exploration & Previous Approaches  500 words
       - Initial conception + voice pivot             50 words
       - Hardware constraints (table + conclusion)   150 words
       - STT analysis (2 sentences)                   30 words
       - Prototyping phases (3 × ~80 words)          240 words
       - Abandoned approaches (bullet list)           30 words
   1.3 Research Question & Hypothesis               150 words
       - Flows FROM 1.2 — "neither alone → hypothesis"
       - Fine-tuning rejection table (PRESERVE)
       - Research question (1 sentence)
   1.4 Sales Structure Foundation (THEORY TABLE)    300 words
       - 6-row theory-to-code table                  250 words
       - 2-3 sentences connecting prose                50 words
   1.5 Critical Analysis & Competitive Diff.        150 words
       - Competitor table (5 rows)                   100 words
       - 4 USPs as bullet points                      50 words
   1.6 Project Objectives (SMART table)             100 words
       - O1-O5 table
       - "Measured outcomes in Section 4.1"

2. PROJECT PROCESS & PROFESSIONALISM             ~3,700 words total
   2.1 Requirements Specification                   400 words
       2.1.1 FR table + NFR table                   200 words
       2.1.2 Requirements evolution + timeline       200 words
   2.2 Architecture & Design                        500 words
       2.2.1 Strategy→FSM pivot + metrics table     300 words
       2.2.2 Why FSM fits the problem                100 words
       2.2.3 FSM state diagram (Mermaid)             100 words
   2.3 Iterative Development & Prompt Eng.          600 words
       2.3.1 6-problem table (PRESERVE VERBATIM)    350 words
       2.3.2 Iteration methodology (1 paragraph)    100 words
       2.3.3 Code snippet references (to Appendix)  150 words
   2.4 Implementation Details                       200 words
       2.4.1 Provider abstraction anecdote           200 words
   2.5 Risk Management                              200 words
       Risk table (5 rows) + 1 sentence summary     200 words
   2.6 Professional Practice                        300 words
       2.6.1 Applied standards table (6 rows)        150 words
       2.6.2 Code audit summary (1 paragraph)        100 words
       2.6.3 Git workflow (1 paragraph)               50 words
   2.7 Monitoring, Effort & Estimation              300 words
       Plan-vs-actual table                          100 words
       Effort estimation table                       100 words
       Estimation lesson (1 paragraph)               100 words
   2.8 Ethics & Security                            400 words
       2.8.1 Data privacy (1 paragraph)              100 words
       2.8.2 STRIDE summary table (6 rows)           150 words
       2.8.3 AI ethics (1 paragraph)                 100 words
       2.8.4 Security posture honest assessment       50 words

3. DELIVERABLE                                   ~1,800 words total
   3.1 Implementation Outcomes                      700 words
       System architecture diagram (Mermaid)         (excluded — diagram)
       Module structure table                        200 words
       Key features (bullet list)                    200 words
       NEPQ stage mapping table                      200 words
       Quiz module (3 sentences)                     100 words
   3.2 Testing & Validation (incl. UAT)             700 words
       3.2.1 Automated tests summary                 150 words
       3.2.2 Manual scenario testing summary         150 words
       3.2.3 UAT Methodology & Results (NEW)         400 words
   3.3 Known Limitations                            400 words
       7 limitations × ~55 words each               400 words

4. EVALUATION                                    ~1,200 words total
   4.1 Requirement Satisfaction                     400 words
       FR achievement table (R1-R5)                  150 words
       NFR achievement table (NF1-NF5)               150 words
       Stakeholder alignment (3 sentences)           100 words
   4.1a Evaluation Methodology                      150 words
       Two-layer approach + developer bias caveat    150 words
   4.1b Theoretical Validation                      200 words
       Theory validation table (7 rows)              150 words
       Honest assessment (1 paragraph)                50 words
   4.2 Strengths                                    200 words
       3 strengths with evidence                     200 words
   4.3 Weaknesses & Trade-Offs                      250 words
       Developer bias, UAT findings, security,       250 words
       guardedness edge cases, no structured logging

5. REFLECTION                                      ~600 words total
   5.1 Personal Reflection                          200 words
       Week 1-8 mindset shift                       100 words
       Before/after table (PRESERVE VERBATIM)        100 words
   5.2 Key Lessons                                  200 words
       3 lessons with specific examples              200 words
   5.3 Future Work                                  150 words
       4 realistic extensions                        150 words
   5.4 Research Directions                           50 words
       3 bullet points                                50 words
```

---

## SECTION 4: EXACT STRUCTURE TO PRODUCE

```
# Sales Roleplay Chatbot - CS3IP Project

> Module/Student/Supervisor/Period/Deliverable/Tech Stack metadata block

## Abstract (~150 words)
- Problem: sales training cost/scale gap
- Method: FSM + LLM hybrid, no fine-tuning
- Key outcomes: forward-ref Section 4.1

## 1. Context, Exploration & Rationale (~1,500 words)

### 1.1 Problem Domain & Business Context (~300 words)
- The cost/scalability/engagement gap (3 bullet points with evidence)
- 3 stakeholder groups (1 sentence each — NO implementation detail)
- The technical problem: LLM drift (2 sentences)

### 1.2 Technical Exploration & Previous Approaches (~500 words)
- Initial conception (2 sentences: voice-first platform, pivoted to text)
- Hardware constraints (keep the table, 1 sentence conclusion)
- STT analysis (2 sentences: Whisper too slow, Google too expensive)
- Prototyping phases — 3 SHORT paragraphs (~80 words each):
  Phase 1 (local LLM): quality failures + latency. Conclusion: local infeasible.
  Phase 2 (kalap_v2): perfect sequencing but rigid. Key insight: PhaseManager was already an FSM.
  Phase 3 (hybrid): "hallucinated stage adherence" problem → FSM enforces WHEN, LLM generates WHAT.
- Abandoned approaches: bullet list (3-5 items, 1 sentence each)
- LLM selection: model comparison table + 1-sentence conclusion

### 1.3 Research Question & Architectural Hypothesis (~150 words)
- Flows DIRECTLY from 1.2 — "neither approach alone was sufficient"
- State the hypothesis: separate structure from generation
- Fine-tuning rejection: the cost/benefit table (keep the table, cut the prose)
- Research question (1 sentence)

### 1.4 Sales Structure Foundation (~300 words)
- USE A TABLE. 6 theories, each row: Theory | Problem It Solved | Code Location | Measured Impact
- 2-3 sentences of connecting prose
- NO standalone paragraphs per theory — the table IS the section

### 1.5 Critical Analysis & Competitive Differentiation (~150 words)
- Competitor table (keep from current doc — 5 rows)
- 4 USPs as bullet points (1 sentence each)

### 1.6 Project Objectives (~100 words)
- SMART objectives table (5 rows: O1-O5)
- "Measured outcomes in Section 4.1" — do NOT put results here

## 2. Project Process & Professionalism (~3,700 words)

NOTE: Section 2 no longer includes initial scope/prototyping (now in Section 1.2). It starts at Requirements.

### 2.1 Requirements Specification (~400 words)
- How constraints shaped requirements (3 bullet points)
- Requirements evolution: what was dropped/added and why (condensed)
- FR table (R1-R5) — keep from current doc
- NFR table (NF1-NF5) — keep from current doc
- "Formal artefacts index: see ARCHITECTURE_CONSOLIDATED.md" (do NOT inline the 30-row table)

### 2.2 Architecture & Design (~500 words)
- Strategy→FSM pivot: the metrics table (keep — files, LOC, review time, feature time)
- Why FSM fits the problem (3 sentences, not 3 paragraphs)
- FSM state diagram (Mermaid — keep the consultative flow diagram)
- SRP extraction: what was extracted, why, measurable outcome (1 paragraph)

### 2.3 Iterative Development & Prompt Engineering (~600 words)
- The 6-problem table (currently at lines 768-776 in old doc) — KEEP THIS TABLE VERBATIM. It is the single most mark-scoring element in Section 2.
- 1 paragraph on the small-talk loop fix (best anecdote: over-engineering → simplification)
- 1 paragraph on iteration methodology (observe → hypothesise → fix → validate)
- "Code snippets supporting these fixes: see Appendix A"
- "Testing framework details: see Section 3.2"

### 2.4 Implementation Details (~200 words)
- Provider abstraction: the anecdote (Groq rate-limited, factory pattern saved the project)
- Before/after code comparison (2-line vs 25-line — keep this)
- Cloud vs local comparison table (condensed)

### 2.5 Risk Management (~200 words)
- Condensed risk table: 5 rows max (R1-R5 from current doc, merged where duplicate)
- 1 sentence: "How risks drove architecture" — R1→provider abstraction, R2→FSM redesign

### 2.6 Professional Practice (~300 words)
- 3 lessons via anecdotes (SRP prevents hidden bugs, pure functions eliminate mocks, config over code)
- Applied standards summary table (keep — 6 rows)
- Code audit summary: what was found, what was fixed (1 paragraph, ref technical_audit.md for detail)
- Git workflow (1 paragraph)

### 2.7 Monitoring, Effort & Estimation (~300 words)
- Plan-vs-actual table (keep — 5 phase rows)
- Effort estimation table (keep — prompt eng estimate vs actual)
- The estimation lesson (1 paragraph: prompt engineering ≠ code debugging, empirical not analytical)
- Effort breakdown table (keep — 5 component rows)

### 2.8 Ethics & Security (~400 words)
- Data privacy (1 paragraph: in-memory only, GDPR Art 5(1)(e), no PII persisted)
- STRIDE summary: condensed table (6 rows, no code, no line numbers)
- "Full STRIDE analysis with implementation detail: see Documentation/Security-Analysis.md"
- AI ethics (1 paragraph: transparency, methodology scope, intended use boundary)
- Security posture honest assessment (2 sentences)

## 3. Deliverable (~1,800 words)

### 3.1 Implementation Outcomes (~700 words)
- System architecture diagram (Mermaid — keep from current doc)
- Module structure table: module | LOC | responsibility (keep, condensed)
- Key features list (bullet points): FSM engine, prompt generation, NLU pipeline, provider abstraction, training coach, quiz assessment, web interface, message rewind
- NEPQ stage mapping table (keep — 5 rows)
- Quiz module (3 sentences + ref Quiz-Feature-Development.md)

### 3.2 Testing & Validation (incl. UAT) (~700 words)

#### 3.2.1 Automated Testing (~150 words)
- Scope: 9 active modules, 209 tests, 186 pass, 23 fail
- State distribution of failures (19 security contract, 2 consultative edge, 1 intent-lock, 1 performance)
- Quiz tests: 26/26 pass

#### 3.2.2 Manual Scenario Testing (~150 words)
- 25 structured scenarios, results summary table by category
- 2-sentence methodology: why both layers needed

#### 3.2.3 User Acceptance Testing (UAT) (~400 words)
THIS IS A NEW SUBSECTION. The student is currently collecting UAT data. Write the structure with placeholders for results.

**What to include:**
- **Methodology summary** (~100 words): Participants (state who — classmates, friends, non-professional contacts; state count), session format (conversation + questionnaire), 3 standardised scenarios (consultative/transactional/mixed-intent — 1 sentence each)
- **Questionnaire dimensions** (~50 words): Likert scale table (Q1-Q6 from current Section 4.1a — naturalness, topic adherence, flow appropriateness, objection handling, methodology adherence, perceived utility). Keep the table.
- **Results table** (~100 words): ⚠️ PLACEHOLDER — format as:

```markdown
| Dimension | Mean (1-5) | SD | n |
|-----------|-----------|-----|---|
| Naturalness (Q1) | ⚠️ [FILL] | ⚠️ | ⚠️ |
| Topic adherence (Q2) | ⚠️ [FILL] | ⚠️ | ⚠️ |
| Flow appropriateness (Q3) | ⚠️ [FILL] | ⚠️ | ⚠️ |
| Objection handling (Q4) | ⚠️ [FILL] | ⚠️ | ⚠️ |
| Methodology adherence (Q5) | ⚠️ [FILL] | ⚠️ | ⚠️ |
| Perceived utility (Q6) | ⚠️ [FILL] | ⚠️ | ⚠️ |
```

- **Qualitative findings** (~100 words): ⚠️ PLACEHOLDER — format as:
  - "What felt most realistic?" → ⚠️ [INSERT THEMES FROM RESPONSES]
  - "What felt most unnatural?" → ⚠️ [INSERT THEMES FROM RESPONSES]
  - "At what point did the bot lose the thread?" → ⚠️ [INSERT THEMES FROM RESPONSES]

- **Limitations of this evaluation** (~50 words): Sample size below statistical significance, participants not sales professionals, no control condition. State honestly. Reference the full UAT protocol in Section 4.1a for the rigorous next step.

**Why UAT goes in Section 3.2 (not Section 4):** Section 3 = "what was built and does it work?" UAT provides evidence that it works from external perspectives. Section 4 then INTERPRETS these findings against objectives — it doesn't re-describe the testing.

### 3.3 Known Limitations (~400 words)
- 7 limitations as numbered list, 2 sentences each max
- No retry logic, prompt injection risk, single-instance deployment, regression gaps, in-memory sessions, no structured logging, LLM non-determinism

## 4. Evaluation (~1,200 words)

### 4.1 Requirement Satisfaction (~400 words)
- FR achievement table (R1-R5 with evidence column — reference "evidence in §3.2")
- NFR achievement table (NF1-NF5 with target, achieved, evidence)
- Stakeholder alignment (3 sentences)
- Reference UAT findings from §3.2.3 where they support FR/NFR claims (do NOT re-describe UAT methodology here)

### 4.1a Evaluation Methodology (~150 words)
- Three-layer approach: automated regression + manual scenario testing + preliminary UAT
- Developer bias caveat stated explicitly
- "UAT methodology and results are reported in §3.2.3" — do NOT re-describe here

### 4.1b Theoretical Validation (~200 words)
- Theory validation table: 7 rows (theory, prediction, result, validated?)
- 1 paragraph honest assessment: 6/7 validated, 1 partial (SPIN close rates unmeasured)

### 4.2 Strengths (~200 words)
- Maintainability (the 30-min transactional flow addition anecdote)
- Separation of concerns held under pressure
- 92% stage accuracy validates core thesis

### 4.3 Weaknesses (~250 words)
- Developer bias (biggest gap)
- UAT limitations: ⚠️ [INCORPORATE ACTUAL FINDINGS — what did testers struggle with? What surprised you?]
- Security posture trade-offs
- Guardedness edge cases
- No structured logging

## 5. Reflection (~600 words)

### 5.1 Personal Reflection (~200 words)
- Week 1-3 → Week 8 mindset shift (academic→professional)
- The before/after table (keep: "My design follows best practices" → "My design creates maintenance burden")

### 5.2 Key Lessons (~200 words)
- "The first fix was always wrong" — permission questions needed 3 layers
- Prompt engineering is a control discipline, not a workaround
- Measure the cost of staying, not just the cost of leaving

### 5.3 Future Work (~150 words)
- Training effectiveness validation (the unanswered question)
- Independent UAT with sales professionals
- Methodology generalizability (BANT, MEDDIC)
- Voice pipeline (deferred, not abandoned)

### 5.4 Research Directions (~50 words)
- 3 bullet points: comparative methodology, prompt engineering optimisation, LLM behavioural reliability

## 6. References (excluded from word count)
Keep all current references. Harvard format.

## Appendices (excluded from word count)
- Appendix A: Iterative Case Studies (code snippets, iteration cycles)
- Appendix B: UAT Supporting Data (full questionnaire, raw responses, conversation transcripts)
- Appendix C: Project Development Diary (ref Diary.md)
```

---

## SECTION 5: BEFORE YOU START WRITING — PRE-FLIGHT CHECKLIST

### Files you MUST read first
1. `Documentation/Project-doc.md` — The source document (read ALL of it in chunks)
2. `Documentation/ARCHITECTURE_CONSOLIDATED.md` — To know what you can reference
3. `Documentation/Diary.md` — To know what's already in the diary
4. `Documentation/feedback_writing_best_practices.md` (in `.claude/projects/.../memory/`) — MANDATORY writing rules
5. `Mark Scheme FYP -2025-6.pdf` or its extracted text — To understand scoring criteria

### Files you must CREATE
1. `Documentation/Security-Analysis.md` — Move the STRIDE table + all code from old Section 2.9.3-2.9.5 here. Add a header "# Security Analysis — STRIDE Threat Model & Implementation Details" and note "This document supplements the security summary in the main project report (Section 2.8)."
2. `Documentation/Artifact-Traceability.md` — Move the entire Appendix B traceability matrix here. Add header "# Artifact Traceability Matrix" and note "This appendix supports the main project report Section 2.1."

### Files you must MODIFY
1. `Documentation/Project-doc.md` — Complete rewrite (the main task)

---

## SECTION 6: CONTENT TO PRESERVE VERBATIM

These specific tables/elements are high-value and should be kept as-is:

1. **Fine-tuning rejection table** (lines 301-305): the Prompt Engineering vs Fine-Tuning comparison
2. **Competitor table** (lines 352-358): platform comparison
3. **SMART objectives table** (lines 382-389): O1-O5
4. **FR table** (lines 630-636): R1-R5
5. **NFR table** (lines 640-646): NF1-NF5
6. **6-problem iterative fixes table** (lines 768-776): THE most important table
7. **Strategy→FSM metrics table** (lines 1267-1273 or 1445-1453): architecture comparison
8. **FSM state diagram** (lines 1380-1431): Mermaid consultative flow
9. **Plan-vs-actual table** (lines 720-727): phase estimation comparison
10. **Effort breakdown table** (lines 2196-2202): component effort
11. **Theory validation table** (lines 2952-2960): Section 4.1b
12. **Before/after mindset table** (lines 3033-3037): Section 5.1

---

## SECTION 7: CONTENT TO DELETE ENTIRELY

1. Lines 89-211: "DETAILED SECTION PLAN & EXECUTION GUIDE" — internal scaffolding
2. Lines 224-246: Acronym list — unnecessary at this length
3. All `⚠️ [Student action required]` figure placeholder instructions (lines 271, 2757-2770, 2206-2220, 2962-2976) — these are instructions to the student, not report content. **EXCEPTION:** Keep ⚠️ placeholders for UAT data that the student will fill in.
4. Lines 1848-1923: DUPLICATE of Section 2.5 (Professional Practice appears twice)
5. Lines 1951-2060: DUPLICATE of Section 2.6 (Risk Management appears twice)
6. Lines 2063-2161: DUPLICATE of Section 2.7 (Monitoring appears twice)
7. Lines 2296-2467: Section 2.9.5 code implementations (moved to Security-Analysis.md)
8. Lines 2622-2694: Elicitation tactics lists + spaCy/fuzzy matching justifications (500+ words on NLU tool selection — condense to 1 sentence: "spaCy and fuzzy matching were evaluated and rejected; regex with word boundaries provided better accuracy for domain-specific keyword detection at lower deployment complexity")
9. Lines 3129-3195: Appendix B in main body (moved to Artifact-Traceability.md)
10. Lines 3172-3195: B.2/B.3 summary statistics and critical path (moved with Appendix B)
11. The `metrics.jsonl` format explanation paragraph (line 3172) — implementation detail
12. All "Organisation of this report:" meta-descriptions (line 251-253)

---

## SECTION 8: SPECIFIC WRITING INSTRUCTIONS FOR KEY SECTIONS

### Section 1.2 (Technical Exploration) — DO THIS:
This section tells the "journey to the final architecture" story. It replaces old Section 2.0. Pattern for each phase: What was tried → What failed → What was learned. Keep each phase to ~80 words (shorter than old plan's 150).

**Phase 1 (~80 words):** Local LLM (Qwen2.5-0.5B→1.5B) — quality failures (role confusion, context loss) — latency 2-5 min — root cause: hardware (38 GB/s, thermal throttling) — conclusion: local infeasible.

**Phase 2 (~80 words):** Deterministic fuzzy matching (kalap_v2) — near-instant, perfect sequencing — but rigid, no adaptation — key insight: the PhaseManager was already an FSM.

**Phase 3 (~80 words):** Discovered "hallucinated stage adherence" — FSM enforces WHEN (deterministic), LLM generates WHAT (natural language) — advancement requires specific signals; without them, FSM holds.

**Abandoned approaches (~30 words):** Bullet list. Fine-tuning (cost), Strategy Pattern (maintenance), voice pipeline (latency), AI-generated code (no problem-solving). One sentence each.

### Section 1.4 (Theory Foundation) — DO THIS:
Write it as ONE table with connecting prose. Do NOT write a standalone paragraph per theory.

```markdown
| Theory | Problem It Solved | Implementation | Measured Impact |
|--------|-------------------|----------------|-----------------|
| SPIN Selling (Rackham, 1988) | Bot advanced after N turns regardless of content (40% false positives) | `doubt_keywords` in `analysis_config.yaml`; `_check_advancement_condition()` in `flow.py` | 40% → 92% stage accuracy |
| NEPQ/Kahneman (Acuff & Miner, 2023) | Bot generated counter-arguments to objections (addressed rational justification, not emotional trigger) | Objection prompt probes for emotional cost, not counter-argument | 65% → 88% objection resolution |
| Constitutional AI (Bai et al., 2022) | LLM ended pitches with permission questions 75% of the time | P1/P2/P3 constraint hierarchy in all stage prompts | 75% → 0% permission questions |
| Chain-of-Thought (Wei et al., 2022) | Bot knew WHAT to do on objections but not HOW to reason through them | IDENTIFY→RECALL→CONNECT→REFRAME scaffold in objection prompt | 65% → 88% resolution with explicit reasoning steps |
| Lexical Entrainment (Brennan & Clark, 1996) | Bot rephrased prospect's words with synonyms; felt mechanical | `extract_user_keywords()` injects prospect's exact terms | Eliminated mechanical parroting |
| Conversational Repair (Schegloff, 1992) | Bot continued probing after "just show me the price" | `user_demands_directness()` jumps FSM to Pitch | 100% urgency detection |
```

Then 2-3 sentences of connecting prose: "These six theories were not selected from a literature survey and then applied. Each was researched in response to a specific observed failure during testing (Section 2.3.1). The architecture draws on each to resolve a different behavioural requirement."

### Section 3.2.3 (UAT) — DO THIS:
This is NEW content. The student is actively collecting data. Write the methodology and structure, with ⚠️ placeholders for all results.

**Structure:**
1. State participants and method (who, how many, what they did)
2. Likert scale questionnaire table (Q1-Q6 — copy from current Section 4.1a)
3. Results table with ⚠️ [FILL] placeholders for mean/SD/n
4. Qualitative themes with ⚠️ [INSERT] placeholders
5. Limitations paragraph (sample size, non-professional, no control)

**Tone:** Honest. State what the UAT can and cannot tell you. It provides preliminary external signal, not statistical proof.

### Section 4.3 (Weaknesses) — DO THIS:
Be genuinely honest. The mark scheme at 70-79% says "substantial evidence of reflection." State weaknesses plainly:

"The biggest gap is independent user testing. Every accuracy metric was produced by the developer testing a system they built. Preliminary UAT (§3.2.3) provides initial external signal but is limited in scope."

Then incorporate UAT findings: ⚠️ [AFTER UAT DATA IS AVAILABLE: What did external testers struggle with? What surprised the developer? What edge cases were surfaced that weren't in the 25-scenario test set?]

Note the framing shift: if UAT data arrives, Section 4.3 should acknowledge what the UAT revealed as weaknesses (not just developer-assessed gaps). This makes the evaluation more honest and credible.

### Section 5 (Reflection) — COMPLETE REWRITE:
The current Section 5 contains ~800 words of technical detail. ALL of that belongs in Sections 2-3.

Section 5 should contain ONLY:
- Personal mindset shifts (the academic→professional journey)
- What surprised you about yourself as a developer
- What you'd do differently (with specific reasons, not generic wisdom)
- Future directions (realistic, not wish lists)

Write in first person. No code references. No metrics. No module names.

---

## SECTION 9: VERIFICATION AFTER WRITING

1. Run: `wc -w Documentation/Project-doc.md` — must be ≤10,500
2. Check word count per section using `##` headers as boundaries — no section should exceed its budget by more than 10%
3. Check each mark scheme aspect has dedicated coverage:
   - Contextual Investigation → Section 1 exists with theory-to-code links
   - Process → Section 2 shows iterative development with metrics
   - Deliverable → Section 3 describes what was built with testing evidence (including UAT)
   - Evaluation → Section 4 has requirement satisfaction + honest weaknesses
   - Reflection → Section 5 has personal growth narrative
4. Check no metric appears more than twice (once in definition, once in evaluation)
5. Check all cross-references resolve (ARCHITECTURE_CONSOLIDATED.md, Security-Analysis.md, etc.)
6. Check no ⚠️ student-action blocks remain EXCEPT legitimate UAT data placeholders
7. Check no duplicate sections remain
8. Check the OVERLAP PREVENTION rules in Section 1 — verify no content appears in a "MUST NOT" column section
9. Verify UAT section (3.2.3) has complete structure with ⚠️ placeholders for data

---

## SECTION 10: WORD COUNT BUDGET SUMMARY

| Section | Max Words | Key Content |
|---------|-----------|-------------|
| Front matter + Abstract | 200 | Metadata, problem/method/outcome |
| Section 1 | 1,500 | Problem, exploration/previous approaches, hypothesis, theory table, competitors, objectives |
| Section 2 | 3,700 | Requirements, architecture, iteration, implementation, risk, practice, estimation, ethics |
| Section 3 | 1,800 | Architecture diagram, modules, features, testing, **UAT results**, limitations |
| Section 4 | 1,200 | Requirements met, theory validation, strengths, weaknesses |
| Section 5 | 600 | Personal reflection, lessons, future work |
| **Total** | **~9,000** | Buffer of ~1,000 words for tables/transitions |

**Hard ceiling: 10,000 words.** If the total exceeds 10,000, cut in this priority order:
1. Section 1.2 (Technical Exploration) — compress prototyping phases further or move hardware table to Appendix
2. Section 3.3 (Known Limitations) — reduce from 7 to 5 most important
3. Section 2.8 (Ethics & Security) — condense STRIDE table further
4. Section 1.5 (Competitors) — reduce to 3 rows

**Recommendation:** Run `wc -w` verification before finalising. Use the line-by-line budget in Section 3 to catch overruns early.
