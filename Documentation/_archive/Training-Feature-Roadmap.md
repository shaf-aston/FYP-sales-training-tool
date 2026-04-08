# Sales Training Feature Roadmap — Making Reps Actually Better

**Problem**: Current system lets reps practice, but doesn't teach them what they're doing wrong or track if they're improving.

**Goal**: Add features that turn practice into measurable skill development.

---

## 1. Current System Gaps (Training Perspective)

| What's Missing | Why Reps Need It | Training Impact |
|----------------|------------------|-----------------|
| **Performance scoring** | Can't tell if conversation was good or bad | No accountability, no goals |
| **Mistake identification** | Don't know what went wrong | Can't improve without diagnosis |
| **Progress tracking** | No visibility into improvement over time | Demotivating, no learning curve |
| **Actionable feedback** | System says "practice more" but not "fix this" | Generic advice doesn't stick |
| **Technique awareness** | Don't recognize when they're using NEPQ stages | Learning is implicit, not explicit |
| **Replay/retry** | Can't experiment with different approaches | One-shot practice limits exploration |

**Current System**: "Here's a conversation. Good luck figuring out what to improve."

**Needed System**: "You scored 67%. You missed 3 buying signals. Try asking 'why' questions earlier. Here's how a pro would handle turn 8."

---

## 2. Feature Prioritization (Training Impact Matrix)

### High Impact, Low Effort (Ship in Phase 1)

| Feature | Training Benefit | Implementation | Priority |
|---------|------------------|----------------|----------|
| **F1: Post-session scoring** | Clear pass/fail → motivation + goals | Analyze transcript for stage progression, objection handling, signal detection | **P0** |
| **F2: Mistake highlighting** | Shows exactly what went wrong → targeted improvement | Flag turns where: wrong stage, missed signal, poor objection handling | **P0** |
| **F3: Improvement tips** | Actionable advice → faster learning | Template-based suggestions per mistake type | **P0** |
| **F4: Progress dashboard** | Visualizes growth → retention + engagement | Track scores over time (sessions table in DB) | **P1** |

### High Impact, Medium Effort (Ship in Phase 2)

| Feature | Training Benefit | Implementation | Priority |
|---------|------------------|----------------|----------|
| **F5: Real-time technique labels** | Metacognition → conscious skill application | Tag each bot turn with stage/technique (already in FSM) | **P1** |
| **F6: Replay with edits** | Experimentation → deeper understanding | Save session state, allow message edits, recompute from that point | **P2** |
| **F7: Side-by-side comparison** | Learn from experts → pattern recognition | Generate "pro response" for key turning points | **P2** |
| **F8: Quiz before/after** | Assess knowledge gaps → targeted practice | 5-question quiz on NEPQ methodology (pre-test/post-test) | **P2** |

### Medium Impact, High Effort (Ship in Phase 3 / Future Work)

| Feature | Training Benefit | Implementation | Priority |
|---------|------------------|----------------|----------|
| **F9: Voice mode** | Realism → transferable skills | Whisper API (STT) + ElevenLabs (TTS) + latency optimization | **P3** |
| **F10: Adaptive difficulty** | Flow state → optimal challenge | Adjust bot "difficulty" based on performance (e.g., more objections) | **P3** |
| **F11: Certification path** | Extrinsic motivation → completion | Unlock levels, earn badges, final assessment | **P3** |
| **F12: Manager dashboard** | Accountability → team performance | Admin view of team scores, common mistakes, leaderboards | **P3** |

---

## 3. Phase 1 Features (MUST-HAVE for Training)

### F1: Post-Session Scoring (P0)

**What It Is**: After each conversation, show a score (0-100) with breakdown.

**Why Reps Need It**:
- **Motivation**: "Beat your last score" creates engagement
- **Accountability**: Managers can require minimum scores
- **Goal-setting**: "I need 80% to move to next difficulty"

**How It Works** (Scoring Rubric):

