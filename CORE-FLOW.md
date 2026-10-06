# CORE-FLOW

Practise a sales conversation against an AI, then see each turn rated and why.

## Run

```bash
pip install -r requirements.txt
python backend/app.py        # http://localhost:5000
pytest
cd web && npm run build    # UI lives in web/ (Next.js); Flask serves the built web/out
```

## Two modes, two engines

| Mode | You are | The AI is | Engine | Routes |
|---|---|---|---|---|
| Prospect mode (main) | salesperson | buyer | `core/buyer_session.py` `BuyerSession` | `backend/routes/prospect.py` |
| Seller-bot mode | customer | seller | `core/seller_bot.py` `SellerBot` | `backend/routes/chat.py`, `session.py` |

Open the engine for the mode you are working on. Nothing else decides the turn.

## Core flow (prospect mode)

| # | Step | File | Why it exists |
|---|---|---|---|
| 1 | Browser posts the salesperson's line | `web/src/lib/api/client.ts` (`/api/prospect/chat`) | The one place the UI talks to the API. |
| 2 | Route checks rate limit, message, session | `backend/routes/prospect.py` `prospect_chat`; `backend/routes/_utils.py` `require_session` / `validate_message` | Transport. Shapes JSON, holds no sales logic. Sessions live in `app.extensions["sessions"]` (`Sessions(seller, buyer)`). |
| 3 | Engine runs the turn | `core/buyer_session.py` `BuyerSession.process_turn` (and `redo`, which rolls itself back on failure) | Orchestrates: rate the line, move readiness, pick objection pacing, store history, save. |
| 4 | Pure rules decide | `core/selling_quality.py` (rating), `core/buyer_rules.py` (sold / walked), `core/buyer_prompt.py` (buyer system prompt) | Deterministic. No I/O, no HTTP, easy to test. |
| 5 | Router picks a provider | `core/services/provider_router.py` `chat_with_fallback` | Tries providers in order, falls back on failure. |
| 6 | Provider calls the LLM | `core/providers/factory.py` → `providers/llm/groq.py` behind `providers/base.py` | Swap seam: every provider has the same interface. |
| 7 | Review and analytics | `core/session_review.py` (per-turn replay), `core/prospect_evaluator.py` (final score + grade), `core/analytics/session_analytics.py` (events to JSONL) | Everything shown after the session is rebuilt from the saved transcript. |

Seller-bot mode: `chat.py` → `SellerBot.chat` → `core/script_engine/` (scripted lines for products in `config/selling.yaml`, AI only fills small gaps; every AI sentence goes through `ai_line.py` `checked_line`) or else `flow.py` (stage machine) · `analysis.py` (buyer signals) · `content.py` + `prompts.py` (prompt build) · `response_guardrails.py` (output checks) → same router. Coaching comes from `trainer.py`.

## Config

Every tunable number lives in `config/limits.yaml`; `core/constants.py` is its only reader and refuses zero or negative values at start-up. LLM calls take a named profile from it (`**LLM["buyer_reply"]`), never literal numbers.

`core/loader.py` reads `signals`, `analysis_config`, `objection_flows`, `product_config`, `prospect_config`, `adaptations`. The module that owns a feature reads its own file: `objection.py` → `objection_pathway_map`, `quiz.py` → `quiz_config`, `script_drills.py` → `script_drills`, `selling_quality.py` → `selling_signals`, `knowledge.py` → `knowledge_sanitization`.

Questions: `core/utils.py` `is_question` is the one rule for both modes (word lists from config). Analytics: every event goes through `SessionAnalytics.record`.

Environment: `backend/settings.py` reads app env (origins, debug, admin token); `core/providers/config.py` reads LLM keys and models. No other module touches the environment, except `METRICS_JSONL_PATH` in `core/analytics/session_analytics.py`.

## Glossary (the words the code uses)

| Term | Meaning | Owner |
|---|---|---|
| **stage** | Where the conversation is: intent → logical → emotional → pitch → negotiation → objection → outcome. `Stage.OUTCOME` is the closing stage, not the result. | `core/enums.py`, `core/flow.py` |
| **strategy** | Which stage sequence the seller bot follows: consultative, transactional, or `intent` (not chosen yet). Stored as `flow_type` in `flow.py` and saved sessions. | `core/enums.py`, `core/flow.py` |
| **signal** | Keyword groups that detect what the buyer means (`signals.yaml`). `selling_signals.yaml` is different: weights for rating the salesperson's language. | `core/analysis.py`, `core/selling_quality.py` |
| **readiness** | Buyer's 0–1 willingness to buy. Moves every turn and decides sold or walked. | `core/buyer_session.py`, `core/buyer_rules.py` |
| **outcome** | End result of a prospect session: `sold`, `walked`, or none yet. | `core/buyer_rules.py` `end_outcome` |
| **objection** / **pathway** | Buyer pushback, typed by `ObjectionType`; a pathway maps the type to a category and handling script. | `core/objection.py`, `config/objection_pathway_map.yaml` |
| **rating** / **score** / **grade** | Three scales, never mixed: a turn gets a 1–5 rating, a session gets a 0–100 score, the score maps to a letter grade. | `core/selling_quality.py`, `core/prospect_evaluator.py` |
| **turn** | One salesperson line plus the buyer's reply. 1-indexed in the API. | `core/buyer_session.py` |
| **session** | One practice run, keyed by `session_id`, holding one engine instance. | `backend/routes/_utils.py` |
| **review** / **evaluation** | Review = per-turn replay with reasons. Evaluation = final score and grade. | `core/session_review.py`, `core/prospect_evaluator.py` |
| **adaptation** | Prompt block injected for a user style or override. | `config/adaptations.yaml`, `core/loader.py` |
| **drill** / **quiz** | Practice exercises built from your own turns. | `core/script_drills.py`, `core/quiz.py` |

Role names: the human is the **salesperson** and the AI the **buyer** in prospect mode; the human is the **customer** and the AI the **seller** in seller-bot mode. "Prospect" is only the mode name and the URL prefix.
