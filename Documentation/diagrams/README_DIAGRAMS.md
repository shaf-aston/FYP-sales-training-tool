# Diagrams Index (Beginner-First)

This folder now uses a merged 6-diagram set designed to be simple enough for a 12-year-old, while still covering the full system.

## Primary Diagram Set

| File | What it explains | Audience |
|---|---|---|
| `01_chatbot_big_picture.mmd` | End-to-end map of one message through client, server, AI providers, and storage | Beginner |
| `02_conversation_journey.mmd` | Stage progression (consultative and transactional) plus the 3 safety checks | Beginner |
| `03_how_responses_are_built.mmd` | How message understanding and prompt-building combine before each AI call | Beginner |
| `04_session_memory_and_recovery.mmd` | New session, resume, restore, and rebuild paths | Beginner |
| `05_prospect_training_and_quiz.mmd` | Prospect roleplay, evaluation, hints, and the 3 quiz types | Beginner |
| `06_engineering_map_minimal.mmd` | Minimal technical map of key modules and dependencies | Technical appendix |

## Recommended Reading Order

1. `01_chatbot_big_picture.mmd`
2. `02_conversation_journey.mmd`
3. `03_how_responses_are_built.mmd`
4. `04_session_memory_and_recovery.mmd`
5. `05_prospect_training_and_quiz.mmd`
6. `06_engineering_map_minimal.mmd` (optional for non-technical readers)

## Merge Mapping (Old -> New)

| Legacy file(s) | New file |
|---|---|
| `01_system_architecture.mmd` + `03_chat_turn_sequence.mmd` | `01_chatbot_big_picture.mmd` |
| `02_fsm_state_machine.mmd` + `10_three_layer_control_architecture.mmd` | `02_conversation_journey.mmd` |
| `04_prompt_assembly.mmd` + `05_nlu_pipeline.mmd` | `03_how_responses_are_built.mmd` |
| `08_session_lifecycle.mmd` | `04_session_memory_and_recovery.mmd` |
| `09_prospect_mode.mmd` | `05_prospect_training_and_quiz.mmd` |
| `06_class_diagram_core.mmd` + `07_class_diagram_features.mmd` | `06_engineering_map_minimal.mmd` |

Legacy diagrams have been removed from the active set. The mapping table above is kept only as migration history.

## Consistency Rules Used

1. One legend per diagram.
2. Plain language first, technical detail second.
3. Short node labels and fewer branches.
4. Same meaning for color categories across files.
5. Runtime strategy branching shown as flow logic, not as a Strategy-pattern class design.

## Rendering

### Mermaid Live

Paste any `.mmd` file into https://mermaid.live

### VS Code

Use Mermaid preview support in markdown/diagram tooling.

### CLI

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i 01_chatbot_big_picture.mmd -o 01_chatbot_big_picture.svg
```





