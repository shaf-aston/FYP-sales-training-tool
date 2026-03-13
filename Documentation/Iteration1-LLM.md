# Iteration 1 — Local LLM (Qwen2.5)

## Overview
The first iteration ran a local Qwen2.5 model on the development machine for all response generation. The chatbot attempted to follow the IMPACT sales methodology, supplemented by external sales datasets.

## Duration
Approximately 3 months.

## Hardware
- Local inference on development machine (11 GB RAM)
- Model: Qwen2.5 (quantised to fit within RAM constraint)

## Methodology
- Target framework: IMPACT formula
- External sales datasets incorporated (e.g. SalesCentre and similar corpora) to ground responses in real sales language
- Datasets introduced additional inconsistencies independent of the model itself

## Inference Latency
- 3–5 minutes per response
- Latency was a primary usability blocker; made real-time conversation practice infeasible

## Observed Failures

### 1. Response Truncation
Model would cut off mid-sentence or mid-argument. Responses frequently ended abruptly before completing a sales stage objective.

### 2. Verbose / Unfocused Output ("Waffle")
Model produced excessively long responses that lost conversational focus. Rather than advancing the IMPACT stage, output often restated context or repeated previous points without progression.

### 3. Markdown Artefacts in Output
Despite explicit prompt instructions prohibiting markdown formatting (e.g. `####` headers), the model intermittently injected heading symbols and other markdown tokens into conversational responses. This required an additional post-processing layer to strip artefacts before presenting output to the user.

### 4. Prompt Non-Adherence
Prompt-level constraints were inconsistently followed. Behavioural instructions (tone, stage adherence, format) did not reliably propagate to output, even with repeated reinforcement in the system prompt.

### 5. Dataset Integration Issues
External sales datasets added noise. Some dataset phrasings conflicted with the methodology prompts, producing inconsistent persona behaviour regardless of model parameters.

## Conclusion
The combination of multi-minute latency, unreliable prompt adherence, and the need for post-processing to correct output artefacts made this approach unviable for interactive training. Following supervisor feedback, the approach was revised toward a first-principles rule-based technique to regain control over conversation flow — the basis of Iteration 2.
