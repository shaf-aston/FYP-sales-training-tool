# User Acceptance Testing (UAT) Strategy and Execution

This document consolidates the User Acceptance Testing (UAT) framework, ensuring clear internal logic, eliminating overlap, and demonstrating a strict correlation with the underlying system architecture (FSM structure, signal analysis).

## 1. UAT Scope, Rationale, and Limitations

**The Core Goal:** The UAT must validate **learning outcomes** and **training effectiveness**, not merely generic UX (e.g., "was the chatbot fun"). Assessors expect proof that the tool achieves its primary mission: improving sales knowledge using the NEPQ methodology.

**The Constraints & Logical Workaround:**
- **Constraint:** Due to university ethics approval limitations, testing is strictly tied to a single-session, 35-minute protocol per participant. **Sample size: N = [X] participants** (to be confirmed).
- **Limitation Acknowledgment:** A single session cannot reliably measure longitudinal, long-term skill acquisition (e.g., the learning curve across weeks). While this is a genuine limitation, it has a compelling workaround.
- **The Workaround Strategy:** Instead of measuring cross-session performance, the UAT captures the **rapid shift from implicit to explicit knowledge**. It measures three outcomes: (1) "Stage Knowledge Gain" (baseline vs. post-session NEPQ terminology), (2) "Transfer Intent" (participants citing a specific technique they’d use), and (3) "FSM Structural Reach" (did participants encounter deeper stages?). Proving measurable gains within 35 minutes validates the system’s utility as a robust training tool.

---

## 2. Testing Objectives Mapped to System Architecture

The UAT directly maps to the 5 core objectives defined in the system's design. This ensures the testing metrics correspond directly with actual codebase functionality:

| Project Objective | What UAT Tests | How It Is Measured in UAT | Codebase Correlation |
| --- | --- | --- | --- |
| **O1: Natural Conversation** | Does it feel realistic vs. scripted? | Likert Q1: "Felt like natural partner" | `content.py` (prompt assembly) and `analysis.py` (signal detection for lexical entrainment). |
| **O2: Structured Methodology** | Does it enforce NEPQ stages? | Pre/post-test Stage Knowledge Gap. Qualitative Q4. | `flow.py` (FSM Engine) maintaining strict intent → objection paths. |
| **O3: Adaptive Responses** | Does it detect user signals dynamically?| Likert Q2: "Adapted to what I said" | `analysis.py` identifying user sentiment and signal detection. |
| **O4: Objection Handling** | Are objections classified and reframed?| Open-ended questions on objection realism | `analysis.py`'s `classify_objection` logic in conversational scenarios. |
| **O5: Availability & Usability** | Is it easy to use without guidance? | Likert Q6: Usability & UI interaction | `index.html`, `app.js`, and Flask routing (`src/web/app.py`) enable seamless chat interface. |

---

## 3. Execution Protocol (35-Minute Single Session)

The execution strictly follows the 35-minute approved window but deliberately frontloads learning outcome measurements.

### Phase 1: Pre-Session Baseline (Study Plan Sec 1 - Introduction)
*Before the participant interacts with the chatbot:*
- **Question:** *"Before we start—quick question: What do you think the main stages of a sales conversation are? Just say whatever comes to mind."*
- **Purpose:** Establishes a raw baseline. Most novices say "opening, pitch, close" (3 generic phases). Fits easily into the 1.5 - 2 min introduction limit.

### Phase 2: Roleplay Simulation (Study Plan Sec 2, 3, 4)
- **Scenario 1:** Fitness Prospect (7 min) — Participant plays a sales rep. Bot plays a fitness coaching prospect. Goal: practice discovery and objection handling.
- **Scenario 2:** Midrange Car Buyer (7 min) — Participant plays sales rep for a car dealership. Bot simulates a prospect with explicit price objection. Forces objection handling via `flow.py:objection` stage and `analysis.py:classify_objection()`.
- **Scenario 3:** Free Exploration (7 min) — Participant chooses product/role (or tests the "Prospect Mode" where they play the prospect and the bot plays sales rep). Captures learning transfer: can they apply a technique they noticed?
- **Mid-Session Pulse Check:** Ask, *"Are you looking at the coaching panel on the right? What is it telling you right now?"*
  *(This validates the `trainer.py:generate_training()` real-time function during transitions.)*

