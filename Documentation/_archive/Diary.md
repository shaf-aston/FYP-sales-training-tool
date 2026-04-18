# DONT REMOVE THIS FILE

## Appendix C: Project Development Diary (condensed)

Project: Sales conversation AI chatbot — FSM-driven routing, prompt-based behavioural control, and real-time coaching feedback.
Timeline: September 2025 – April 2026 (28 weeks)

Merged narrative (essentials):
- Sep–Nov: Early prototype used a local LLM + FastAPI. High latency, memory pressure and limited context made interactive training unusable → pivot to cloud APIs.
- Nov–Jan: Ethics review and planning; cloud approach chosen for responsiveness. Provider options were evaluated (an option informally labelled "Lotus" was noted); the team adopted a cloud-API integration (Groq initially) but kept a provider abstraction so alternatives (including Lotus) remain revisit-able.
- Feb: Architecture refactor — the Strategy Pattern proved brittle and tightly coupled. Replaced with a YAML-driven finite-state machine to ensure deterministic, auditable stage transitions editable by non-engineers.
- Mar: Behaviour safety & hardening — added fixed-order prompt layering (overrides → adaptations → baseline), stage-gated objection SOP injection, whole-word keyword matching, and one-question-per-turn guardrails to prevent prompt leakage and false positives.
- Apr: Simulation & evaluation — role-specific prospect framing to avoid ground-truth leakage; deterministic, session-locked A/B assignment and analytics for repeatable evaluation. Tests and analytics integrated to measure regressions.

Key outcomes:
- Behaviour now scales through configuration (YAML) rather than code; most changes are YAML edits + focused tests.
- Provider abstraction preserves the option to revisit alternatives noted during evaluation (e.g., Lotus).
- Tests and analytics are in place to guard regressions and validate changes.

Lessons (short):
- Establish test scenarios earlier.
- Prioritise prompt engineering and configuration-driven design from the start.
- Document decisions continuously, as narrative aids evaluation and maintenance.

For full historical detail and commit-level evidence, see:
- Documentation/technical_decisions.md
- Documentation/ARCHITECTURE_CONSOLIDATED.md

