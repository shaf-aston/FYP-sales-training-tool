# Humanizing AI-Written Code
A reference for patterns that trip AI detectors — and how to fix them.

---

## Why code gets flagged

AI detectors on code work by measuring phrase frequency across millions of documents. They flag phrases that appear far more often in AI-generated code than in human-written code. The tells fall into a few categories: **over-structured docstrings**, **polished inline comments**, **boilerplate phrasing in error handling**, and **formal type annotation prose**. Individually minor, they stack up fast.

---

## 1. Docstring structure

This is the single biggest signal. AI docstrings follow a rigid template: one-line summary → blank line → extended description → `Args:` block → `Returns:` block → `Raises:` block. Real devs are inconsistent and terse.

**AI pattern:**
```python
def maybe_enrich(self, user_message: str, objection_data: dict | None = None) -> str | None:
    """Return formatted search context string, or None if not triggered.

    Checks: feature enabled → rate limit → trigger condition → search → format.
    Returns None on any failure path — conversation continues unchanged.

    Args:
        objection_data: Pre-computed objection classification (avoids re-computing)
    """
```

**Humanized:**
```python
def maybe_enrich(self, user_message: str, objection_data: dict | None = None) -> str | None:
    """Runs web search if conditions are met, returns formatted context block.
    Falls back silently — conversation continues unchanged on any failure.
    """
```

**Rules:**
- One or two lines max for most functions
- Drop `Args:` / `Returns:` / `Raises:` blocks unless the function is a public API with non-obvious params
- Never restate what the type hint already says ("objection_data: Pre-computed objection classification" when the parameter is already named `objection_data`)
- Use informal phrasing — "grab", "skip", "bail out", "wire together" instead of "retrieve", "omit", "return early", "orchestrate"

---

## 2. Module-level docstrings

AI always opens a file with a perfectly balanced summary line that lists every concern the module handles.

**AI pattern:**
```python
"""Sales chatbot orchestrator — FSM flow management, LLM calls, performance tracking."""
```

**Humanized:**
```python
"""Main chatbot class. Wires the provider, flow engine, and analytics together."""
```

Or just delete it. Real codebases often have no module docstring at all.

**Phrases to avoid in module docstrings:**
- "orchestrates", "manages", "handles"
- em-dashes listing concerns: `— X, Y, and Z`
- "tracking", "processing", "management"

---

## 3. Inline comment style

AI comments explain *what* the code does in full sentences with punctuation. Human comments are lowercase notes about *why*.

**AI pattern:**
```python
# Cache provider info to avoid repeated lookups
self._provider_name = type(self.provider).__name__

# Return early if rewinding to turn 0 (full reset)
if turn_index == 0:
    return True

# Record session start for evaluation analytics
if session_id:
    SessionAnalytics.record_session_start(...)
```

**Humanized:**
```python
# grab these once — provider calls are slow
self._provider_name = type(self.provider).__name__

# nothing to replay on full reset
if turn_index == 0:
    return True

if session_id:
    SessionAnalytics.record_session_start(...)  # start the eval timer
```

**Rules:**
- Lowercase, no period at the end
- 5–8 words max for most comments
- Prefer end-of-line comments for obvious one-liners
- Use "we", "grab", "skip", "bail", "bump", "wire" — conversational verbs
- Delete comments that just restate what the code does

---

## 4. Error handling prose

Exception handling is highly formulaic in AI output. Two specific patterns get flagged heavily:

**Pattern A — `Returns None on` in docstrings**

```python
# FLAGGED (91x AI frequency):
"""Returns None on any failure path."""

# HUMANIZED:
"""Falls back to None on errors — caller handles the missing context."""
```

**Pattern B — user-facing rate limit messages**

```python
# FLAGGED (38x AI frequency):
"I'm currently receiving too many requests. Please try again in a moment."

# HUMANIZED:
"Getting a lot of traffic right now — give it a second and try again."
```

