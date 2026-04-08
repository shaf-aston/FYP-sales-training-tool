# Architecture Diagrams Index

This directory contains comprehensive Mermaid diagrams that visualize the sales chatbot architecture, with special emphasis on the **3-Layer Control Architecture** for drift prevention.

## Quick Guide to the 3-Layer Control System

**Problem Solved**: Initial attempts used prompts alone (~70% success). LLM's RLHF priors created semantic drift. Solution: Three independent layers working together.

**Layers**:
- 🟪 **Layer 1 — Prompt Constraints** (Soft): Rules in system prompt guide behavior
- 🔴 **Layer 2 — FSM Guards** (Hard): Block invalid stage transitions  
- 🔵 **Layer 3 — Output Contracts** (Hard): Pattern detection for violations

---

## Diagrams Explained

| File | Purpose | Best For | 3-Layers Highlighted |
|------|---------|----------|---------------------|
| **10_three_layer_control_architecture.mmd** | Complete flow of all 3 layers in one chat turn | **START HERE** to understand drift prevention | ✅ Primary focus |
| **03_chat_turn_sequence.mmd** | HTTP request trace through system with layer annotations | Understanding where each layer is invoked | ✅ Annotated |
| **04_prompt_assembly.mmd** | 4-tier prompt construction pipeline (Tier 1 overrides, etc.) | **Layer 1 deep dive** — how prompt constraints work | ✅ Tier 1 detail |
| **02_fsm_state_machine.mmd** | All stage transitions (INTENT → CONSULTATIVE/TRANSACTIONAL) | Understanding FSM stages & safety valves | ✅ Layer 2 detail |
| **05_nlu_pipeline.mmd** | Intent, sentiment, objection classification | Understanding signal detection that powers Layer 2 & 3 | ⚠️ Related |
| **08_session_lifecycle.mmd** | Session creation, persistence, cleanup | Understanding session state management | ❌ Not related |
| **01_system_architecture.mmd** | High-level module responsibilities | Getting oriented with code organization | ❌ Not related |
| **06_class_diagram_core.mmd** | Class relationships (SalesChatbot, SalesFlowEngine, etc.) | Understanding code structure | ❌ Not related |
| **07_class_diagram_features.mmd** | Feature module classes (Trainer, Quiz, etc.) | Understanding training & evaluation features | ❌ Not related |
| **09_prospect_mode.mmd** | Prospect evaluation & scoring system | Understanding feedback generation | ❌ Not related |

---

## Reading Sequence for Section 2.3.2 Review

If verifying the claims in **"2.3.2 Why Layered Control, Not Just Better Prompts"**, read in this order:

### 1️⃣ Start: 3-Layer High-Level Overview
Open **[10_three_layer_control_architecture.mmd](10_three_layer_control_architecture.mmd)**
- The complete flowchart showing all three layers in one chat turn
- Shows how they interact and what happens at each decision point
- Includes annotations on small-talk loop fix
- References actual file paths and functions

### 2️⃣ Understand Layer 1 in Detail
Open **[04_prompt_assembly.mmd](04_prompt_assembly.mmd)**
- Zooms into Tier 1 (overrides) through Tier 4 (stage assembly)
- Shows where `_SHARED_RULES` are applied
- Shows how override conditions bypass normal pipeline
- Shows how anti-parroting rule is injected

### 3️⃣ Understand Layer 2 in Detail
Open **[02_fsm_state_machine.mmd](02_fsm_state_machine.mmd)**
- Shows all allowed state transitions (guards)
- Shows what signal keywords trigger each transition
- Shows safety valve mechanism (max_turns)
- Shows fast-path commits (early jumps to PITCH)

### 4️⃣ Understand Signal Detection (Powers Layers 2 & 3)
Open **[05_nlu_pipeline.mmd](05_nlu_pipeline.mmd)**
- Shows how keywords are extracted and matched
- Shows how sentiment is detected
- Shows how this feeds into advancement & override decisions

### 5️⃣ See Full Integration
Open **[03_chat_turn_sequence.mmd](03_chat_turn_sequence.mmd)**
- Traces one complete HTTP request through the system
- Shows **where each layer is applied** (via annotations)
- Shows timing (prompt assembly before LLM, FSM check after)
- Shows analytics recording

---

## Code References for Verification

> Note: Function names reflect the codebase at time of writing; logical roles remain stable even if names change. When verifying, grep `src/` for the function if names differ.

