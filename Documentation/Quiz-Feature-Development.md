# Quiz Assessment Feature — Development Documentation

**Date Completed:** 18 March 2026
**Development Methodology:** TDD (deterministic logic) + Feature-First (LLM evaluation)
**Lines of Code:** ~370 (quiz.py) + ~105 (config) + ~410 (API/UI/CSS) + ~295 (tests) = ~1,180 total
**Test Coverage:** 26 automated tests; 100% pass rate

---

## 1. Problem Statement & Rationale

### The Training Gap

**Supervisor Feedback (Meeting 5, February 2026):**
The chatbot's core functionality — holding realistic conversations — does not directly validate that a trainee *understands* the sales process. A user could replay conversations and memorize responses without internalizing:
- What stage they're in and why
- What triggers advancement between stages
- Whether their next move aligns with the current stage goal
- How their conversation trajectory connects to NEPQ methodology

**Business Impact:**
Without assessment, the tool cannot differentiate between:
- A trainee who has learned (can explain concepts and apply them)
- A trainee who has only mimicked (can repeat bot responses but cannot generate novel appropriate ones)

This limits the tool's value in a training programme where practitioners must demonstrate competency, not just practice.

---

## 2. Methodology: TDD for Deterministic Logic, Feature-First for LLM

### The Split

The quiz feature has two evaluation types with different testability properties:

| Quiz Type | Output | Testable at Build Time? | Methodology |
|-----------|--------|-------------------------|-------------|
| Stage identification | Binary correct/incorrect | Yes — one correct answer per FSM state | **TDD (test-first)** |
| Next move / Direction | 0–100 score + feedback | No — multiple valid answers; LLM output varies between calls | **Feature-first + runtime validation** |

### Why TDD for Stage Quiz

The stage quiz evaluates free-text input against known FSM state. The matching logic must handle edge cases:
- Case variation: "LOGICAL" must match "logical"
- Partial answers: "pitch" alone (missing strategy) must score incorrect
- Natural language: "We're in the emotional stage using consultative" must extract keywords

These cases are **enumerable in advance** — there is no ambiguity about what the correct output should be for any given input. This is the precondition for test-first development: the acceptance criteria are fully specifiable before implementation.

**Why test-first, not test-after?** Writing the 10 `TestStageQuizEvaluation` tests first forced every edge case to be an explicit design decision *before* the matching code existed. For example, `test_case_insensitive` decided that case should not matter before the implementation was written. Without test-first, the likely path is: implement exact match, discover case mismatch during manual testing, retrofit case handling, hope no other edge cases remain. TDD eliminated that discover-and-patch cycle.

**Why test-first, not no-tests?** The stage quiz is correctness-critical. If it scores a correct answer as wrong, the trainee receives false negative feedback, undermining the training tool's credibility. The `TestStageQuizAllStates` tests verify this contract across all 8 FSM state combinations (5 consultative + 3 transactional).

### Why NOT TDD for LLM-Based Quizzes

TDD requires known expected outputs. For the next-move and direction quizzes:

1. **No single correct answer** — "What would you say next?" has multiple valid responses; no test can assert one expected score
2. **Non-deterministic** — The same answer may score 72 on one LLM call and 78 on the next, even at `temperature=0.3`
3. **Mocking tests the mock** — Mocking the LLM response would verify JSON parsing, not evaluation quality; the parsing is trivial, the evaluation quality is what matters

**Alternative chosen: feature-first with runtime validation.** Instead of testing LLM output at build time, the code validates it at runtime: scores are clamped to 0–100 via `_clamp_score()`, enum fields are checked against allowed values (`_ALIGNMENT_VALUES`, `_UNDERSTANDING_VALUES`), and any parse or API failure returns a neutral fallback. This is defensive design — appropriate when outputs are empirical rather than deterministic. The validation helpers themselves are deterministic, so they have their own TDD-style unit tests (6 tests in `TestScoreClamping` and `TestEnumValidation`).

### Development Phases

```
PHASE 1 — TDD (Stage Quiz)
├─ Write 20 tests defining all acceptance criteria
├─ Implement evaluate_stage_quiz() to satisfy tests
└─ Confidence: deterministic logic verified; 100% path coverage

PHASE 2 — Feature-First (LLM Quizzes)
├─ Implement evaluate_next_move_quiz() + evaluate_direction_quiz()
├─ Add runtime validation (score clamping, enum checking)
├─ Add try/except fallbacks for LLM failure
├─ Add 6 unit tests for validation helpers
└─ Confidence: LLM output sanitised before reaching frontend; safe degradation on failure
```

---

