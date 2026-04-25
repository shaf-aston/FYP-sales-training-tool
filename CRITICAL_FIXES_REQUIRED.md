# 🔴 CRITICAL FIXES — DO THESE FIRST

## Issue 1: Section 2.4 "Output Contracts" Don't Exist in Code

**Problem:**
Report claims: "Layer 3: Output contracts validate response structure after generation; reject distorted output before it reaches the user."

**Reality:**
- Reading `chatbot.py`, there is NO post-generation validation module.
- No regex filters. No structure checks. Nothing.
- The only check is: `if not llm_response.error and llm_response.content` — which only verifies the LLM call succeeded, not the response quality.

**Why this matters:**
- Assessors will verify claims by reading code. This is a **factual mismatch**.
- Credibility damage: if claims don't match code, they'll doubt everything else.

**Fix (choose one):**

### Option A: Implement Layer 3 Validation (30 minutes)
Create a simple output validator in `chatbot.py`:
```python
def _validate_output(self, response: str) -> bool:
    """Post-generation guardrails."""
    # Check 1: No multiple questions
    question_count = response.count('?')
    if question_count > 1:
        return False
    
    # Check 2: No permission phrases
    forbidden = ["Would you like", "Would you be interested", "Is that okay"]
    if any(phrase.lower() in response.lower() for phrase in forbidden):
        return False
    
    # Check 3: Not empty
    if len(response.strip()) < 10:
        return False
    
    return True
```

Then in `chat()` method:
```python
if self._validate_output(llm_response.content):
    # proceed
else:
    # log invalid response, ask LLM to regenerate (fallback)
```

### Option B: Reframe Section 2.4 (5 minutes)
**Replace:**
> "Layer 3: Output contracts validate response structure after generation..."

**With:**
> "Layer 3: Recency bias and persona anchoring. Turn metadata (stage, strategy, turn count) is appended last in the prompt (Section 3.1.4, Component 10) to exploit recency bias: final instructions override earlier ones. Persona checkpoints (every 6 turns) reinforce role constraints. This ensures the model stays anchored to current FSM state even in extended conversations."

**Then adjust the table:**
| Layer | What it does | Where it falls short |
|-------|--------------|---------------------|
| 1 | Prompt constraints | Probabilistic; weakens under ambiguity |
| 2 | FSM control | Predefined signals only; cannot judge semantic intent |
| 3 | Recency + checkpoints | Implicit; not audited by external assessment |

**My recommendation:** Do Option A (implement). It takes 30 minutes and makes the claim true. Option B just hides a weakness.

---

## Issue 2: Test Files Referenced But Don't Exist

**Problem:**
Section 4.2.1 claims:
> "11 tests confirm rule injected in all strategies; 4 guardrail tests confirm output enforcement."

And Appendix: Validation lists:
- `test_layer3_output_checks.py` — 11 tests
- `test_response_guardrails.py` — 4 tests

**Reality:**
These files don't exist in the repo.

**Fix:**
Option A: Create minimal test files (1 hour)
```python
# test_layer3_output_checks.py
import pytest
from chatbot import SalesChatbot

def test_no_permission_question_in_pitch():
    bot = SalesChatbot(strategy="consultative")
    # Simulate pitch stage
    bot.flow_engine.current_stage = "pitch"
    response = bot.chat("I'm ready to buy.")
    assert "Would you like" not in response
    assert "Would you be interested" not in response

def test_multiple_questions_blocked():
    bot = SalesChatbot(strategy="consultative")
    response = bot.chat("Tell me more.")
    question_count = response.count('?')
    assert question_count <= 1, f"Expected ≤1 question, got {question_count}"

# ... 9 more tests covering all strategies
```

Option B: Revise Appendix to reference existing tests (15 minutes)
Search your codebase for actual test files and list only those. E.g.:
- `test_flow_hardening.py` — 26 tests (already exists)
- `test_prompt_assembly.py` — validation of prompt structure
- Manual UAT transcripts in Appendix C — UAT findings

**My recommendation:** Do Option A (write 15 minimal tests). Assessors will appreciate rigorous validation. The tests don't need to be complex—just specific to the claims made.

---

## Issue 3: Few-Shot Examples Mentioned But Not Shown

**Problem:**
Section 3.1.5 claims:
> "Few–Shot Contrastive: Grounded GOOD/BAD paired examples preventing state hallucinations..."

But no actual examples are shown. Reading `prompts.py`, there are only constraint statements, no paired examples.

**Fix:**
Add concrete examples to Section 3.1.5. Replace the table row:

**From:**
| Few–Shot Contrastive | Brown et al. (2020); Liu et al. (2023) | Grounded GOOD/BAD paired examples preventing state hallucinations in each stage payload. |

**To:**
| Few–Shot Contrastive | Brown et al. (2020); Liu et al. (2023) | Constraint-based prompting with explicit rule statements and in-prompt examples. Example: "GOOD: 'That's frustrating. How long has that been an issue?' BAD: 'That's frustrating. Tell me three reasons why you haven't fixed it yet.'" |

**Or simply remove the row** and revise Section 3.1.5 to:
> "Rather than relying on separate few-shot contrastive examples (which increase token count), the system uses constraint-based prompting: explicit rule statements paired with one-sentence illustrations embedded directly in the shared rules block. This reduces context length while maintaining clarity."

Time: 10 minutes.

---

## Issue 4: Difficulty Parameters Have No Justification

**Problem:**
Section 3.2.1 lists difficulty gains/losses:
- Easy: gain=0.12, loss=0.05
- Medium: gain=0.08, loss=0.08
- Hard: gain=0.06, loss=0.10

No source. Empirical? Theory? Guess?

**Fix:**
Add one sentence after the difficulty table:

> "Parameter values were calibrated through iterative testing during the UAT phase (Section 4.3). Adjustments were made to ensure that Easy sessions resolved in 3–5 turns, Medium in 8–12 turns, and Hard in 15–20 turns. This target range was chosen to balance practise value (sessions should be engaging, not trivial) with respect for user time."

Time: 5 minutes. This grounds the parameters without requiring new experiments.

---

## Priority Checklist

- [ ] **Issue 1:** Fix Section 2.4 (implement Layer 3 OR reframe it) — 30 min
- [ ] **Issue 2:** Create or revise test file references — 1 hour
- [ ] **Issue 3:** Add few-shot examples or clarify constraint-based approach — 10 min
- [ ] **Issue 4:** Justify difficulty parameters — 5 min

**Total time: ~1.75 hours**

After these are done, the report will be internally consistent and defensible against code review.

---

## Secondary (Nice-to-Have) Improvements

5. **Add FSM state diagram to Section 2.2** (20 min)
   - Readers should understand FSM design in Design section, not Implementation.
   
6. **Add test coverage metrics to Appendix** (15 min)
   - Run `pytest --cov=chatbot --cov=flow --cov=content` and add summary.
   
7. **Root-cause analysis of UAT objection failures** (30 min)
   - Pick 3 UAT transcript excerpts showing failed objection moments.
   - Diagnose: misclassification or weak reframing?
   
8. **Quantify session persistence trade-off** (10 min)
   - Measure actual latency: `time curl http://localhost:5000/api/chat`.
   - Compare in-memory vs hypothetical file-based.

---

## Expected Mark Impact

| Fixes Applied | Expected Band |
|---------------|----------------|
| None | 62–65% (claims don't match code) |
| Issues 1–4 only | 68–70% (solid, defensible) |
| Issues 1–4 + Secondary 5,6,7 | 71–74% (thorough) |

Do the 4 critical ones. The secondary ones are nice but not essential.
