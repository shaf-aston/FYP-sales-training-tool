# Oral Exposition: 40-Minute Demo Script

## 1. Presentation Structure (10 Mins)
**Objective:** Establish the business problem, the hypothesis, and the architectural solution.
*   **Slide 1: Problem Domain** - Sales training requires reactivity under pressure. Live roleplay is expensive, and unconstrained LLMs drift into generic bot-personas or hallucinate.
*   **Slide 2: Architectural Hypothesis** - "Constraint over Fine-tuning." We use a deterministic finite state machine (FSM) to control *when* to advance stages, and an LLM to control *what* to say.
*   **Slide 3: Provider Abstraction** - Highlight zero-cost deployment (Render + Groq) achieving ~900ms inference speeds locally.
*   **Slide 4: Validation Data** - Quick summary: 92% stage adherence over automated tests, 84.5 SUS score from 8 UAT users. 

## 2. Live Demo Scenarios (20 Mins)
### Scenario 1: The Consultative Flow (NEPQ Framework)
*   **Action**: Execute a positive path. 
*   **Goal**: Show the system asking discovery questions, exploring emotional stakes, and waiting for the user to express explicit intent.
*   *Demonstrate*: Open the Debug Panel in the UI. Show that the backend NLU classifies intent as "Low", forcing the FSM into the `Intent` or `Logical` stage.

### Scenario 2: The Premature Pitch (Handling Drift)
*   **Action**: As the user, immediately type: "Just tell me the price of your enterprise tier."
*   **Goal**: Show that the LLM *does not* blindly answer the question. The FSM blocks the transition, and the NLU detects a need for "Pushback" or guarded acknowledgement.
*   *Demonstrate*: Show the logs/Trace panel output showing the prompt constraint P1 firing, redirecting the user back to the discovery phase.

### Scenario 3: The Transactional Pivot
*   **Action**: Express extreme urgency ("I need this implemented by Tuesday, we have a budget of 5k").
*   **Goal**: Show the FSM immediately skipping `Logical` and `Emotional` stages and going straight to `Pitch` because of the explicit threshold bypass.
*   *Demonstrate*: Show the JSON metrics capturing the strategy pivot event.

### Scenario 4: The Objection Sandbox
*   **Action**: Give a classic Price objection ("This seems too expensive compared to XYZ").
*   **Goal**: Show the LLM classifying the objection type correctly as "Price", recalling context, and delivering a reframed response based on the `signals.yaml` configuration.

## 3. Defense / Q&A Preparation (10 Mins)
Anticipate the following assessor questions:
1.  **"Why didn't you just fine-tune an open-source model?"**
    *   *Ans:* Cost-efficiency and rigid structural guarantees. A fine-tuned model can still hallucinate a stage jump; a deterministic state machine mathematically evaluates guard conditions before transition. It is also radically cheaper.
2.  **"How does your NLU avoid simple pattern-matching brittleness?"**
    *   *Ans:* As validated in UAT, the system employs negation-aware regex mapped across priority hierarchies, mitigating cases where users say "I don't have an issue."
3.  **"What happens when the LLM provider goes down?"**
    *   *Ans:* The codebase uses an interface (`BaseLLMProvider`). The `Factory` can default back from primary (Groq) to a secondary (Ollama) seamlessly.