| Component | Weight | How It's Calculated |
|-----------|--------|---------------------|
| **Stage progression** | 30% | Did they reach PITCH or OBJECTION? (Yes=30, EMOTIONAL=20, LOGICAL=15, INTENT=5) |
| **Signal detection** | 25% | Did they respond to buying signals? (Count turns where analysis detected signal + bot acted on it) |
| **Objection handling** | 20% | If objection raised, did bot classify correctly + reframe? (Yes=20, Partial=10, No=0) |
| **Questioning depth** | 15% | Did they ask "why" questions? (Count analysis.classify_intent() high-impact questions) |
| **Conversation length** | 10% | Efficient closure? (7-12 turns=10, <7=5 rushed, >12=5 dragging) |
| **TOTAL** | 100% | Sum of all components |

**Example Scorecard**:
```
Session Score: 72/100 (Good)

✅ Stage Progression: 30/30 (Reached OBJECTION stage)
⚠️ Signal Detection: 15/25 (Missed 2 buying signals at turns 4, 9)
✅ Objection Handling: 20/20 (Correctly reframed price objection)
⚠️ Questioning Depth: 9/15 (Asked 3 "why" questions, target is 5+)
✅ Conversation Length: 8/10 (9 turns—efficient)

Next Goal: Improve signal detection to reach 80%
```

**Implementation** (2-3 days):
1. Add `ChatbotTrainer.score_session(transcript, analysis_log)` method
2. Calculate each component using existing `SessionAnalytics` data
3. Return JSON with score + breakdown
4. Display in web UI (new `/api/session/score` endpoint)

**UAT Validation**:
- "Did the score reflect your performance?" (Yes/No)
- "Did the breakdown help you understand what to improve?" (Likert 1-5)

---

### F2: Mistake Highlighting (P0)

**What It Is**: Show specific turns where rep made mistakes, with explanation.

**Why Reps Need It**:
- **Precision**: "You messed up at turn 8" > "You need to improve objection handling"
- **Pattern recognition**: See recurring mistakes across sessions
- **Immediate feedback**: Know exactly where to focus

**How It Works** (Mistake Detection Rules):

| Mistake Type | Detection Logic | Example |
|--------------|-----------------|---------|
| **Missed buying signal** | User shows high intent, but bot stays in same stage | Turn 4: User says "I really need this soon" → Bot didn't advance to PITCH |
| **Premature pitch** | Bot pitches before EMOTIONAL stage (consultative only) | Turn 3: Bot presents package before exploring pain |
| **Ignored objection** | User raises objection, but bot doesn't classify/reframe | Turn 7: User says "too expensive" → Bot continues pitch |
| **Question repetition** | Bot asks same question type 2+ times in a row | Turns 5-6: Both ask about budget in different words |
| **Pitch ends with question** | Bot asks question after presenting solution | Turn 10: "We have this package. Interested?" (weak close) |

**Example Mistake Log**:
```
⚠️ Mistakes Found: 3

Turn 4 - Missed Buying Signal
  User: "I really need to get this sorted by next month"
  Issue: High intent + urgency signal detected, but you stayed in INTENT stage
  Fix: Advance to LOGICAL or ask "What happens if you don't solve this by then?"

Turn 7 - Ignored Objection
  User: "That sounds expensive"
  Issue: Price objection raised, but you continued with features
  Fix: Acknowledge concern, then reframe: "What would reliability be worth to you?"

Turn 10 - Weak Close
  Bot: "We have this coaching package. Does that sound good?"
  Issue: Pitch should use assumptive close, not ask permission
  Fix: "Let's get you started with the 12-week program. When can you begin?"
```

**Implementation** (3-4 days):
1. Add `ChatbotTrainer.identify_mistakes(transcript, analysis_log)` method
2. Use existing `analysis.py` signal detection + FSM state
3. Store mistakes in `session_analytics.jsonl` (new field)
4. Display in post-session report UI

**UAT Validation**:
- "Did highlighted mistakes match what you felt went wrong?" (Yes/No/Partial)
- "Were the suggested fixes helpful?" (Likert 1-5)

---

### F3: Improvement Tips (P0)