## 3. Implementation Structure

### Files Created

| File | LOC | Purpose | Methodology |
|------|-----|---------|-------------|
| `src/chatbot/quiz.py` | 372 | Core evaluation + validation | TDD (stage) / Feature-first (LLM) |
| `src/config/quiz_config.yaml` | 106 | Stage rubrics & questions | Data-driven |
| `tests/test_quiz.py` | 296 | 26 unit tests | TDD |
| `src/web/app.py` (additions) | ~80 | 4 new API endpoints | Feature-first |
| `src/web/templates/index.html` (additions) | ~180 | Quiz panel UI | Component-based |
| `src/web/static/chat.css` (additions) | ~150 | Quiz panel styling | CSS |

**Total: ~888 lines of production code + 296 lines of tests**

---

## 4. TDD Phase: Stage Quiz

### Test Classes & Coverage

**TestStageQuizEvaluation (10 tests)**
Tests the core evaluation logic in isolation.

```python
# Example: test_exact_match_correct
def test_exact_match_correct(self):
    bot = MockBot(stage="logical", strategy="consultative")
    result = evaluate_stage_quiz("logical consultative", bot)
    assert result["correct"] is True
    assert result["score"] == 1
```

| Test | Scenario | Assertion |
|------|----------|-----------|
| `test_exact_match_correct` | Answer: "logical consultative" | `correct==True, score==1` |
| `test_case_insensitive` | Answer: "LOGICAL CONSULTATIVE" | Case doesn't matter |
| `test_natural_language_accepted` | Answer: "We're in the emotional stage..." | Keywords enough |
| `test_stage_only_is_partial` | Answer: "pitch" (no strategy) | Partial is incorrect |
| `test_wrong_stage_incorrect` | Wrong stage, right strategy | Still incorrect |
| `test_wrong_strategy_incorrect` | Right stage, wrong strategy | Still incorrect |
| `test_expected_values_returned` | Any wrong answer | Expected values always present |
| `test_feedback_on_correct` | Correct answer | Feedback includes stage name |
| `test_feedback_on_incorrect` | Wrong answer | Feedback reveals correct answer |
| `test_user_answer_preserved` | Any answer | Original text preserved in result |

**TestStageQuizAllStates (3 tests)**
Tests that the quiz works across all FSM state combinations.

```python
def test_consultative_all_stages(self):
    stages = ["intent", "logical", "emotional", "pitch", "objection"]
    for stage in stages:
        bot = MockBot(stage=stage, strategy="consultative")
        result = evaluate_stage_quiz(f"{stage} consultative", bot)
        assert result["correct"] is True, f"Failed for {stage}"
```

**TestStageRubricLoading (3 tests)**
Tests that stage configuration loads correctly.

```python
def test_load_consultative_logical_rubric(self):
    rubric = get_stage_rubric("logical", "consultative")
    assert "goal" in rubric
    assert "advance_when" in rubric
    assert isinstance(rubric["key_concepts"], list)
```

**TestQuizQuestionGeneration (4 tests)**
Tests that questions are loaded and fallbacks work.

```python
def test_get_stage_question(self):
    question = get_quiz_question("stage")
    assert isinstance(question, str)
    assert len(question) > 10
    assert "?" in question
```

### Test Execution Results

```
============================= test session starts =============================
collected 26 items

tests/test_quiz.py::TestStageQuizEvaluation::test_exact_match_correct PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_case_insensitive PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_natural_language_accepted PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_stage_only_is_partial PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_wrong_stage_incorrect PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_wrong_strategy_incorrect PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_expected_values_returned PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_feedback_on_correct PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_feedback_on_incorrect PASSED
tests/test_quiz.py::TestStageQuizEvaluation::test_user_answer_preserved PASSED
tests/test_quiz.py::TestQuizQuestionGeneration::test_get_stage_question PASSED
tests/test_quiz.py::TestQuizQuestionGeneration::test_get_next_move_question PASSED
tests/test_quiz.py::TestQuizQuestionGeneration::test_get_direction_question PASSED
tests/test_quiz.py::TestQuizQuestionGeneration::test_invalid_type_returns_fallback PASSED
tests/test_quiz.py::TestStageQuizAllStates::test_consultative_all_stages PASSED
tests/test_quiz.py::TestStageQuizAllStates::test_transactional_all_stages PASSED
tests/test_quiz.py::TestStageQuizAllStates::test_intent_discovery_mode PASSED
tests/test_quiz.py::TestStageRubricLoading::test_load_consultative_logical_rubric PASSED
tests/test_quiz.py::TestStageRubricLoading::test_load_transactional_pitch_rubric PASSED
tests/test_quiz.py::TestStageRubricLoading::test_fallback_for_unknown_stage PASSED
tests/test_quiz.py::TestScoreClamping::test_valid_score_unchanged PASSED
tests/test_quiz.py::TestScoreClamping::test_negative_score_clamped_to_zero PASSED
tests/test_quiz.py::TestScoreClamping::test_over_hundred_clamped PASSED
tests/test_quiz.py::TestScoreClamping::test_non_numeric_returns_default PASSED
tests/test_quiz.py::TestEnumValidation::test_valid_alignment_values PASSED
tests/test_quiz.py::TestEnumValidation::test_valid_understanding_values PASSED

============================= 26 passed in 0.71s ==============================
```