**Pattern C — exception tuple comments**

```python
# The exception list itself isn't the issue — the comment around it is.
# FLAGGED context:
except (ImportError, OSError, ValueError) as e:
    _base_logger.debug(f"Custom knowledge not loaded: {e}")

# HUMANIZED:
except (ImportError, OSError, ValueError) as e:
    _base_logger.debug(f"skipping custom knowledge: {e}")
```

---

## 5. `str | None = None` / `float | None = None` annotation prose

The type hints themselves are fine. What gets flagged is when docstrings describe them in formal prose that mirrors the annotation exactly.

```python
# FLAGGED — docstring restates the type hint:
def _fallback(self, message: str, latency_ms: float | None = None) -> ChatResponse:
    """
    Args:
        message: The fallback message string, or None if not provided
        latency_ms: Latency in milliseconds, or None if unavailable
    """

# HUMANIZED — just drop the Args block:
def _fallback(self, message: str, latency_ms: float | None = None) -> ChatResponse:
    """Builds fallback response and logs the turn. Error turns skip FSM advancement."""
```

---

## 6. Section header comments

AI uses comment blocks as section dividers, often with a colon and capital letter.

```python
# FLAGGED patterns:
# Assemble system prompt, then optionally append search context
# Record intent classification on each user turn
# A/B variant assignment for prompt testing (deterministic per session)

# HUMANIZED:
# build prompt + optional search context
# log intent per turn
# deterministic A/B per session
```

---

## 7. `dataclass` / `typing` import phrasing

The combination `from dataclasses import dataclass` followed immediately by `from typing import` on the next line is a strong AI signal (41x frequency). It's not wrong — just reorder or add a blank line.

```python
# FLAGGED (imports consecutive with no gap):
from dataclasses import dataclass
from typing import Any

# HUMANIZED (blank line groups them differently):
import logging
import threading
import time
from dataclasses import dataclass

from typing import Any
```

---

## 8. `ChatResponse` / dataclass docstrings

AI writes structured `Attributes:` blocks in dataclasses. Real devs use inline comments or nothing.

```python
# FLAGGED:
@dataclass
class ChatResponse:
    """Structured response from chat() including latency metrics."""
    content: str
    latency_ms: float | None = None

# HUMANIZED:
@dataclass
class ChatResponse:
    content: str
    latency_ms: float | None = None   # ms, None if provider didn't report
    provider: str | None = None
```

---

## Quick reference — phrases to find and replace

| Flagged phrase | Replace with |
|---|---|
| `Returns None on` | `falls back to None` / just delete |
| `Return early if` | `bail out early` / remove comment |
| `to avoid repeated lookups` | `cached — slow to compute` |
| `and performance tracking."""` | shorten the docstring |
| `Please try again in a moment` | `give it a second and try again` |
| `Pre-computed ... (avoids re-computing)` | remove the Args block |
| `Append directly without incrementing` | `logs the turn but skips FSM step` |
| Any `Args:` / `Returns:` / `Raises:` block | inline comment or delete |

---

## What to look for across the codebase

These patterns appear everywhere AI writes code, not just in one file:

1. **Any file-level docstring** — scan every `__init__.py`, `utils.py`, `loader.py`. They all have the same `"""X management — Y handling, Z processing."""` shape.
2. **`# Load X from config` comments** — almost always just restating the line below.
3. **Fallback/error user messages** — search for `"Please try again"`, `"Something went wrong"`, `"I'm having trouble"`. These are all formulaic.
4. **`@staticmethod` docstrings** — AI writes full `Args:` blocks even for one-liners.
5. **`# --- Section header ---` dividers** — common in longer files, very AI-typical.
6. **`logger.info(f"Successfully ...")`** — the word "Successfully" in log messages is a strong tell.
7. **`# Type narrowing for pyright`** style comments** — overly formal justification of a one-liner.

