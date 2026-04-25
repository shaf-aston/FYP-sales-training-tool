# CRITICAL FIXES STATUS

**Current state:** The codebase now reflects the knowledge sanitisation and nullable-latency fixes.

## Completed in code

- `core/knowledge.py` now loads `config/knowledge_sanitization.yaml` and reads `suspicious_patterns`.
- `backend/routes/chat.py` and `backend/routes/voice.py` now serialize latency values safely when `latency_ms` is `None`.

## Still worth reviewing in the write-up

- Keep the architecture diagram and report notes aligned with the current module names and behavior.
- If you mention latency metrics in the report, note that route serialization now treats missing latency as a valid case.

## Historical context

This file was originally used to track the pre-patch mismatches. It is kept as a lightweight reference, not as an active task list.
