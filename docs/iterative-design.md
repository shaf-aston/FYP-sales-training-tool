# Iterative Design Documentation: Module Timeline & Strategy Evolution

**Document Purpose**: Chronological development record organized by module implementation phases and high-level strategy shifts. Shows how technical requirements emerged through prototyping, supervisor feedback, and iterative refinement from Sept 2025 (Qwen 2.5 LLM failure) through Jan 2026 (rule-based KALAP V2 architecture).

---

**Project**: KALAP V2 Sales Training Chatbot  
**Student**: [Your Name]  
**Supervisor**: Sylvia  
**Date Range**: September 2025 - January 2026 (Ongoing)  
**Status**: Active Development

---

## Development Timeline: Strategy Pivot

| Timeline | Strategic Focus | Architecture | Modules | Status |
|----------|-----------------|--------------|---------|--------|
| **Sept-Early Oct** | Problem Investigation | Qwen 2.5 + SQLite DB | None (design phase) | Failed |
| **Mid Oct** | Pivot Decision | Rule-based system | Conceptual (5-6 identified) | Decision Point |
| **Late Oct-Nov** | Core Engine Build | State Machine + Config | 6 modules (incremental) | Partial |
| **Dec** | Integration & Testing | Full KALAP V2 + Frontend | All 6 complete + tests | Functional |
| **Jan 2026** | Polish & Role Toggle | Dual-mode + Bug Fixes | Complete (1,179 lines) | Production-Ready |

---

## 1. Phase 1: Early Stage - LLM Investigation & Failure (Sept-Early Oct 2025)

### 1.1 Initial Concept (Pre-Implementation)

**Problem**: Create a sales training roleplay chatbot.

**Initial Assumptions** (Incorrect):
- Needed LLM for "intelligent" conversation
- Required database to store training examples
- Needed fine-tuning for sales-specific responses

**Supervisor Meeting #1 (29 Sept 2025)**:
Sylvia asked:
- "What is the end-product vision?"
- "What are base functional requirements?"
- "How do you showcase developer skills vs AI generation?"

**Action Taken**: Dove headfirst into implementation without clear requirements.

### 1.2 First Implementation Attempt: Qwen 2.5 + Database

**Architecture**:
```
User Input → Database (training examples) → Qwen 2.5-0.5B → Fine-tuned responses
```

**Technology Stack**:
- Qwen 2.5-0.5B (local LLM)
- PyTorch for fine-tuning
- SQLite database for conversation training data
- Flask backend

**Rationale at the Time**: "LLMs are good at conversation, so fine-tune one for sales."

### 1.3 Technical Failure: The Hashtag Problem

**What Happened**:
- Model started outputting hashtags (`#sales #closing #prospect`)
- Random syntax appeared: `**bold text**`, `## headers`, bullet points
- Responses became inconsistent and unprofessional
- 30% of outputs contained markdown formatting

**Example Failure**:
```
User: "What's your budget?"
Qwen 2.5: "Well #budget is important. Here are **3 key points**:
- Consider your ROI
- Look at ## Monthly Costs
Let's discuss #pricing strategies"
```

**WHY This Happened** (Technical Root Cause):
1. **Training Data Contamination**: Fine-tuning dataset likely contained markdown-formatted documents (README files, technical docs, Stack Overflow posts)
2. **Tokenizer Mismatch**: Qwen 2.5's tokenizer wasn't filtering markdown syntax tokens during training
3. **No Output Validation**: No post-processing to strip formatting tokens
4. **Over-fitting**: Small model (0.5B parameters) memorized training artifacts instead of learning patterns
5. **Context Window Pollution**: Previous turns containing hashtags reinforced the behavior in subsequent responses

**Database Issues**:
- Database was sound (no corruption)
- Data schema worked correctly
- Problem was in the model's output layer, not data storage

**Technical Root Cause Analysis**:

The hashtag and markdown contamination was NOT a database or data retrieval problem. It was a model-layer failure occurring in three stages:

1. **Training Data Contamination** (Pre-Model): Fine-tuning dataset inadvertently included markdown-formatted text. The 0.5B parameter model could not distinguish between markdown syntax and sales language.

2. **Tokenizer Failure** (Encoding Stage): Qwen 2.5's tokenizer did not filter markdown tokens (`#`, `**`) during fine-tuning. Unlike production LLMs with sanitisation layers, tokens passed directly to embedding.

