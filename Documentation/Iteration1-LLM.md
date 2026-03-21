# Iteration 1 — Local LLM (Qwen2.5)

## Overview
The first iteration ran a local Qwen2.5 model on the development machine for all response generation. The chatbot attempted to follow the IMPACT sales methodology, supplemented by external sales datasets. The model was upgraded mid-iteration from 0.5B to 1.5B parameters after severe quality failures, but neither resolved the core latency problem.

## Duration
Approximately 3 months.

## Hardware
- Development machine: Lenovo ThinkPad (Intel i7-8550U, 11 GB RAM total; ~3 GB available at runtime — Windows and VS Code consuming ~8 GB)
- Model stage 1: Qwen2.5-0.5B (~1 GB RAM; smallest available instruct model, chosen for minimal footprint)
- Model stage 2: Qwen2.5-1.5B (~3 GB RAM; upgraded mid-iteration after 0.5B quality failures — ~3x reduction in issues, but latency remained unacceptable)

## Methodology
- Target framework: IMPACT formula
- External sales datasets incorporated (e.g. SalesCentre and similar corpora) to ground responses in real sales language
- Datasets introduced additional inconsistencies independent of the model itself

## Inference Latency
- 3–5 minutes per response (Qwen2.5-1.5B on available hardware)
- Root cause: memory bandwidth bottleneck (i7-8550U dual-channel LPDDR3 at ~38 GB/s) + continuous page-file swapping with only ~3 GB free RAM + thermal throttling from 2.7 GHz to 1.4–1.8 GHz after ~90 seconds of sustained load
- Latency was a primary usability blocker; made real-time conversation practice infeasible

## Observed Failures

### 1. Response Truncation
Output token limits were applied to reduce inference time — this caused responses to cut off mid-sentence or mid-argument before completing a stage objective. Removing the limit restored coherence but returned full latency. No viable middle ground was found.

### 2. Verbose / Unfocused Output ("Waffle")
Model produced excessively long responses that lost conversational focus. Rather than advancing the IMPACT stage, output often restated context or repeated previous points without progression.

### 3. Markdown Artefacts in Output
Despite explicit prompt instructions prohibiting markdown formatting, the model injected heading symbols (`####`), emphasis markers (`*****`), and role labels (`Salesperson:`) into conversational responses. This required an additional post-processing layer to strip artefacts before presenting output to the user.

### 4. Role Confusion
The model intermittently generated salesperson responses instead of maintaining the customer/prospect persona. Conversation structure would invert — the bot would offer solutions rather than express needs or objections — breaking the training scenario entirely.

### 5. Prompt Non-Adherence
Prompt-level constraints were inconsistently followed. Behavioural instructions (tone, stage adherence, format) did not reliably propagate to output, even with repeated reinforcement in the system prompt.

### 6. Dataset Integration Issues
External sales datasets added noise. Some dataset phrasings conflicted with the methodology prompts, producing inconsistent persona behaviour regardless of model parameters.

## Conclusion
The combination of multi-minute latency, role confusion, unreliable prompt adherence, and the need for post-processing to correct output artefacts made this approach unviable for interactive training. Following supervisor feedback, the approach was revised toward a first-principles rule-based technique to regain control over conversation flow — the basis of Iteration 2.