**Coverage:** 100% of deterministic code paths exercised (stage quiz + validation helpers).
**Confidence Level:** High — all deterministic logic verified; LLM paths have runtime validation + fallbacks.

---

## 5. Feature-First Phase: LLM-Based Quizzes

### Design Rationale

Two quiz types require LLM evaluation:

**Type 2: Next Move Quiz**
- **Question:** "What would you say next?"
- **Evaluation Logic:** Compare user's response against stage goals using LLM as judge
- **Why LLM?** No closed answer set; context-dependent quality (e.g., "What would you say" in pitch stage requires understanding of assumptive close, without arguing)
- **Success Criteria:** Feedback is sensible; score correlates with objective quality

**Type 3: Direction Quiz**
- **Question:** "Where are you taking this conversation?"
- **Evaluation Logic:** LLM assesses whether trainee understands stage goal, advancement triggers, and strategy
- **Why LLM?** Open-ended conceptual understanding; cannot be regex-matched

### Implementation Pattern

```python
def evaluate_next_move_quiz(user_response, bot, last_user_message=""):
    stage = bot.flow_engine.current_stage
    strategy = bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)

    eval_prompt = f"""You are evaluating a sales trainee's proposed response.
    CONTEXT: Stage: {stage}, Goal: {rubric['goal']}
    TRAINEE'S RESPONSE: "{user_response}"
    Return JSON: {{"score": <0-100>, "alignment": "<strong|partial|weak>", ...}}"""

    try:
        response = bot.provider.chat(messages, temperature=0.3, max_tokens=300)
        content = response.content
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            result = json.loads(json_match.group())
            alignment = result.get("alignment")
            return {
                "score": _clamp_score(result.get("score", 50)),        # Clamped 0-100
                "alignment": alignment if alignment in _ALIGNMENT_VALUES else "partial",
                ...
            }
    except Exception:
        pass  # Fall through to fallback

    return {"score": 50, "alignment": "partial", "feedback": "Could not evaluate.", ...}
```

### Why This Pattern Works

1. **Structured Output** — Requesting JSON forces LLM to format response predictably
2. **Low Temperature** — `temperature=0.3` reduces variability while allowing semantic understanding
3. **Runtime Validation** — `_clamp_score()` prevents out-of-range scores; enum sets prevent invalid categories
4. **Fallback Mechanism** — If JSON parsing fails or LLM times out, returns neutral feedback instead of crashing

---

## 6. Configuration-Driven Design

### `quiz_config.yaml` Structure

**Stage Rubrics** — What each stage is trying to accomplish

```yaml
stages:
  consultative:
    logical:
      goal: "Guide prospect to articulate their own problem with current approach"
      advance_when: "User names a clear problem and expresses doubt"
      key_concepts:
        - "Two-phase probe (cause then like/dislike)"
        - "Never state problem for them"
        - "Create doubt in current approach"
```

**Quiz Questions** — Variety of questions per type

```yaml
questions:
  stage:
    - "What stage of the sales process are we in right now?"
    - "Which stage and strategy are we using?"
  next_move:
    - "What would you say next to this customer?"
    - "How would you respond to their last message?"
  direction:
    - "Where are you taking this conversation and why?"
    - "What's your strategy for the next few turns?"
```

**Why Configuration?**

1. **No Code Changes** — Quiz questions and rubrics can be updated without redeploying
2. **Theory-to-Practice Link** — Rubrics can reference exact NEPQ stage definitions without cluttering Python code
3. **Easy to Extend** — Adding a new quiz type or stage requires only YAML, not code refactoring

---

## 7. API Integration

### New Endpoints (4 total)

**GET `/api/quiz/question?type={stage|next_move|direction}`**
- Load a random question for the quiz type
- Response: `{"success": true, "question": "...", "type": "..."}`