3. **Overfitting & Memorisation** (Generation Stage): With only ~500 fine-tuning examples, the small model memorised training artifacts rather than learning generalised patterns. No output validation removed formatting tokens before returning results.

**Distinction**: The database design was sound—retrieval, indexing, and schema correct. The failure was purely in the model's ability to generate clean text, not in data storage.

**Time Invested**: 3 weeks debugging (adjusting schema, retraining, tuning hyperparameters—all ineffective), zero usable output.

### 1.4 Supervisor Feedback (Meeting #2, 7 Oct 2025)

**Sylvia's Review**:
- "Too many buzz terms - call things what they are"
- "Training and Dialogue conversation are two separate parts"
- "Requirements are too heavy and need to be cut down"

**Reality Check**: I was over-engineering with LLM when requirements were unclear.

---

## 2. Pivot Period: Requirements Clarity (Oct-Nov 2025)

### 2.1 The Realization

**Question**: Do I actually need an LLM for this?

**Analysis**:
| Requirement | LLM Needed? | Why/Why Not |
|-------------|-------------|-------------|
| Follow IMPACT formula phases | No | Deterministic state machine |
| Ask specific questions | No | Template-based |
| Validate user answers | No | Keyword + length scoring |
| Provide feedback | No | Rule-based criteria |

**Conclusion**: LLM was solving a problem that didn't exist.

### 2.2 Supervisor Meeting #3 (20 Oct 2025)

**Sylvia's Guidance**:
- "Provide analytical reviews for technology decisions"
- "Implementation specificity - inputs vs outputs"
- "Try implementing code to see functionality"

**Action**: Started prototyping rule-based approach.

### 2.3 Technical Pivot Decision

**Old Approach**:
```python
# Qwen 2.5 approach (failed)
response = model.generate(user_input, training_examples)  # Unpredictable
```

**New Approach**:
```python
# Rule-based approach (adopted)
if current_phase == "intent":
    if missing_captures("tangible_outcome"):
        return get_question("tangible_outcome")
```

**Why This Works**:
- Deterministic: Same input = same output
- Testable: Can write unit tests
- Fast: <100ms vs 2-3s
- Controllable: No random hashtags

---

## 3. Implementation Phase: Building KALAP V2 (Nov-Dec 2025)

### 3.1 Module-First Development

**Approach**: Build focused modules, test each independently.

**Created**:
1. `phase_manager.py` - State machine for phase transitions
2. `context_tracker.py` - In-memory session storage
3. `question_router.py` - Question selection logic
4. `answer_validator.py` - Response scoring
5. `fuzzy_matcher.py` - Keyword matching with typo tolerance
6. `response_generator.py` - Orchestrator

**Each module**: Single file, single responsibility, 70-300 lines.

### 3.2 Supervisor Meeting #4 (11 Nov 2025)

**Topics**:
- Ethics form completion
- PyTorch discussion (still thinking ML)

**Reality**: Still hadn't fully committed to rule-based approach mentally.

### 3.3 The Fuzzy-Matching Breakthrough

**Supervisor Meeting #6 (24 Nov 2025)**:
Sylvia suggested:
- "Creating a fuzzy-matching system linking to cues"
- "Making a dialogue flow"
- "Use pre-made functionalities/libraries"

**Implementation**:
```python
from rapidfuzz import fuzz

def match_intent(user_input, keywords):
    for kw in keywords:
        if fuzz.partial_ratio(kw.lower(), input_lower) > 70:
            return True
```

**Why This Works**:
- Handles typos ("buget" → "budget")
- No training required
- Library does heavy lifting (minimalism principle)

### 3.4 Configuration Over Code

**Problem**: Hardcoded questions in Python strings.

**Solution**: Moved to JSON config files.

**Before**:
```python
INTENT_QUESTION = "What do you need help with?"  # Hardcoded
```

**After**:
```json
{
  "intent": {
    "tangible_probe": "What specifically do you need help with?"
  }
}
```

**Benefit**: Change questions without touching Python code.

---

## 4. Testing and Refactoring (Dec 2025)

### 4.1 Test-Driven Validation

**Started**: 0 tests  
**After pytest setup**: 113 tests

**Test Categories**:
- Unit tests: Each module independently
- Integration tests: Multi-module flows
- API tests: HTTP endpoints
- Formula tests: IMPACT methodology compliance

### 4.2 Code Reduction Through Refactoring

