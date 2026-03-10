# Problem and Motivation

## The Sales Methodology Adherence Gap

Existing task-oriented dialogue systems (ToDS) such as MultiWOZ (Wu et al., 2019) optimize for multi-domain intent classification and slot-filling via belief state tracking, yet do not encode sales methodology as a hard constraint on conversational stage progression. LLM-augmented chatbots have ameliorated naturalness in dialogue management (Brown et al., 2020; OpenAI GPT series) but introduce a counterintuitive failure mode: the model produces contextually plausible responses whilst circumventing prescribed stage sequences when user input exhibits resistance or low cooperative intent. This work terms this phenomenon "hallucinated stage adherence"—the model executes stage-appropriate language despite skipping the informational prerequisites that stage is designed to establish.

The independent variable in this system is **user resistance** (operationalized as the absence of NEPQ signal keywords in user messages); the dependent variable is **premature stage advancement**. This failure is empirically demonstrated in ARCHITECTURE.md (Phase 4 FSM fix): prior to correction, the `user_shows_doubt` advancement rule returned `True` after exactly 5 turns regardless of whether prospect-verbalized doubt appeared in the conversation history. Under this regime, a consultative bot could advance to the emotional stage (which presupposes a clearly-named problem and acknowledged pain point) after a user repeatedly asserts confidence in their current approach—rendering Future Pacing and Consequence of Inaction questions semantically ungrounded.

## Dual-Use Contribution

This system makes two distinct contributions that address this gap:

### Training Dimension
A NEPQ-based (Neuro-Emotional Persuasion Questioning, Jeremy Miner, 7th Level Communications) consultative FSM provides a controlled, deterministic environment for methodology internalization. Trainees learn consultative sales not through observation of human exemplars or through open-ended practice, but through roleplay against a bot that enforces each NEPQ stage as a hard state—the bot cannot exit the logical (Problem Awareness) stage without lexical evidence of doubt; cannot exit the emotional stage without evidence of articulated stakes. This makes the framework visible and debuggable. Concurrent coaching via `trainer.py` (real-time generation of stage-specific feedback) anchors the reinforcement to the named methodology.

### Deployment Dimension
Strategy differentiation (consultative = 5-stage NEPQ; transactional = 3-stage NEEDS→MATCH→CLOSE) prevents methodology contamination across product categories. A complex B2B service sale and a simple product purchase require fundamentally different conversational models—the system encodes this divergence in separate prompt hierarchies and advancement rules. This dual-path architecture ensures that methodology adherence is not a universal prompt instruction that can be violated under pressure, but rather a structural property of the system itself.

## Theoretical Grounding

**NEPQ** (Neuro-Emotional Persuasion Questioning, Jeremy Miner): A seven-stage sales framework grounded in behavioral economics and prospect psychology. The framework operationalizes the principle that human beings are most persuasive when they allow others to persuade themselves—thus, stage progression moves from discovery (what does the prospect want) → problem awareness (doubting current approach) → emotional stakes (visualizing future, cost of inaction) → commitment → objection handling. This work implements stages 1–3 within the consultative FSM. Verified free resources: [NEPQ 101 Mini-Course](https://salesrevolution.pro), [7th Level Methodology](https://7thlevelhq.com/our-methodology/).

**Finite State Machine (FSM)**: Mealy/Moore state automata provide deterministic, testable stage management. Unlike implicit state managed by LLM context windows, explicit FSM state is queryable (`flow_engine.current_stage`), transition conditions are declarative (ADVANCEMENT_RULES registry), and violations are auditable.

## Scope and What This Is Not

This system is **not** a retrieval-augmented generation (RAG) system: product knowledge is injected via YAML configuration files (`product_config.yaml`, `custom_knowledge.yaml`), not embedded vector similarity search. It is **not** a generic task-oriented dialogue system wrapped in prompts: deterministic stage enforcement cannot be achieved through instruction alone—the bot architecture itself (the FSM in `flow.py`) prevents stage skipping.

The system is intentionally scoped to consultative and transactional sales. It does not address objection handling subtlety, does not learn or adapt methodology over time, and does not conduct A/B testing to optimize framework variants.

## Target Users

**Dual audience**: (1) Sales trainees internalizing NEPQ methodology through coached roleplay, receiving real-time feedback on stage-appropriate questioning and emotional attunement; (2) sales teams deploying the system as a methodology-enforcing sales assistant, ensuring that product pitches follow established stage sequences rather than skipping to close on the first objection.