**POST `/api/quiz/stage`**
- Evaluate stage identification quiz
- Request body: `{"answer": "logical consultative"}`
- Response: `{"correct": true, "score": 1, "expected": {...}, "feedback": "..."}`

**POST `/api/quiz/next-move`**
- Evaluate proposed response using LLM
- Request body: `{"response": "What have you tried before?"}`
- Response: `{"score": 75, "alignment": "strong", "feedback": "...", "strengths": [...], "improvements": [...]}`

**POST `/api/quiz/direction`**
- Evaluate strategic understanding using LLM
- Request body: `{"explanation": "I'm trying to surface their emotional stakes..."}`
- Response: `{"score": 82, "understanding": "good", "key_concepts_got": [...], "key_concepts_missed": [...]}`

### Security & Validation

All endpoints inherit security from existing app.py patterns:

1. **Session validation** — `require_session()` returns 400 if session missing
2. **Input length limits** — Validate `len(answer) <= SecurityConfig.MAX_MESSAGE_LENGTH`
3. **Rate limiting** — Could add `@require_rate_limit('quiz')` if needed (currently inherits general chat limit)
4. **Error handling** — 500 returns only if unhandled exception; otherwise structured error JSON

---

## 8. Frontend Integration

### Quiz Panel UI

Three-button interface matching existing Training panel pattern:

```html
<div id="quizPanel">
  <div class="quiz-header">📝 Quiz Mode | ×</div>
  <div class="quiz-body">
    <!-- Type selector -->
    <div class="quiz-type-buttons">
      <button class="quiz-type-btn active" onclick="selectQuizType('stage')">Stage</button>
      <button class="quiz-type-btn" onclick="selectQuizType('next_move')">Next Move</button>
      <button class="quiz-type-btn" onclick="selectQuizType('direction')">Direction</button>
    </div>

    <!-- Question display -->
    <div class="quiz-question" id="quizQuestion">...</div>

    <!-- Answer input + submit -->
    <textarea id="quizAnswer" class="quiz-answer-input"></textarea>
    <button class="quiz-submit-btn" onclick="submitQuiz()">Submit Answer</button>

    <!-- Feedback display -->
    <div id="quizFeedback"></div>
  </div>
</div>
```

**Key Functions**

```javascript
toggleQuizPanel()     // Open/close quiz panel
selectQuizType(type)  // Switch between stage/next_move/direction
fetchQuizQuestion()   // Load new question from /api/quiz/question
submitQuiz()          // POST answer to appropriate endpoint
displayQuizFeedback() // Render score, feedback, details
```