**Redundancy Found**:
1. `answer_validator.py`: `validate()` and `calculate_completion_score()` both scored text identically
2. `fuzzy_matcher.py`: 4 unused methods that duplicated rapidfuzz functionality
3. `response_generator.py`: Duplicate orchestration in salesrep/prospect modes

**Actions**:
- Created shared `_score_text()` method
- Removed custom fuzzy matching (used rapidfuzz instead)
- Extracted `_build_metadata()` and `_try_advance_phase()` helpers

**Result**: -322 lines (-27%) with identical functionality.

### 4.3 Bug Discovery Through Code Review

**High-Priority Bug**:
```python
# BEFORE (bug)
bot_message = f"{transition} {formatted_q}"  # transition could be None

# AFTER (fixed)
bot_message = f"{transition} {formatted_q}".strip() if transition else formatted_q
```

**Why This Matters**: Concatenating `None` produces "None What's your goal?" - unprofessional output.

---

## 5. Current State (January 2026)

### Libraries (Current Design)

- rapidfuzz — fuzzy string matching (intent detection, typo tolerance)
- textblob — sentiment analysis (emotional scoring)
- jinja2 — templating (dynamic question rendering)
- fastapi — backend API framework
- uvicorn — ASGI server for running FastAPI
- pydantic — request/response data validation
- pytest, pytest-asyncio, pytest-cov — testing framework and plugins

### 5.1 What Works

**Core Engine**:
- 6 modules, 1,179 lines total
- 113 passing tests
- <100ms response time
- Deterministic conversation flow

**Frontend**:
- React chat UI
- Role toggle (Salesrep/Prospect modes)
- Voice integration via Web Speech API

**Backend**:
- FastAPI with 3 endpoints
- Debug endpoint for curl testing

### 5.2 What's Still Needed

**Incomplete Features**:
1. Voice recording persistence
2. Progress analytics dashboard
3. Multiple scenario support
4. Admin panel for adding questions

**Known Issues**:
- TextBlob import sometimes fails on Windows (non-critical)
- Session data lost on server restart (by design - in-memory)

---

## 6. Lessons Learned (Technical)

### 6.1 LLM Failure Analysis

**What I Learned**:
- Fine-tuning small models (0.5B params) on contaminated data = disaster
- No output validation = unpredictable results
- Training data quality > model size
- Debugging LLM outputs is near-impossible (black box)

### 6.2 Rule-Based Success Factors

**Why It Worked**:
- Requirements were deterministic (IMPACT formula has fixed phases)
- Testability: Can verify every code path
- Speed: No GPU inference overhead
- Controllability: Explicit logic = explicit debugging

### 6.3 Supervisor Guidance Impact

**Sylvia's Most Valuable Advice**:
1. "Call things what they are" → Stopped using buzz terms
2. "Use pre-made libraries" → Adopted rapidfuzz, textblob, jinja2
3. "Fuzzy-matching system" → Core of current architecture
4. "Line-by-line analysis" → Found the transition=None bug

---

## 7. Metrics: Before vs After

| Metric | Sept 2025 (Qwen 2.5) | Jan 2026 (KALAP V2) | Change |
|--------|----------------------|---------------------|--------|
| Response Time | 2-3 seconds | <100ms | 30x faster |
| Output Quality | 30% corrupted (hashtags) | 100% clean | Fixed |
| Test Coverage | 0 tests | 113 tests | +113 |
| Dependencies | 15+ (ML stack) | 3 (utilities) | -80% |
| Code Lines | ~3000 (estimated) | 1,179 | -61% |
| Bugs Found | Unknown (untestable) | 6 (all fixed) | Transparent |

---

### 9.1 PhaseManager (State Machine Core)

**Implementation Window**: Nov 1-10, 2025 (10 days)

**Purpose**: Encapsulate the Smash Formula's 6-phase structure and enforce state transitions.

**Key Code**:
```python
class PhaseManager:
    PHASES = ["intent", "logical_certainty", "emotional_certainty", 
              "future_pace", "consequences", "pitch"]
    
    def can_advance(self, current_phase, captures):
        # Enforce gate conditions
        if current_phase == "intent":
            return all(k in captures for k in ["tangible_outcome", "pain"])
```

**Why First**: Conversation structure is foundational—all other modules depend on knowing which phase the user is in.

