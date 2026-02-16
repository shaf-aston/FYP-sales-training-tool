# 📋 STUDY DOCUMENTS REVIEW

**Overall Assessment:** **GOOD** - Minor Fixes Needed
Your ethics documents are well-structured and follow standard university protocols. The metrics are relevant to your chatbot. Below are specific items requiring attention.

---

## 🔴 MUST FIX (Ethics Approval Blockers)

| Document | Issue | Fix |
| :--- | :--- | :--- |
| **PIS** | Supervisor details incomplete | Add Sylvia Wong's email and phone |
| **PIS** | Version number placeholder | Replace `<enter version # here>` with actual version (e.g., "V1.0") |
| **Consent Form** | Version/date placeholders | Replace `<enter version # here>` and `<enter PIS date here>` |
| **PIS** | Funding statement uncertain | Confirm "Aston University" or "Self-funded" - remove "I BELIEVE SO" |

---

## 🟡 RECOMMENDED FIXES

| Document | Issue | Fix |
| :--- | :--- | :--- |
| **STUDY.docx** | "Information Extraction" metric lists 5 fields but chatbot may not capture all | Either reduce to 3 fields (outcome, problem, goal) OR ensure prompts actually extract these |
| **STUDY.docx** | "95% tone alignment" target is unmeasurable | Change to binary "Yes/No tone match observed" or use questionnaire Likert score |
| **STUDY.docx** | Scenario 2 targets (100% budget alignment, 90% feature clarity) lack measurement method | Add: "Examiner marks Yes/No during observation" |
| **PIS** | Withdrawal period inconsistent: "2 weeks" in PIS vs "14 days" in Consent | Use consistent wording (14 days = 2 weeks, but pick one) |

---

## ✅ METRICS ASSESSMENT

### Relevant & Appropriate Metrics

| Metric | Relevance | Measurable? |
| :--- | :--- | :--- |
| **Stage Progression Accuracy** | ✅ Core FSM functionality | **Yes** - observable transitions |
| **Time-to-Pitch (≤3 turns)** | ✅ Transactional efficiency | **Yes** - count turns |
| **Response Latency (<2s)** | ✅ UX quality | **Yes** - logged by system |
| **Low-Intent Handling** | ✅ Tests elicitation logic | **Yes** - binary observation |
| **Error Recovery** | ✅ Robustness | **Yes** - binary observation |
| **Tone Matching** | ✅ Adaptive behavior | ⚠️ **Subjective** - use questionnaire |

### Questionable Metrics

| Metric | Issue | Recommendation |
| :--- | :--- | :--- |
| **"Information Extraction (5/5 fields)"** | Your chatbot doesn't explicitly extract "consequence" or "duration" | Reduce to 3 fields OR add extraction logic |
| **"95% tone alignment"** | No way to measure percentage | Change to Likert scale from questionnaire |
| **"100% budget alignment"** | Depends on product config, not chatbot logic | Remove or mark as N/A if no budget feature |