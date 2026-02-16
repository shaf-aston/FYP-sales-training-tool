# STUDY DOCUMENTS: REMAINING FIXES

## Status: **3 Items Need Action**

---

## Fix 1: Information Extraction Metric Mismatch

**Location:** STUDY.docx → "Examiner Observation Metrics" table

**Problem:** You claim to measure 5 fields (outcome, problem, goal, consequence, duration), but your chatbot's `extract_preferences()` in `analysis.py` only extracts product preferences (reliability, budget, safety, etc.) — NOT these 5 fields.

**Options:**
| Option | Effort | Recommendation |
|--------|--------|----------------|
| A) Reduce to 3 fields | Low | ✅ **Do this** |
| B) Add extraction logic to code | High | Not worth it for UAT |

**Fix:** Change this row:
```
BEFORE: "Information Extraction Completeness | 5 fields captured (outcome, problem, goal, consequence, duration) | [Fields extracted: X/5] | ≥3/5 = Pass"

AFTER:  "Information Extraction Completeness | 3 fields captured (outcome, problem, goal) | [Fields extracted: X/3] | ≥2/3 = Pass"
```

**Reasoning:** Your prompts in `content.py` line 517 say "Extract: goals, problems, consequences" but there's no structured extraction happening. Reducing to 3 observable fields (what user wants, what's wrong, what they're trying to achieve) is realistic for manual observation.

---

## Fix 2: Tone Matching Target Unmeasurable

**Location:** STUDY.docx → Scenario 2 metrics (item 5) AND Examiner Tracking Sheet

**Problem:** "≥95% tone alignment" has no measurement method. You can't calculate a percentage during observation.

**Fix:** Change in TWO places:

**Scenario 2 (item 5):**
```
BEFORE: "Target: ≥95% tone alignment with buyer communication style."

AFTER:  "Target: Examiner observes consistent tone match (Yes/No). Validated via Questionnaire Q4 (≥3.5/5 mean score)."
```

**Examiner Tracking Sheet:**
```
BEFORE: "Tone Matching | Bot mirrors user formality | Yes/No | Yes = Pass"

AFTER:  (Already correct - keep as Yes/No)
```

**Reasoning:** Binary observation is realistic. The 95% figure is meaningless without automated analysis.

---

## Fix 3: Budget Alignment Depends on Missing Feature

**Location:** STUDY.docx → Scenario 2 metrics (item 4) AND Examiner Tracking Sheet

**Problem:** "100% of recommendations align with buyer's budget" assumes your chatbot tracks budget. Your `product_config.yaml` and prompts don't implement budget tracking.

**Options:**
| Option | Action |
|--------|--------|
| A) Remove metric | If budget not in scope |
| B) Mark as "N/A - Feature not implemented" | Honest for UAT |
| C) Add budget to scenario script | User states budget, examiner checks if response acknowledges it |

**Recommended Fix (Option C):**
```
BEFORE: "Budget Alignment | Target: 100% of recommendations align with buyer's budget"

AFTER:  "Budget Acknowledgment | Target: Bot acknowledges stated budget within 2 turns | Examiner records: Yes/No | Yes = Pass"
```

**Update Scenario 2 task:**
```
BEFORE: "You have a budget in mind and want quick answers"

AFTER:  "You have a budget of £20,000-£25,000 and want quick answers"
```

**Reasoning:** This makes the metric observable. If user says "my budget is £20k" and bot ignores it, that's a fail.

---

## Consistency Check: ✅ PASS

| Element | PIS | Consent | Study | Recruitment | Status |
|---------|-----|---------|-------|-------------|--------|
| Duration | 30 mins | — | 30-35 mins | 30 mins | ✅ Consistent |
| Withdrawal period | 2 weeks | 14 days | — | — | ✅ Same (14 days = 2 weeks) |
| Recording type | audio/video | audio/video | audio/video | — | ✅ Consistent |
| Anonymization | Yes | Yes | Yes | — | ✅ Consistent |
| Sample size | — | — | 10-15 | — | ✅ Stated |
| Participant split | — | — | 50/50 | — | ✅ Stated |

---

## Summary: What To Do

| # | Document | Section | Change |
|---|----------|---------|--------|
| 1 | STUDY.docx | Examiner Metrics table | Change "5 fields" → "3 fields", target "≥2/3" |
| 2 | STUDY.docx | Scenario 2, item 5 | Change "95%" → "Yes/No + Questionnaire Q4 ≥3.5" |
| 3 | STUDY.docx | Scenario 2, item 4 + task | Add explicit budget (£20-25k), change metric to "Budget Acknowledgment" |

**Everything else is consistent and complete.**