**Supervisor Alignment**: Meeting #3 (20 Oct) feedback: "Implementation specificity - inputs vs outputs" guided explicit state gates.

### 9.2 ContextTracker (Session Memory)

**Implementation Window**: Nov 2-12, 2025 (parallel with PhaseManager)

**Purpose**: Maintain conversation state (current phase, captures, conversation history).

**Key Code**:
```python
class ContextTracker:
    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.current_phase = "intent"
        self.captures = {}  # User-provided information
        self.messages = []  # Conversation history
```

**Why Early**: Required by PhaseManager for state queries; needed before question routing.

**Design Choice**: In-memory storage (not database) for sprint velocity—persistence can be added in Term 2.

### 9.3 QuestionRouter (Template Selection)

**Implementation Window**: Nov 13-23, 2025 (10 days)

**Purpose**: Select appropriate follow-up questions based on phase and captured information.

**Key Code**:
```python
def get_next_question(phase, captures, recent_objections):
    # Route to specific question based on context
    if phase == "intent" and "pain" not in captures:
        return templates["intent"]["probe_pain"]
```

**Critical Feature**: Jinja2 templating enables dynamic variable injection.

**Example Output**:
```python
template = "You mentioned {{pain}}. How does that impact {{business_area}}?"
# Rendered: "You mentioned high churn. How does that impact customer retention?"
```

**Supervisor Alignment**: Meeting #6 (24 Nov): "Creating a fuzzy-matching system linking to cues" informed the template architecture.

### 9.4 AnswerValidator (Response Scoring)

**Implementation Window**: Dec 1-8, 2025 (8 days)

**Purpose**: Score user responses against multiple criteria (relevance, specificity, information capture).

**Key Code**:
```python
class AnswerValidator:
    def validate(self, user_input, phase):
        score = 0
        if self._is_relevant(user_input, phase): score += 0.3
        if self._is_specific(user_input): score += 0.4
        if self._extracts_captures(user_input, phase): score += 0.3
        return score
```

**Design Rationale**: Multi-criteria avoids brittleness of simple keyword matching.

**Refactoring (Dec 15)**: Removed duplicate `calculate_completion_score()` method; consolidated into single `_score_text()` helper.

### 9.5 FuzzyMatcher (Intent Detection)

**Implementation Window**: Dec 8-15, 2025 (7 days)

**Purpose**: Match user input to conversation intents despite typos and paraphrasing.

**Key Code**:
```python
from rapidfuzz import fuzz

def match_intent(user_input, intent_keywords):
    for keyword in intent_keywords:
        if fuzz.partial_ratio(keyword.lower(), user_input.lower()) > 70:
            return True
    return False
```

**Why Adopted**: Supervisor Meeting #6 explicitly suggested "Use pre-made functionalities/libraries."

**Example Handling**:
- Input: "I need to figure out my goal budget situation" 
- Matches: "budget" (86% partial ratio) → captures "budget_focus"

**Removed Code**: Initial implementation had 4 custom fuzzy matching methods—all removed in refactor, replaced by rapidfuzz (DRY principle).

### 9.6 ResponseGenerator (Orchestrator)

**Implementation Window**: Dec 16-25, 2025 (10 days)

**Purpose**: Coordinate all 5 modules to produce contextually appropriate responses.

**Key Code**:
```python
def generate_response(user_message, context):
    # Orchestration flow
    intent = fuzzy_matcher.match_intent(user_message)
    is_valid = answer_validator.validate(user_message, context.phase)
    can_advance = phase_manager.can_advance(context.phase, context.captures)
    
    if can_advance:
        context.current_phase = phase_manager.advance(context.phase)
    
    next_question = question_router.get_next_question(context.phase, context.captures)
    return {
        "bot_message": f"{transition_signal} {next_question}",
        "phase": context.current_phase,
        "score": is_valid
    }
```

**Critical Bug (Fixed Jan 8)**:
```python
# BEFORE: transition could be None
bot_message = f"{transition} {formatted_q}"  # → "None What's your goal?"

# AFTER: strip() handles None gracefully
bot_message = f"{transition} {formatted_q}".strip() if transition else formatted_q
```

**Supervisor Alignment**: Meeting #6 "Line-by-line analysis" informed rigorous code review process that caught this bug.

---

## 10. Frontend Development: CorePage React Component

**Implementation Window**: Dec 10-20, 2025 (10 days, parallel with backend testing)

