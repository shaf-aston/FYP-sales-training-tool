# User Acceptance Testing (UAT) Strategy and Execution

This document consolidates the User Acceptance Testing (UAT) framework, ensuring clear internal logic, eliminating overlap, and demonstrating a strict correlation with the underlying system architecture (FSM structure, signal analysis).

## 1. UAT Scope, Rationale, and Limitations

**The Core Goal:** The UAT must validate **learning outcomes** and **training effectiveness**, not merely generic UX (e.g., "was the chatbot fun"). Assessors expect proof that the tool achieves its primary mission: improving sales knowledge using the NEPQ methodology.

**The Constraints & Logical Workaround:** 
- **Constraint:** Due to university ethics approval limitations, testing is strictly tied to a single-session, 35-minute protocol per participant.
- **Limitation Acknowledgment:** A single session cannot reliably measure longitudinal, long-term skill acquisition (e.g., the learning curve across weeks). While this is a genuine limitation, it has a compelling workaround.
- **The Workaround Strategy:** Instead of measuring cross-session performance, the UAT captures the **rapid shift from implicit to explicit knowledge**. It measures "Baseline Knowledge vs. Post-Session Knowledge Gain", "Methodology Visibility", and "Transfer Intent." Proving a measurable bump in awareness within 35 minutes validates the system’s utility as a robust training tool.

---

## 2. Testing Objectives Mapped to System Architecture

The UAT directly maps to the 5 core objectives defined in the system's design. This ensures the testing metrics correspond directly with actual codebase functionality:

| Project Objective | What UAT Tests | How It Is Measured in UAT | Codebase Correlation |
| --- | --- | --- | --- |
| **O1: Natural Conversation** | Does it feel realistic vs. scripted? | Likert Q1: "Felt like natural partner" | Output generated via `providers` with fallback logic. |
| **O2: Structured Methodology** | Does it enforce NEPQ stages? | Pre/post-test Stage Knowledge Gap. Qualitative Q4. | `flow.py` (FSM Engine) maintaining strict intent → objection paths. |
| **O3: Adaptive Responses** | Does it detect user signals dynamically?| Likert Q2: "Adapted to what I said" | `analysis.py` identifying user sentiment and signal detection. |
| **O4: Objection Handling** | Are objections classified and reframed?| Open-ended questions on objection realism | `analysis.py`'s `classify_objection` logic in conversational scenarios. |
| **O5: Availability & Usability** | Is it easy to use without guidance? | Likert Q6: Usability & UI interaction | Built-in UI features like `trainer.py` real-time coaching generation. |

---

## 3. Execution Protocol (35-Minute Single Session)

The execution strictly follows the 35-minute approved window but deliberately frontloads learning outcome measurements.

### Phase 1: Pre-Session Baseline (Study Plan Sec 1 - Introduction)
*Before the participant interacts with the chatbot:*
- **Question:** *"Before we start—quick question: What do you think the main stages of a sales conversation are? Just say whatever comes to mind."*
- **Purpose:** Establishes a raw baseline. Most novices say "opening, pitch, close" (3 generic phases). Fits easily into the 1.5 - 2 min introduction limit.

### Phase 2: Roleplay Simulation (Study Plan Sec 2, 3, 4)
- **Scenario 1:** Fitness Prospect (7 min) 
- **Scenario 2:** Midrange Car Buyer (7 min) - *Forces objection handling.*
- **Scenario 3:** Free Exploration (7 min)
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
Users pick 3 of 6 features. Tracking votes for *"Performance feedback"* and *"Sales technique labels"* explicitly builds empirical justification for the Future Work roadmap (F1 & F4).

---

## 4. Key Metrics and Data Interpretation

By structuring the UAT this way, the resulting data natively creates clear impact statements:

- **Stage Knowledge Gain:** If a user jumps from mentioning 2 stages (Baseline) to 5 stages (Post-session) representing NEPQ concepts, the UAT empirically proves methodology transfer.
- **Transfer Intent Percentage:** Capturing instances where participants confidently cite a specific maneuver (e.g., *"I'd ask why the timeline matters instead of just listing features"*) provides concrete evidence that the simulation prepares users for real human roles.
- **Technical Validation Evidence:** By tracking whether participants hit the **"PITCH"** or **"OBJECTION"** state in `flow.py`, you tie performance metrics directly to the FSM boundaries.

---

## 5. Integrating UAT Gaps into Future Work

Any UAT limitations or highly desired features discovered are logically funneled into the **Future Work** section, directly corresponding to existing components in the repository:

1. **Post-Session Scoring (F1):** 
   - *Rationale:* Users felt they didn't know an explicitly quantifiable "score". 
   - *Architectural Grounding:* Could map `session_analytics.py` data to score progression (30% logic, 25% signal detection matches).
2. **Mistake Highlighting (F2):** 
   - *Rationale:* Users identified they were repeating errors. 
   - *Architectural Grounding:* Turn-level anomaly detection extending `analysis.py`.
3. **Progress Dashboard (F3):** 
   - *Rationale:* Bridges the primary UAT limitation (single-session) by enabling long-term gamification. 
   - *Architectural Grounding:* Utilizes the output of `metrics.jsonl` and `analytics.jsonl` dynamically.

This structure proves that every feature is designed strictly with learning outcomes in mind, rooted directly in the backend code systems, and evaluated properly within ethical constraints.