### Layer 1: Prompt Constraints
**File**: `src/chatbot/prompts.py`
- Declaration: `_SHARED_RULES` — shared hard constraints (search for `_SHARED_RULES` in the file)
- Referenced from: `src/chatbot/content.py` — `generate_stage_prompt()`

**File**: `src/chatbot/content.py`
- `generate_stage_prompt()` — 4-tier prompt assembly (includes Tier 1 override checks, terse input handling, and persona checkpoint)

**File**: `src/chatbot/overrides.py`
- `check_override_condition()` — priority override checks (direct_info_request, soft_positive, repetitive_validation)

### Layer 2: FSM Guards
**File**: `src/chatbot/flow.py`
- `FLOWS` dict with transitions and `advance_on` conditions
- `_check_advancement_condition()` — applies guards before advancing
- Advancement rules: `user_has_clear_intent()`, `user_shows_doubt()`, etc.
- `get_advance_target()` applies guards to choose safe targets

**File**: `src/chatbot/chatbot.py`
- `_apply_advancement()` — invoked after LLM responses to evaluate advancement
- Main chat loop coordinates analysis → prompt assembly → LLM → advancement

### Layer 3: Output Contracts
**File**: `src/chatbot/analysis.py`
- `text_contains_any_keyword()` — negation-aware keyword matching
- `is_repetitive_validation()` — detects excessive validation patterns

---

## Key Insights

### Why Three Layers?

| Scenario | Layer 1 Alone | Layer 2 Alone | All 3 |
|----------|---------------|--------------|----|
| LLM tries to skip stage | ❌ May drift | ✅ Blocked | ✅ Blocked |
| User gives terse reply | ✅ Terse guidance | ❌ No constraint | ✅ Double-checked |
| Bot repeats "I understand" | ⚠️ Prompt says "no" | ❌ FSM doesn't prevent | ✅ Override triggered |

**Result**: Each layer compensates for others' weaknesses.

### Small-Talk Loop Example

**Scenario**: User says "I need a car." Bot asks validation questions without progressing.

**How 3 Layers Fix It**:

1. **Layer 1** (Prompt): "MAX 1-2 questions per response" + "Never replay >3 words"
   - Prevents bot from asking multiple affirmations in one turn

2. **Layer 2** (FSM Guard): Requires "doubt" signal to leave LOGICAL stage
   - Prevents bot from auto-advancing just because it asked questions
   - Blocks exit after 3 turns if no signal detected

3. **Layer 3** (Output Contract): `is_repetitive_validation()` detects pattern
   - If "I understand" appears 2+ times in last 10 bot messages
   - Triggers override template that forces new topic

**Combined effect**: Bot cannot get stuck in validation loops.

---

## Understanding Mermaid Syntax in This Repo

All diagrams use Mermaid.js (rendered in GitHub, Notion, etc.):

- **Flowchart** (`flowchart TD`): Nodes with flow arrows — use for processes
- **Sequence** (`sequenceDiagram`): Actors passing messages — use for HTTP requests
- **State** (`stateDiagram-v2`): States with transitions — use for FSM

Color coding (consistent across diagrams):
- **Purple** (`#9C27B0`): Prompt/Content decisions
- **Red** (`#D32F2F`): FSM/Flow blocking
- **Blue** (`#1976D2`): Analysis/Contracts
- **Green** (`#388E3C`): Success/Completion

---

## Rendering Diagrams

### Online (Fastest)
Copy-paste `*.mmd` content into: https://mermaid.live

### In VS Code
Install extension: `Markdown Preview Mermaid Support`

### CLI (for PDF/PNG)
```bash
# Install mmdc (Mermaid CLI)
npm install -g @mermaid-js/mermaid-cli

# Render to SVG
mmdc -i 10_three_layer_control_architecture.mmd -o output.svg

# Or to PNG
mmdc -i 10_three_layer_control_architecture.mmd -o output.png
```

---

## Integration with Documentation

- **Section 2.3.2** (Report): "Why Layered Control, Not Just Better Prompts"
  - Reference: 10_three_layer_control_architecture.mmd for visuals
  
- **Appendix A** (Report): "Code References for Iterations"
  - Reference: Diagrams (this folder) for visual citations

- **README.md** (Root): "System Overview"
  - Reference: 01_system_architecture.mmd for module roles

---

## Summary

**For reviewers**: Start with **`10_three_layer_control_architecture.mmd`** to see the complete picture. Then drill into specific layers using the 4-part reading sequence above.




---

## Glossary

- `demands_directness`: a rule used by the NLU to detect explicit user impatience or requests for direct answers. See `src/chatbot/analysis.py` → `user_demands_directness()` for the implementation and heuristics.