### Phase 3: Post-Session Interview (Study Plan Sec 5)
**Likert Scale & Direct Questions (Sec 5b):**
1. Conversational Quality (Natural/Adaptive/Scripted)
2. Sales Ability (Structured approach/Effectiveness)
3. Usability (Ease of Use)
4. Objection handling & Missed opportunities (Open-ended)

**Learning Outcome Questions (Sec 5c "Discretionary" Section):**
*The protocol explicitly allows discretionary questions here, giving ethical clearance for these three additions:*
1. **Q7 (Stage Knowledge Gain):** *"Earlier you mentioned X, Y, and Z. Now, can you describe what stages the conversation actually went through?"*
2. **Q8 (Methodology Recognition):** *"Did you notice specific sales techniques the chatbot was using? (e.g., digging into consequences?)"*
3. **Q9 (Transfer Intent):** *"Could you apply something you noticed here in a real customer conversation tomorrow? Give me an example."*

**Feature Priorities (Sec 5d):**
Participants pick 3 of 6 desired features to prioritise future development. The 6 options are:
1. **Post-Session Scoring** — Quantified performance score with breakdown
2. **Mistake Highlighting** — In-session alerts when repeating errors
3. **Progress Dashboard** — Multi-session tracking and gamification
4. **Sales Technique Labels** — Explicit coaching labels (e.g., "future pacing" pop-up)
5. **Quiz Assessment** — Pre/post methodology quizzes
6. **Recording & Replay** — Video/transcript archive of past sessions

Tracking votes for *"Performance feedback"* (option 1) and *"Sales technique labels"* (option 4) explicitly builds empirical justification for the Future Work roadmap (F1 & F4).

---

## 4. Key Metrics and Data Interpretation

**Primary claim:** A single 35-minute session produces a measurable shift from surface-level sales knowledge (2–3 generic stages) to NEPQ-structured awareness (5 stages with rationale), evidenced by pre/post comparison of Q7 responses. The two supporting metrics below corroborate this claim from behavioural and technical angles.

- **Stage Knowledge Gain** *(primary metric)*: Scored by counting distinct NEPQ-labelled stages a participant can name and briefly explain before vs. after the session (Q7). A response is credited only when the participant names the stage *and* gives a rationale (e.g., "I'd ask about consequences, not just symptoms" counts; "there was a questioning part" does not). **Success threshold:** the mean gain across all N participants is ≥2 named stages. Coded independently by the researcher against a fixed rubric; no LLM scoring. Example: if N=10 and gains are [2,3,1,2,2,2,3,1,2,2], the mean is 2.0 → success.

- **Transfer Intent** *(behavioural corroboration)*: The percentage of participants who, in Q9, cite a specific technique they could apply in a real conversation the next day — with an example. Scored binary per participant (yes/no): a vague "I'd ask more questions" does not qualify; a technique-plus-context answer does (e.g., "I'd use a consequence question when they mention a problem but aren't urgent"). Denominator = all participants who completed the session.

- **FSM State Reach** *(technical corroboration)*: For each participant session, the researcher retrieves the final logged stage from `GET /api/analytics/session/<session_id>` and records whether the session reached PITCH or OBJECTION state (the deeper stages). Reaching OBJECTION state confirms the FSM enforced at least 4 stage transitions (intent → logical → emotional → pitch → objection), the structural backbone of NEPQ methodology. This is cross-referenced against Q4 and Q8 qualitative responses to confirm participants noticed the stage progression — i.e., methodology transfer is reflected not just in system logs but in participant awareness.

