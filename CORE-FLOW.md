# CORE-FLOW

Practise a sales conversation against an AI, then see each turn rated and why.

Run it: see [README](README.md#-run-it). Words: see [GLOSSARY](GLOSSARY.md).

## Two modes, two engines

Modes are named for what the learner does.

| Mode | You are | The AI is | Engine | Page | API | Routes |
|---|---|---|---|---|---|---|
| Sell mode | salesperson | buyer | `core/buyer_session.py` `BuyerSession` | `/sell/` | `/api/sell/*` | `backend/routes/sell.py` |
| Buy mode | customer | seller | `core/seller_bot.py` `SellerBot` | `/buy/` | `/api/buy/*` | `backend/routes/buy.py` |

Shared routes: `backend/routes/knowledge.py` (`/api/knowledge`), `backend/routes/monitoring.py` (`/api/health`, `/api/analytics/*`, `/api/feedback`).

Open the engine for the mode you are working on. Nothing else decides the turn.

## Core flow (sell mode)

| # | Step | File | Why it exists |
|---|---|---|---|
| 1 | Browser posts the salesperson's line | `web/src/lib/api/client.ts` (`/api/sell/chat`) | The one place the UI talks to the API. |
| 2 | Route checks rate limit, session, message | `backend/routes/sell.py` `chat`; `backend/routes/_utils.py` `with_session` / `validate_message` | Transport. Shapes JSON, holds no sales logic. Sessions live in `app.extensions["sessions"]` (`Sessions(seller, buyer)`, two `SessionStore`s named for the AI's side). |
| 3 | Engine runs the turn | `core/buyer_session.py` `BuyerSession.process_turn` (and `redo`, which rolls itself back on failure); setup in `core/sell_service.py`, state in `core/buyer_state.py`, logs and analytics in `core/buyer_record.py` | Orchestrates: rate the line, move readiness, pick objection pacing, store history, save. |
| 4 | Pure rules decide | `core/turn_rating.py` (rating), `core/buyer_rules.py` (sold / walked / coaching hint), `core/buyer_prompt.py` (buyer system prompt), `core/buyer_guardrails.py` (checks each reply) | Deterministic. No I/O, no HTTP, easy to test. |
| 5 | Router picks a provider | `core/services/provider_router.py` `complete` | Tries providers in order, falls back on failure. |
| 6 | Provider calls the LLM | `core/providers/factory.py` → `providers/llm/groq.py` behind `providers/base.py` | Swap seam: every provider has the same interface. |
| 7 | Review and analytics | `core/session_review.py` (per-turn replay), `core/sell_evaluator.py` (final score + grade), `core/analytics/session_analytics.py` (events to JSONL) | Everything shown after the session is rebuilt from the saved transcript. |

Buy mode: `buy.py` → `SellerBot.chat` → `core/script_engine/` (scripted lines for the products in `config/script/engine.yaml`; any other product gets `default_product`. AI only fills small gaps, and every AI sentence goes through `ai_line.py` `checked_line`). `flow.py` `CallFlow` keeps the call's history and stage. Coach notes come from the script step; `coach.py` answers the learner's questions.

One seller turn (`script_engine/seller.py` `ScriptSeller.reply`; the moves are pure functions in `engine.py`, every word and list in YAML):
1. A reply that says nothing ("ok") is heard as an answer only.
2. `hear_ahead` (not on questions): an answer to a later step given early (a step's `answered_by`, e.g. "I want 5k a month") is kept, and that step is skipped when reached.
3. One recognise pass over interruptions (`script/common_sense.yaml`), product facts, objections and the keen-buyer `ready` examples. Each (except a product fact, never an answer) must beat reading the reply as the step's own answer; `ready` and items with `min_score` must also clear their floor.
4. Keen buyer → `jump` to the method's `ready.then` (open plays and parked worries dropped). Interruption → its reply, then its `after`: ask the step again in the words last used (`asked_line`), wait, rephrase, or (frustration on a step with no other words) `move_on` without saving or acking. Objection → parked before the price, looped after. Fact → its answer.
5. A question that matches none of the step's own answers is an uncovered product question → one AI answer from the offer's `about` and what they told us, checked (no number counting something the facts don't, `answer_banned_words`, no early price, `NOT_COVERED` → `uncovered_fallback`), then the step again.
6. Otherwise the reply answers the step ("yeah makes sense, what's next?" at the temp check too). The "I heard you" line is one checked AI sentence that may link to earlier answers; if the reply also asked something, the AI answer to it takes that place when the facts cover it. A nudge ("what's next?", "go on") is cut off the end of a reply first; a reply that is only a nudge gets `nudge.reply` and the step in other words, or the next step. A `{blank}` from a step marked `echo` takes their own words by rule, no AI ("I want financial freedom" → "...to achieve financial freedom?"; lead-ins in `echo_drop_starts` dropped, too long or verb-first or "my ..." → the plain line). A route with `keep: false` (a vague answer, backing out) is never saved as their answer. Any AI call can fail: the plain script line is said, and the AI rests server-wide only after `ai_fail_limit` failures in a row.

## Config

Every tunable number lives in `config/limits.yaml` (also the security headers and env-var defaults); `core/constants.py` is its only reader and refuses zero or negative values at start-up. LLM calls take a named profile from it (`**LLM["buyer_reply"]`), never literal numbers. Error text for the API lives in `backend/messages.py`.

Each module reads its own file, named like it: `buyer_session.py` / `buyer_prompt.py` / `sell_evaluator.py` → `buyer.yaml` (personas, difficulty profiles, prompt, `evaluation:`), `buyer_products.yaml`, `buyer_guardrails.py` → `buyer_guardrails.yaml`, `turn_rating.py` → `turn_rating.yaml`, `script_engine/` → `script/engine.yaml`, `methods/`, `offers/`, `script/common_sense.yaml`, `coach.py` → `coach.yaml`, `quiz.py` → `quiz.yaml`, `drills.py` → `drills.yaml`, `knowledge.py` → `knowledge_fields.yaml`. All go through `core/loader.py` `load_yaml` (cached, returns a copy).

Questions: `core/utils.py` `is_question` decides if a buy-mode reply asks something; sell-mode turn rules keep their own lists in `turn_rating.yaml`. Analytics: every event goes through `SessionAnalytics.record`, with `mode: buy | sell`.

Environment: `core/env.py` is the only module that touches the environment (and loads `.env`); its defaults live in `config/limits.yaml`.

## Words

Every term, and the naming rules, live in [GLOSSARY.md](GLOSSARY.md).
