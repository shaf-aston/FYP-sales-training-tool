## The Bug: Jumping Ahead Too Soon

### What the system does

This is a sales chatbot following a method called NEPQ, built around two sequential stages:

1. **Logical stage** - Get the prospect to admit they have a problem
2. **Emotional stage** - Ask how life would look if that problem were solved

The emotional questions only make sense **after** a problem has been acknowledged. Without that foundation, asking "how would things be different if we fixed your problem?" is a non-sequitur - the prospect never said they had one.

---

### The bug

The old code advanced to the emotional stage after **5 messages, regardless of what the prospect said**:

```python
def user_shows_doubt(history, user_msg, turns):
    doubt_keywords = ['not working', 'struggling', 'problem', ...]
    return text_contains_any_keyword(recent_text, doubt_keywords) or turns >= 5  # ❌ Always True after 5 turns
```

The `or turns >= 5` means the keyword check is irrelevant - after 5 messages the condition is always `True`. So even if the prospect spent all 5 messages saying *"I'm doing great, very happy, no complaints"* - the bot would still ask "what would life look like if we solved your problem?"

The question has no ground to stand on, and the prospect knows it.

---

### The fix

The new code only advances when the prospect actually **uses a doubt word**:

```python
def user_shows_doubt(history, user_msg, turns):
    return _check_advancement_condition(history, user_msg, turns, 'logical', min_turns=2)
```

Which resolves to:

```python
keywords = stage_config.get(keyword_key, [])  # reads doubt_keywords from analysis_config.yaml
has_signal = text_contains_any_keyword(recent_text, keywords)
return has_signal or turns >= max_turns  # ✅ safety valve at 10, not 5
```

The doubt words themselves come from config - explicit and auditable:

```yaml
advancement:
  logical:
    doubt_keywords:
      - "not working"
      - "struggling"
      - "problem"
      - "inconsistent"   # e.g. "results have been inconsistent lately"
      - "failing"
      # ...25 terms total
```

No doubt word? The bot stays patient and keeps probing - up to **10 messages** as a safety net, not a trigger.

---

### Before vs. after

| | Old | New |
|---|---|---|
| Advances when... | 5 messages pass | Prospect says a doubt word |
| Safety limit | 5 messages | 10 messages |
| Coherent to prospect? | ❌ Often not | ✅ Yes |

---

### The core lesson

Don't let the AI *judge* when a stage is complete. Give it a **clear, testable rule** - did the prospect say one of these 25 words? That's auditable and reliable. 