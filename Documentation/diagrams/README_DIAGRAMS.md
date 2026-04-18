# Diagram Legend & Conventions

## Accuracy Notice

**Recent Corrections (April 2026):**
- ✅ Fixed `02_fsm_state_flow.mmd`: Removed fabricated `NEGOTIATION` stage from `TRANSACTIONAL` flow. Verified against `src/chatbot/flow.py` — TRANSACTIONAL contains only `INTENT → PITCH → OBJECTION`.
- ✅ Created `01_system_architecture.mmd`: Consolidated perspective eliminating redundancy across 5 overlapping "big picture" diagrams.
- ✅ Created `03_runtime_sequence.mmd`: Accurate execution order for `SalesChatbot.chat()` verified against codebase implementation.

All core diagrams now match `src/chatbot/` implementation exactly.

## Color Coding

| Color | Meaning |
|-------|---------|
| **Blue** | Web/API layer, routes, HTTP endpoints |
| **Orange** | Core logic, state machines, decisions |
| **Purple** | LLM providers, external services |
| **Green** | Outputs, results, final deliverables |
| **Gray** | Config files, runtime data, storage |
| **Turquoise** | Orchestration hubs, aggregation points |
| **Red** | Decision nodes, conditionals |

## Symbols

| Symbol | Meaning |
|--------|---------|
| `[ ]` Rectangle | Standard process node |
| `( )` Rounded | Orchestration hub (routing/grouping) |
| `{ }` Diamond | Conditional decision |
| `[( )]` Cylinder | Persistent storage (files, DB) |
| `-->` Arrow | Standard flow |
| `-.->` Arrow | Optional/fallback flow |

## Hub Nodes (Turquoise Ovals)

**What**: Logical aggregation points that bundle multiple arrows to reduce clutter.  
**If multiple independent components feed into one role**: Use a hub (e.g., all web routes → Web Gateway).  
**If single linear steps, single-source endpoints, or decision nodes**: Don't use a hub.


## Diagram Files — Consolidated Structure

### ✅ Core Diagrams (Recommended — Accurate to Codebase)

| File | Purpose |
|------|---------|
| `01_system_architecture.mmd` | **Physical module layout** — Web layer, Core logic, Prospect mode, Providers, Config. Single source of truth for "what calls what". |
| `02_fsm_state_flow.mmd` | **State machine** — FSM stages (INTENT / LOGICAL / EMOTIONAL / PITCH / OBJECTION), decision guards, stage transitions. Fixed: removed fabricated NEGOTIATION state. |
| `03_runtime_sequence.mmd` | **Execution pipeline** — Single chat turn: Request → Prompt assembly → LLM call → FSM advancement → Persistence. Accurate to `SalesChatbot.chat()` implementation order. |

### 📦 Legacy Diagrams (Preserved — May Be Redundant)

The following diagrams still exist but overlap with the three core diagrams above:
- `01_chatbot_big_picture.mmd` — Overlaps with 01_system_architecture
- `02_chatbot_detailed_architecture.mmd` — Overlaps with 01_system_architecture  
- `02_sequence_full_flow.mmd` — Overlaps with 03_runtime_sequence
- `03_conversation_journey.mmd` — Stage progression subset of 02_fsm_state_flow
- `04_session_memory_and_recovery.mmd` — Specialized session lifecycle (not in core diagrams)
- `05_prospect_training_and_quiz.mmd` — Specialized prospect flow (not in core diagrams)
- `06_engineering_map_minimal.mmd` — Overlaps with 01_system_architecture
- `06a_class_diagram_core.mmd` — Class-level detail (not in core diagrams)
- `07_how_responses_are_built.mmd` (now `08_prompt_assembly_pipeline.mmd`) — Overlaps with 03_runtime_sequence
- `11_VOICE_MODE_UNIFIED_COMPLETE.mmd` (now `09_voice_io_complete.mmd`) — Specialized voice flow (not in core diagrams)

**Recommendation:** Start with the three core diagrams for most readers. Use legacy diagrams only if you need specialized deep-dives into session lifecycle, prospect mode, or voice I/O.

## Quick Tips

- **Subgraphs**: Physical grouping (modules/files)
- **Hubs**: Logical routing boundaries (operational roles)
- **Color convention**: Shapes use `:::classname` styling (e.g., `:::web`, `:::core`, `:::hub`)
- **Multi-line labels**: Use `<br/>` for line breaks in node labels
- **For non-technical readers**: Focus on orange nodes (decisions) and turquoise hubs (roles), skip implementation details