**What It Is**: After showing mistakes, give 3-5 actionable tips to improve.

**Why Reps Need It**:
- **Actionability**: Not just "what's wrong" but "how to fix it"
- **Prioritization**: Focus on highest-impact changes first
- **Learning**: Each tip is a mini-lesson on sales technique

**How It Works** (Tip Generation Logic):

| If This Mistake... | Then This Tip... |
|--------------------|------------------|
| Missed 2+ buying signals | "Practice recognizing urgency phrases like 'need soon', 'must have', 'struggling with'. When you hear these, transition to problem exploration." |
| Stuck in INTENT stage (didn't reach LOGICAL) | "Ask follow-up questions to dig deeper. Try: 'What's driving that need?' or 'Walk me through what's not working with your current situation.'" |
| Reached PITCH but score <70% | "Your questioning was shallow. Before pitching, ask at least 3 'why' questions to understand root cause. Example: 'Why is that performance level so critical for you?'" |
| Ignored objection | "When you hear price concerns, never ignore or justify. Instead, reframe: 'What would solving this problem be worth to your business?' Get them to value, not cost." |
| Pitch ended with question | "Assumptive closes work better than asking permission. Instead of 'Interested?', say 'Let's start with X. When can you begin?' Assume the sale." |

**Example Tips Report**:
```
💡 Top 3 Tips to Improve Your Score:

1. Recognize Buying Signals Earlier (Impact: +15 points)
   You missed urgency at turn 4 ("need this soon"). When you hear time pressure,
   transition to problem exploration immediately. Practice recognizing these phrases.

2. Ask More "Why" Questions (Impact: +10 points)
   You asked 3 probing questions, target is 5+. Before pitching, understand root cause.
   Try: "Why is that so important?" or "What happens if nothing changes?"

3. Use Assumptive Closes (Impact: +5 points)
   Your pitch ended with "Does that work for you?" (weak). Instead, assume the sale:
   "Let's get you started with the 12-week package. When's your first session?"

Keep Doing:
✅ Strong objection reframe at turn 7
✅ Good stage progression (reached OBJECTION)
```

**Implementation** (2 days):
1. Template-based tip system (mistake type → tip template)
2. Map mistakes to impact scores (which ones matter most)
3. Return top 3-5 tips sorted by impact
4. Display with "Keep Doing" positives (motivational)

**UAT Validation**:
- "Did tips give you clear actions to take?" (Likert 1-5)
- "Which tip was most helpful?" (Open-ended)

---

### F4: Progress Dashboard (P1)

**What It Is**: Chart showing score trends over time (last 10 sessions).

**Why Reps Need It**:
- **Motivation**: See the learning curve (gamification)
- **Retention**: "I'm getting better" → keep practicing
- **Goal tracking**: "3 more sessions until 80% average"

**How It Works** (Dashboard Metrics):

**Chart 1: Score Trend (Line Graph)**
```
100|
 90|                                *
 80|                    *       *
 70|        *       *       *
 60|    *               *
 50|*
   +----------------------------------
    S1  S2  S3  S4  S5  S6  S7  S8  S9 S10
What I did is.
Current Average: 74/100 (↑8 from last 5 sessions)
```

**Chart 2: Component Breakdown (Bar Graph)**
```
Stage Progression:    ████████████████████████ 85%
Signal Detection:     ████████████████         60% (Needs Work)
Objection Handling:   ████████████████████     75%
Questioning Depth:    ██████████████████       70%
Conversation Length:  ██████████████████████   80%
```

**Chart 3: Most Common Mistakes (Top 3)**
```
1. Missed buying signals        (appeared in 6/10 sessions)
2. Shallow questioning          (appeared in 4/10 sessions)
3. Pitch ends with question     (appeared in 3/10 sessions)
```

**Implementation** (3 days):
1. Query `session_analytics.jsonl` for last 10 sessions
2. Calculate aggregates (mean score, component averages, mistake frequencies)
3. Generate chart data (JSON for frontend)
4. Build dashboard UI (Chart.js or similar)

**UAT Validation**:
- "Did the dashboard motivate you to practice more?" (Yes/No)
- "Did you notice patterns in your mistakes?" (Yes/No)

---

## 4. Phase 2 Features (NICE-TO-HAVE for Advanced Training)

### F5: Real-Time Technique Labels (P1)

**What It Is**: During conversation, show small tags next to each bot message indicating the technique being used.

**Why Reps Need It**:
- **Metacognition**: Learn to recognize techniques as they're being applied
- **Pattern matching**: "Ah, that's what an impact chain looks like"
- **Explicit learning**: Turn implicit methodology into conscious knowledge

**Example**:
```
User: I need a new car because mine keeps breaking down.

Bot: What's it costing you when your car breaks down unexpectedly?
     [TECHNIQUE: Impact Chain - Consequence Awareness]

User: Well, I've missed work twice this month...

Bot: And when you miss work, what does that mean for your income? Your stress levels?
     [TECHNIQUE: Future Pacing - Amplifying Pain]
```

**Implementation** (2 days):
1. Extend `content.py:get_response_prompt()` to return technique label
2. Add `technique` field to LLM response JSON
3. Display in chat UI (small gray tag, expandable tooltip with explanation)

---

### F6: Replay with Edits (P2)

**What It Is**: After session ends, allow rep to go back to any turn, edit their message, and see how the conversation changes.

**Why Reps Need It**:
- **Experimentation**: "What if I asked this instead?"
- **Learning from mistakes**: Fix highlighted errors and see immediate impact
- **Confidence building**: "Oh, that one word change made it work!"

**Example Workflow**:
```
1. Rep reviews session, sees mistake at Turn 4 (missed signal)
2. Clicks "Edit Turn 4"
3. Changes "What features do you need?" to "Why is that timeline so critical?"
4. System re-runs conversation from Turn 4 onward
5. New path shows: Reached PITCH 2 turns earlier, score jumps from 72 → 81
```

**Implementation** (4-5 days):
1. Save full session state (conversation history, FSM stage, analysis log)
2. Add `/api/session/replay` endpoint (takes session_id, turn_index, new_message)
3. Restore state to that turn, insert new message, continue conversation
4. Show side-by-side: "Original path" vs "Edited path"

---

### F7: Expert Comparison (P2)

**What It Is**: At key turning points (e.g., objection raised, closing attempt), show what an expert would have said.

**Why Reps Need It**:
- **Benchmarking**: See the gap between novice and pro
- **Pattern library**: Build mental repertoire of strong responses
- **Confidence**: "I can say it like that too"

**Example**:
```
Turn 7 - Price Objection Raised

Your Response:
  "I understand it's expensive. But we offer financing options."
  Score: 12/20 (Acknowledged but didn't reframe)

Expert Response:
  "I hear you. Before we talk price, help me understand—what would solving this
   reliability issue be worth to you? If you never had to worry about breakdowns again,
   what's that peace of mind worth?"
  Why This Works: Shifts from cost to value, makes them justify to themselves

Try This Next Time: [Button: Apply Expert Response to Turn 7]
```

**Implementation** (3 days):
1. Pre-write expert responses for common scenarios (objections, closes, probing)
2. Match scenarios using objection classification + stage
3. Display in post-session review UI (expandable "See Expert Response")

---

### F8: Quiz Before/After (P2)

**What It Is**: 5-question quiz on NEPQ methodology. Take before first session (pre-test), after 10 sessions (post-test).

**Why Reps Need It**:
- **Assessment**: Measure knowledge gain, not just performance
- **Identifies gaps**: "I score well but don't understand why" → knowledge issue
- **Certification**: Pass quiz + achieve 80% avg score = certified

**Example Questions**:
```
Q1: In the NEPQ framework, what's the primary goal of the LOGICAL stage?
    A) Present product features
    B) Understand the cost of the problem
    C) Close the sale
    D) Build rapport
    [Answer: B]

Q2: When a prospect says "I need to think about it," this is likely a:
    A) Genuine request for time
    B) Smokescreen objection
    C) Partnership objection
    D) Budget objection
    [Answer: B]

Q3: An assumptive close example is:
    A) "Are you ready to buy?"
    B) "Does this sound good to you?"
    C) "Let's get you started. When can you begin?"
    D) "Would you like to proceed?"
    [Answer: C]
```

**Implementation** (2 days):
1. Create question bank (15 questions, randomize 5 per quiz)
2. Store pre-test/post-test scores in DB
3. Show improvement: "Pre-test: 40% → Post-test: 80% (+40%)"

---

## 5. Implementation Roadmap

### Sprint 1: Scoring & Feedback (1 week)
**Goal**: Reps can see how they did and what to fix

| Day | Task | Deliverable |
|-----|------|-------------|
| Mon | Design scoring rubric, create test cases | Scoring algorithm spec |
| Tue | Implement `ChatbotTrainer.score_session()` | Scoring backend working |
| Wed | Implement `ChatbotTrainer.identify_mistakes()` | Mistake detection working |
| Thu | Implement `ChatbotTrainer.generate_tips()` | Tip generation working |
| Fri | Build post-session report UI | F1, F2, F3 deployed |

**Success Metric**: Reps can complete session and get score + tips within 2 seconds

---

### Sprint 2: Progress Tracking (3 days)
**Goal**: Reps can track improvement over time

| Day | Task | Deliverable |
|-----|------|-------------|
| Mon | Query analytics for last 10 sessions, calculate aggregates | Dashboard data API |
| Tue | Build chart UI (score trend, component breakdown) | Charts render |
| Wed | Add "Common Mistakes" section + polish | F4 deployed |

**Success Metric**: Dashboard loads in <1 second, shows actionable insights

---

### Sprint 3: Metacognition (1 week)
**Goal**: Reps understand *why* things work

| Day | Task | Deliverable |
|-----|------|-------------|
| Mon | Extend `content.py` to return technique labels | Backend tags each response |
| Tue | Build real-time label UI with tooltips | F5 deployed |
| Wed | Design expert response templates (10 scenarios) | Expert response library |
| Thu | Match scenarios to expert responses (rules engine) | Matching logic working |
| Fri | Build expert comparison UI in post-session review | F7 deployed |

**Success Metric**: Reps report "I now recognize NEPQ stages" in feedback

---

### Sprint 4: Quiz & Certification (2 days)
**Goal**: Validate knowledge gain

| Day | Task | Deliverable |
|-----|------|-------------|
| Mon | Create 15-question quiz bank, build quiz UI | Quiz functional |
| Tue | Store pre/post scores, show improvement delta | F8 deployed |

**Success Metric**: Pre-test to post-test improvement avg 30%+

---

## 6. UAT Validation (Training-Focused)

Do not replace the Likert questions from the ethics-approved study plan. Those six questions (natural conversation, adaptive, structured, effective, usability) must stay — they were approved. Add the following on top of them.

### Additional questions to add (fit within 5b/5c of the existing protocol)

**If F1 (scoring) is built — add after existing Q6:**
- "Your session score was [X]/100. Does that feel accurate to how you performed?" (Yes/No + why)
- "Would seeing this score after each session motivate you to practise more?" (1-5)

**In section 5c (qualitative, interviewer's discretion) — add these:**
- "Can you name 2 stages the chatbot conversation went through?" — tests explicit stage recall
- "What specific technique did you notice the chatbot using?" — tests NEPQ recognition
- "Could you apply something you noticed here in a real sales conversation?" (1-5) + "Give an example."

### Success criteria (measured from real sessions — no targets pre-set)

| Metric | How measured | Record here |
|--------|--------------|-------------|
| Stage knowledge gain | Baseline answer vs Q7 answer | |
| Structured approach rating | Likert Q3 mean | |
| Learning outcome rating | Likert Q5 mean | |
| Coaching panel utility | Likert Q4 mean | |
| NEPQ technique recognition | Count who name a specific technique in 5c | |
| Transfer intent | Count who say yes to "could apply in real conversation" | |

Targets are determined after data collection, not before. Stating "≥75% say X" before running sessions is speculation, not a success criterion.

---

## 7. Why Each Feature Matters (Training Rationale)

### F1: Scoring → Accountability & Goals
**Training Principle**: "What gets measured gets managed"
- Without scores, practice is aimless
- With scores, reps have targets ("beat 80%")
- Enables manager oversight (require minimum scores)

### F2: Mistake Highlighting → Precision Learning
**Training Principle**: "Feedback must be specific to stick"
- Generic "improve objection handling" doesn't teach
- "At turn 7, you ignored the price objection—here's how to reframe" sticks
- Accelerates skill development by 3x (Ericsson's deliberate practice)

### F3: Improvement Tips → Actionable Next Steps
**Training Principle**: "Show the path, not just the destination"
- Identifying mistakes ≠ knowing how to fix them
- Tips bridge the gap between diagnosis and action
- Prevents frustration ("I know I'm bad, but what do I DO?")

### F4: Progress Dashboard → Retention & Motivation
**Training Principle**: "Visible progress drives persistence"
- Gamification increases engagement by 40% (Deterding et al.)
- Learning curves are motivating if visible
- Prevents dropout ("I'm not getting better" → quits)

### F5: Real-Time Labels → Metacognition
**Training Principle**: "Unconscious competence requires conscious practice first"
- Reps must recognize techniques before applying them
- Labels turn implicit methodology into explicit knowledge
- Accelerates pattern recognition (Dreyfus model of skill acquisition)

### F6: Replay with Edits → Experimentation
**Training Principle**: "Learning requires safe failure + iteration"
- One-shot practice limits exploration
- Replay enables "what if" thinking
- Builds causal understanding ("because I said X, Y happened")

### F7: Expert Comparison → Benchmarking
**Training Principle**: "Modeling expert behavior accelerates skill transfer"
- Reps need to see the gap between current and expert
- Provides mental repertoire of strong responses
- Bandura's social learning theory in action

### F8: Quiz → Knowledge Validation
**Training Principle**: "Performance ≠ Understanding"
- Rep might score well without understanding why
- Quiz validates conceptual knowledge, not just execution
- Enables certification (knowledge + skill = complete training)

---

## 8. Minimum Viable Training System (MVP+)

**If you can only ship 3 features, ship these**:

1. **F1: Scoring** (P0) - Measures performance
2. **F2: Mistake Highlighting** (P0) - Diagnoses problems
3. **F3: Improvement Tips** (P0) - Prescribes solutions

**Why**: This trio creates a complete feedback loop:
- Measurement ("You scored 67%")
- Diagnosis ("Here's what went wrong")
- Prescription ("Here's how to fix it")

Everything else is enhancement, but these 3 are **essential for training**.

---

## 9. Summary: What Makes This a Training Tool

### Before (Current System)
❌ No performance measurement
❌ No learning feedback
❌ No progress visibility
❌ No technique awareness
❌ No improvement path
**Result**: "Fun to try, but doesn't make me better"

### After (With Phase 1 Features)
✅ Clear scores → accountability
✅ Mistake diagnosis → precision learning
✅ Actionable tips → clear next steps
✅ Progress tracking → motivation
**Result**: "I practiced 10 sessions and my score went from 55 → 80. I can now handle price objections confidently."

### After (With Phase 2 Features)
✅ Real-time technique labels → metacognition
✅ Replay with edits → experimentation
✅ Expert comparisons → pattern library
✅ Quiz validation → knowledge certification
**Result**: "I understand NEPQ methodology and can apply it autonomously in real sales calls."

---

## Next Steps

1. **Review this roadmap** - Does the training focus align with your FYP goals?
2. **Implement Scoring MVP** - F1, F2, F3 in 1 week (5 days)
3. **Test with 3 reps** - Get feedback on scoring accuracy and tip helpfulness
4. **Update UAT protocol** - Replace roleplay questions with training impact questions
5. **Document in report** - Section 5.3 "Future Work" → These features with rationale

**This roadmap transforms your project from "chatbot" to "training system."**
