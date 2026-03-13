# Iteration 2 — First-Principles Fuzzy Matching

## Overview
The second iteration replaced the local LLM with a deterministic, rule-based approach to conversation flow. Rather than using a dialogue management framework (Dialogflow, Rasa), the system was built from first principles using fuzzy string matching to classify user input and select scripted responses.

## Duration
Approximately 1 month (mid-December to January).

## Approach
User utterances were matched against a set of predefined intent patterns using fuzzy string similarity (e.g. token-ratio matching via a library such as `rapidfuzz` / `fuzzywuzzy`). Based on the closest match, the system selected a scripted response and advanced through the IMPACT formula stages deterministically. No LLM was involved in response generation.

## Motivation (Problems Addressed from Iteration 1)
- Eliminate multi-minute LLM inference latency
- Enforce strict adherence to the IMPACT formula stage sequence
- Remove dependency on a local model that could not reliably follow prompt constraints
- Gain full, auditable control over conversation flow without a third-party dialogue platform

## Latency
Near-instantaneous. Pattern matching and response selection were fast enough for real-time conversation.

## Observed Failures

### 1. Rigidity of Responses
Scripted responses could not adapt language to the user's specific phrasing, context, or product domain. Every matched intent produced the same fixed reply, making repeated conversations feel mechanical and predictable.

### 2. High Manual Maintenance Cost
Each new intent, stage variation, or edge case required separately hand-coding response branches. The approach scaled poorly — adding coverage for one strategy required substantial duplicated effort.

### 3. No Support for Multiple Strategies
The architecture could not flexibly accommodate different sales strategies (e.g. consultative vs. transactional) without a near-complete rewrite of the matching and routing logic.

### 4. Lack of Humanisation
Responses lacked natural variation in language. While the stage-progression logic was sound, the output was noticeably robotic — unsuitable for a training tool where realistic human-like dialogue is a core requirement.

## What Worked
- Stage-sequencing and process adherence to the IMPACT formula were reliable
- Response latency was not a bottleneck
- Deterministic control over conversation flow was fully achieved

## Conclusion
Iteration 2 demonstrated that deterministic stage control was achievable and valuable, but scripted responses were insufficient for a realistic training experience. The final architecture (current system) retained the deterministic FSM for stage management from this iteration while restoring LLM generation — now via a cloud provider (Groq) — for natural language output within each stage.