**Purpose**: Dual-mode chat interface supporting Salesrep and Prospect practice modes.

**Key Features**:
```javascript
const [role, setRole] = useState("salesrep");  // Toggle between modes

const handleRoleToggle = () => {
    const newRole = role === "salesrep" ? "prospect" : "salesrep";
    setRole(newRole);
    setMessages([]);  // Reset session on role switch
    setConversationId(null);
};
```

**Architecture Decision**: Role stored in component state, not backend, enabling seamless UI switching.

---

## 11. Testing & Code Quality (Dec 20-Jan 15)

### 11.1 Test-Driven Refactoring

**Initial State (Dec 10)**: ~2,000 lines, 0 tests

**Test Framework**: pytest (113 tests by Jan 15)

**Test Categories**:

| Category | Count | Focus |
|----------|-------|-------|
| Unit (PhaseManager, ContextTracker, etc.) | 58 | Module logic independently |
| Integration (multi-module flows) | 27 | Module interaction |
| API (HTTP endpoints) | 14 | Backend endpoints |
| Smash Formula compliance | 22 | Methodology verification |
| End-to-end scenarios | 4 | Full conversation flow |

**Code Reduction Results**:

| Area | Before | After | Removed | Reason |
|------|--------|-------|---------|--------|
| AnswerValidator duplication | 2 scoring methods | 1 method | ~40 lines | Consolidate identical logic |
| FuzzyMatcher unused methods | 4 custom methods | 0 (use rapidfuzz) | ~60 lines | Adopt library solution |
| ResponseGenerator modes | Duplicate salesrep/prospect | Shared helpers | ~150 lines | Extract common orchestration |
| Hardcoded values | 8+ scattered | 0 (moved to constants.js) | ~70 lines | Centralize configuration |
| **Total** | - | - | **322 lines (-27%)** | DRY principle |

**Refactoring Driven By**: Test failures exposed duplicated logic; fixing tests revealed opportunity to simplify.

### 11.2 Bug Discovery Through Testing

**High-Priority Bug** (Discovered Dec 28, Fixed Jan 8):
```python
# In response_generator.py:_build_metadata()
transition = objection_signals.get(intent)  # Could be None
bot_message = f"{transition} {formatted_q}"  # Fails if None
```

**Impact**: Produced "None What's your tangible outcome?" — unprofessional.

**Fix**:
```python
transition = objection_signals.get(intent) or ""
bot_message = f"{transition} {formatted_q}".strip()
```

**Prevention**: Added unit test verifying None handling:
```python
def test_none_transition_handling():
    response = generate_response("vague answer", context)
    assert "None" not in response["bot_message"]
```

---

## 12. Open Questions (Ongoing Development)

**Current Uncertainties**:
1. Should I add voice recording playback?
2. How much analytics is "enough" for FYP?
3. Is the current UI professional enough?
4. Do I need deployment (cloud hosting)?

**Approach**: Implement minimally, validate with supervisor, iterate.

---

## 13. Appendix A: Qwen 2.5 Failure Examples

**Training Data Sample (Suspected Contamination)**:
```markdown
# Sales Techniques

Use these strategies:
- Ask open-ended questions
- Listen actively
- **Close with confidence**

#sales #training #tips
```

**Model Output After Fine-Tuning**:
```
Bot: Great question! Here are **key points**:
- Understand their needs
- Build rapport first
#prospecting #closing
```

**Root Cause**: Model learned markdown syntax as part of "sales language" instead of filtering it.

---

## 14. Appendix B: Configuration Files Structure

```
kalap_v2/config/
├── phase_definitions.json    # Phase names, required captures, gates
├── scoring_rules.json        # Validation thresholds, keywords
└── transition_signals.json   # Keywords triggering phase changes
```

**Example Entry**:
```json
{
  "intent": {
    "required_captures": ["tangible_outcome", "pain_experience"],
    "exit_gate": {
      "minimum_score": 0.2
    }
  }
}
```

---

## References

None yet - this is a working document reflecting ongoing development.

---

---

## Cross-Reference Note

The architectural pivot from LLM to rule-based design is discussed in depth in this document (Sections 1.3-2.3). The formal abstract and Term 1 summary appears in Ai Report T1.md (Abstract section); readers should reference that document for the official problem statement. This document provides the iterative narrative; the report provides the formal assessment.

---

**Last Updated**: January 15, 2026  
**Status**: Active development, features still being added