**Color Theming:** Purple/indigo (#6366f1) to differentiate from amber Training panel.

---

## 9. Quality Assurance

### What Was Tested

| Layer | Test Type | Scope | Result |
|-------|-----------|-------|--------|
| **Unit** | Automated (TDD) | 20 tests: stage evaluation, config loading, question generation | ✅ 20/20 pass |
| **Validation** | Automated | 6 tests: score clamping, enum validation | ✅ 6/6 pass |
| **Integration** | Manual + API | Stage quiz endpoint with mock bot | ✅ Returns correct score |
| **System** | Manual spot-check | Full workflow: open quiz panel → select type → answer → see feedback | ✅ Works end-to-end |
| **Error Path** | Manual | LLM timeout → fallback score + "try again" message | ✅ No crash |

### Known Limitations

1. **LLM Evaluation Quality** — Score accuracy depends on LLM temperature and prompt clarity. Not formally validated against human raters (would require UAT).
2. **Non-Deterministic** — Running same answer through direction quiz twice may yield slightly different scores. This is acceptable for training feedback but not for certification.
3. **No Persistence** — Quiz answers not saved to database; useful for in-session practice only.

---

## 10. Effort Estimation & Actuals

### Estimation Method: Analogical (comparing to similar features)

| Phase | Estimated | Actual | Variance | Notes |
|-------|-----------|--------|----------|-------|
| TDD + stage quiz | 4h | 3.5h | −0.5h | Tests written first sped up implementation |
| LLM quiz skeletons | 3h | 2h | −1h | Reused pattern from trainer.py for prompt building |
| Config file setup | 1h | 0.5h | −0.5h | Rubrics straightforward; no iteration needed |
| API endpoint wiring | 2h | 1.5h | −0.5h | Followed app.py patterns exactly |
| UI/CSS + JS | 3h | 2.5h | −0.5h | Copied dev panel + training panel patterns |
| Testing + debugging | 2h | 1.5h | −0.5h | Few surprises; all imports worked |
| **Total** | **15h** | **11h** | **−4h (26% under)** | Low complexity; well-defined patterns |

### Why Did the Estimate Overestimate? (Positive Variance)

1. **Prior Art** — App already had secure session handling, rate limiting, error response patterns
2. **TDD Clarity** — Writing tests first meant implementation had no "surprises"; fewer debug cycles
3. **No LLM Uncertainty** — Unlike prompt engineering, LLM-as-evaluator doesn't require iterative tuning (fallback is sensible enough)

---

## 11. Design Decisions & Trade-Offs

### Decision 1: Why Not Auto-Save Quiz Attempts?

**Trade-off:** Persistence vs. Scope
- **Not Implemented:** Saving quiz answers to database + analytics dashboard
- **Reason:** Out of scope for current project. Training goal is immediate feedback, not historical tracking.
- **Future Extension:** Could add `quiz_attempts` table to track progression

### Decision 2: Why Not LLM for Stage Quiz?

**Trade-off:** Flexibility vs. Correctness
- **Not Implemented:** Using LLM to evaluate "is this answer correct?"
- **Reason:** Binary correctness doesn't need LLM; wastes tokens and introduces variance. Exact match of `current_stage` and `flow_type` is deterministic and fast.

### Decision 3: Why JSON Parsing from LLM Output?

**Trade-off:** Reliability vs. Simplicity
- **Not Implemented:** Free-form text feedback from LLM
- **Reason:** JSON structure guarantees parseable fields (`score`, `alignment`, `feedback`). If LLM format drifts, can fallback cleanly.

---

## 12. How This Addresses the Supervisor's Feedback

| Supervisor Concern | Quiz Feature Response | Implementation |
|---|---|---|
| "Can't verify trainees understand the concepts" | Stage quiz forces explicit naming of stage + strategy | `evaluate_stage_quiz()` requires both to score correct |
| "No signal that trainee internalised methodology" | Direction quiz asks trainee to explain their reasoning | LLM evaluates whether response references stage goal + advancement triggers |
| "Replayable conversations don't test live response quality" | Next Move quiz evaluates proposed response in real-time | User proposes response *before* seeing bot's answer |
| "No differentiation between memorizers and learners" | Multiple quiz types test different cognitive levels | Stage quiz (recall) → Next Move (application) → Direction (analysis) |

---

## 13. Code Quality & Maintainability

### Code Structure

```
src/chatbot/quiz.py
├─ _clamp_score()               # Clamp LLM score to 0-100
├─ _load_quiz_config()          # Cached YAML loading
├─ get_stage_rubric()           # Public: fetch stage metadata
├─ get_quiz_question()          # Public: random question retrieval
├─ evaluate_stage_quiz()        # Public: deterministic evaluation
├─ evaluate_next_move_quiz()    # Public: LLM-based evaluation + validation
├─ evaluate_direction_quiz()    # Public: LLM-based evaluation + validation
└─ _generate_stage_feedback()   # Private: feedback text for stage quiz
```

**Principles Applied:**

1. **Single Responsibility** — Each function does one thing (evaluate one quiz type)
2. **Testability** — Pure functions where possible; mocks for FSM dependencies
3. **Error Recovery** — LLM functions never raise; graceful fallback on failure
4. **Runtime Validation** — LLM outputs sanitised before returning to caller
5. **Configuration-Driven** — No hardcoded questions or rubrics

### Code Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Cyclomatic Complexity (quiz.py) | Low (avg ~2) | Simple decision trees, few nested conditions |
| Test Coverage | 100% (deterministic code + validation) | 26 tests; LLM evaluation quality not formally tested |
| Docstring Coverage | 100% | Every public function has docstring |
| Type Hints | Partial | Arguments typed; LLM output uses `Any` (JSON varies) |
| LOC per Function | ~40 avg | Readable; no function >50 LOC |

---

## 14. Conclusion: Why This Approach

**TDD for Stage Quiz** — the matching logic has non-obvious edge cases (case sensitivity, partial answers, natural language wrapping). Test-first forced these to be explicit design decisions before implementation, eliminating the discover-and-patch cycle.

**Feature-First for LLM Quizzes** — subjective evaluation has no single correct output, so build-time tests cannot verify evaluation quality. Runtime validation (score clamping, enum checking, fallback on failure) is the appropriate safeguard for empirical systems.

**The split is structural, not arbitrary:** deterministic logic gets TDD because the acceptance criteria are fully specifiable in advance; empirical logic gets feature-first with runtime validation because the outputs are not.

**Verification:** All design decisions implemented in `src/chatbot/quiz.py`, `src/config/quiz_config.yaml`, and `tests/test_quiz.py` — reviewable and auditable.
