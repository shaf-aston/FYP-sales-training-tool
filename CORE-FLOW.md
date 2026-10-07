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

Modes are named for what the learner does.

| Mode | You are | The AI is | Engine | Page | API | Routes |
|---|---|---|---|---|---|---|
| Sell mode (main) | salesperson | buyer | `core/buyer_session.py` `BuyerSession` | `/sell/` | `/api/sell/*` | `backend/routes/sell.py` |
| Buy mode | customer | seller | `core/seller_bot.py` `SellerBot` | `/buy/` | `/api/buy/*` | `backend/routes/buy.py` |

Shared routes: `backend/routes/knowledge.py` (`/api/knowledge`), `backend/routes/monitoring.py` (`/api/health`, `/api/analytics/*`, `/api/feedback`). Old paths (`/api/init`, `/api/test/*`, `/api/prospect/*` ...) still answer through `backend/routes/old_paths.py` until the deployed web uses the new ones; `/practice/` and `/practice/sell/` redirect to `/buy/` and `/sell/`.

Open the engine for the mode you are working on. Nothing else decides the turn.

## Core flow (sell mode)

| # | Step | File | Why it exists |
|---|---|---|---|
| 1 | Browser posts the salesperson's line | `web/src/lib/api/client.ts` (`/api/sell/chat`) | The one place the UI talks to the API. |
| 2 | Route checks rate limit, message, session | `backend/routes/sell.py` `chat`; `backend/routes/_utils.py` `require_session` / `validate_message` | Transport. Shapes JSON, holds no sales logic. Sessions live in `app.extensions["sessions"]` (`Sessions(seller, buyer)`, named for the AI's side). |
| 3 | Engine runs the turn | `core/buyer_session.py` `BuyerSession.process_turn` (and `redo`, which rolls itself back on failure) | Orchestrates: rate the line, move readiness, pick objection pacing, store history, save. |
| 4 | Pure rules decide | `core/selling_quality.py` (rating), `core/buyer_rules.py` (sold / walked), `core/buyer_prompt.py` (buyer system prompt) | Deterministic. No I/O, no HTTP, easy to test. |
| 5 | Router picks a provider | `core/services/provider_router.py` `chat_with_fallback` | Tries providers in order, falls back on failure. |
| 6 | Provider calls the LLM | `core/providers/factory.py` → `providers/llm/groq.py` behind `providers/base.py` | Swap seam: every provider has the same interface. |
| 7 | Review and analytics | `core/session_review.py` (per-turn replay), `core/sell_evaluator.py` (final score + grade), `core/analytics/session_analytics.py` (events to JSONL) | Everything shown after the session is rebuilt from the saved transcript. |

Buy mode: `buy.py` → `SellerBot.chat` → `core/script_engine/` (scripted lines for the products in `config/selling.yaml`; any other product gets `default_product`. AI only fills small gaps, and every AI sentence goes through `ai_line.py` `checked_line`). `flow.py` keeps the call's history and stage. Coach notes come from the script step; `trainer.py` answers the trainee's questions.

One seller turn (`script_engine/seller.py` `ScriptSeller.reply`; the moves are pure functions in `engine.py`, every word and list in YAML):
1. A reply that says nothing ("ok") is heard as an answer only.
2. `hear_ahead` (not on questions): an answer to a later step given early (a step's `answered_by`, e.g. "I want 5k a month") is kept, and that step is skipped when reached.
3. One recognise pass over interruptions (`script/common_sense.yaml`), product facts, objections and the keen-buyer `ready` examples. Each (except a product fact, never an answer) must beat reading the reply as the step's own answer; `ready` and items with `min_score` must also clear their floor.
4. Keen buyer → `jump` to the method's `ready.then` (open plays and parked worries dropped). Interruption → its reply, then its `after`: ask the step again in the words last used (`asked_line`), wait, rephrase, or (frustration on a step with no other words) `move_on` without saving or acking. Objection → parked before the price, looped after. Fact → its answer.
5. A question that matches none of the step's own answers is an uncovered product question → one AI answer from the offer's `about` and what they told us, checked (no number counting something the facts don't, `answer_banned_words`, no early price, `NOT_COVERED` → `uncovered_fallback`), then the step again.
6. Otherwise the reply answers the step ("yeah makes sense, what's next?" at the temp check too). The "I heard you" line is one checked AI sentence that may link to earlier answers; if the reply also asked something, the AI answer to it takes that place when the facts cover it. A nudge ("what's next?", "go on") is cut off the end of a reply first; a reply that is only a nudge gets `nudge.reply` and the step in other words, or the next step. A `{blank}` from a step marked `echo` takes their own words by rule, no AI ("I want financial freedom" → "...to achieve financial freedom?"; lead-ins in `echo_drop_starts` dropped, too long or verb-first or "my ..." → the plain line). A route with `keep: false` (a vague answer, backing out) is never saved as their answer. Any AI call can fail: the plain script line is said, and the AI rests server-wide only after `ai_fail_limit` failures in a row.

## Config

Every tunable number lives in `config/limits.yaml`; `core/constants.py` is its only reader and refuses zero or negative values at start-up. LLM calls take a named profile from it (`**LLM["buyer_reply"]`), never literal numbers.

`core/loader.py` reads `product_config`, `sell_config` (the AI buyer's personas, difficulty profiles and prompt, and sell-mode scoring). The module that owns a feature reads its own file: `script_engine/` → `selling`, `methods/`, `offers/`, `script/`, `response_guardrails.py` → `guardrails`, `quiz.py` → `quiz_config`, `script_drills.py` → `script_drills`, `selling_quality.py` → `selling_signals`, `knowledge.py` → `knowledge_sanitization`.

Questions: `core/utils.py` `is_question` is the one rule for both modes (word lists from config). Analytics: every event goes through `SessionAnalytics.record`.

Environment: `backend/settings.py` reads app env (origins, debug); `core/providers/config.py` reads LLM keys and models. No other module touches the environment, except `METRICS_JSONL_PATH` in `core/analytics/session_analytics.py`.

## Glossary (the words the code uses)

| Term | Meaning | Owner |
|---|---|---|
| **stage** | Where the conversation is: intent → logical → emotional → pitch → outcome, set by each script step's `ui_stage`. `Stage.OUTCOME` is the closing stage, not the result. | `core/enums.py`, `config/methods/*.yaml` |
| **strategy** | Always consultative in buy mode (the script). Sell mode groups products as transactional or consultative for the picker only. | `core/flow.py`, `backend/routes/sell.py` |
| **signal** | `selling_signals.yaml`: weights for rating the salesperson's language. | `core/selling_quality.py` |
| **readiness** | Buyer's 0–1 willingness to buy. Moves every turn and decides sold or walked. | `core/buyer_session.py`, `core/buyer_rules.py` |
| **outcome** | End result of a sell session: `sold`, `walked`, or none yet. | `core/buyer_rules.py` `end_outcome` |
| **objection** | Buyer pushback. Buy mode: the script's `objections` (loop, normalise, direct). Sell mode: pacing in the buyer rules. | `config/methods/*.yaml`, `core/script_engine/` |
| **rating** / **score** / **grade** | Three scales, never mixed: a turn gets a 1–5 rating, a session gets a 0–100 score, the score maps to a letter grade. | `core/selling_quality.py`, `core/sell_evaluator.py` |
| **turn** | One salesperson line plus the buyer's reply. 1-indexed in the API. | `core/buyer_session.py` |
| **session** | One practice run, keyed by `session_id`, holding one engine instance. | `backend/routes/_utils.py` |
| **review** / **evaluation** | Review = per-turn replay with reasons. Evaluation = final score and grade. | `core/session_review.py`, `core/sell_evaluator.py` |
| **drill** / **quiz** | Practice exercises built from your own turns. | `core/script_drills.py`, `core/quiz.py` |

Role names: modes are named for the learner (**sell mode**: the learner sells; **buy mode**: the learner buys), engines for the AI (`BuyerSession` is the AI buyer, `SellerBot` the AI seller). In sell mode the human is the **salesperson** and the AI the **buyer**; in buy mode the human is the **customer** and the AI the **seller**. "Prospect" in script content means the person being sold to, never a mode.
