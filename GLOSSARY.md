# Glossary

One word per idea, used the same way in code, config, API, UI and docs.
New idea → add it here first, then name things after it. A word in the "never" list at the bottom is a bug.

## People and modes

| Term | Meaning | In code |
|---|---|---|
| **learner** | The human using the app. | never "user", "trainee" in new text |
| **buy mode** | The learner buys. The AI is the **seller** and reads a sales script. | page `/buy/`, API `/api/buy/*`, `backend/routes/buy.py`, `Mode = "buy"` |
| **sell mode** | The learner sells. The AI is the **buyer** and pushes back. | page `/sell/`, API `/api/sell/*`, `backend/routes/sell.py`, `Mode = "sell"` |
| **customer** | The learner in buy mode. | coach prompt label `CUSTOMER` (`config/coach.yaml`) |
| **salesperson** | The learner in sell mode. | "your turn", `rate_turn` |
| **seller** | The AI in buy mode. | `SellerBot` (`core/seller_bot.py`), route variable `seller` |
| **buyer** | The AI in sell mode. | `BuyerSession` (`core/buyer_session.py`), route variable `buyer` |
| **prospect** | The person being sold to, **inside the buy-mode script only** (`config/methods/`, `core/script_engine/`). Never a mode. | `prospect_pronouns`, label `ready:prospect` |

Rule: modes are named for the learner; engines and stores for the AI (`seller_sessions` hold buy-mode sessions).

## Conversation

| Term | Meaning | Owner |
|---|---|---|
| **session** | One practice run, keyed by `session_id`, holding one engine. Sent as the `X-Session-ID` header. | `core/utils.py` `new_session_id`, `backend/security.py` `SessionStore` |
| **turn** | One learner line plus the AI reply. Counted from 1 in the API. | `BuyerState.turn_count`, `CallFlow.user_turn_count` |
| **history** | The full transcript, greeting first. `historyIndex` (web) is a message's place in it. | `CallFlow.conversation_history`, `history_json` |
| **stage** | Where the sale is: intent → logical → emotional → pitch → outcome. `outcome` is the closing stage, not the result. | `core/enums.py` `Stage`, step `ui_stage` |
| **product group** | Picker grouping of sell-mode products: transactional or consultative. | `config/buyer.yaml` `product_groups` |
| **epoch** | Web counter bumped when the conversation is replaced; late replies from the old one are dropped. | `SessionContext.tsx` |

## Sell mode (the AI buyer)

| Term | Meaning | Owner |
|---|---|---|
| **persona** | The buyer's character: name, background, needs. | `config/buyer.yaml` `personas` |
| **pick** | What the learner chose in setup (persona, objection), kept for "play again". | web `BuyerPick` |
| **difficulty / difficulty profile** | easy, medium or hard, and the numbers that make it so (`behaviour`, opening lines, objection bank). | `buyer.yaml` `difficulty_profiles` |
| **readiness** | Buyer's willingness to buy, 0 to 1 (web shows %). Moves each turn; decides the outcome. **Readiness band**: At risk, Warming up, Ready. | `BuyerState.readiness`, `buyer_rules.py` |
| **outcome** | How a sell session ended: `sold`, `walked`, or `active` (not over). | `buyer_rules.end_outcome`, `BuyerState.ended` |
| **patience** | Turns a cold buyer waits before walking (`patience_turns`). | `buyer.yaml` |
| **objection** | Buyer pushback. Sell mode draws from an **objection bank**, paced by `ObjectionPacer`; **real objections** come from recorded calls; a **chosen objection** is one the learner typed in setup. | `buyer_rules.py`, `buyer.yaml` |
| **guardrail** | Check on each AI buyer reply (e.g. no early "yes, I'll buy"). | `core/buyer_guardrails.py` `CheckedReply` |
| **knowledge** | The learner's own product notes, given to the AI buyer as research notes. | `core/knowledge.py`, `config/knowledge_fields.yaml`, page `/knowledge/` |

## Buy mode (the scripted seller)

| Term | Meaning | Owner |
|---|---|---|
| **method** | A call script: ordered steps. | `config/methods/*.yaml`, `method.py` |
| **offer** | What the script sells: price, facts, `about`. | `config/offers/*.yaml` |
| **step** | One scripted line (`say`) with the answers it listens for (`listen`). | `method.py` `Step` |
| **route** | One kind of answer on a step, with where it goes next (`then`). Its **label** names it. `keep: false` → the answer is never saved. | `method.py` `Route` |
| **capture / slot** | A step's saved answer, by name. | `Step.capture` |
| **blank / echo** | `{name}` in a later line is a blank; an `echo` step fills it with the prospect's own words by rule. | `fill.py` |
| **probe / stuck** | Other wording when an answer is unclear; `stuck` is where it goes when probes run out (on an answer step: after `misses` re-asks). | `Step` |
| **shrug / reask / ask meaning** | A **shrug** ("dunno man", "no clue") says nothing: never kept as the answer. The step is asked again: first its probes, then the question alone with a calm **reask** lead ("No rush, even a rough idea helps."), only when the step asks a question and never on top of a sense's own lead (a rephrase). Unclear words about the question ("I want to make money online") get **ask meaning**: "What do you mean by wanting to make money online?", but never about an answer they already gave ("more money" twice: asked another way). After `misses` re-asks the call moves on. | `shrug.py`; `engine.yaml` `filler_words`, `vague_words`, `misses`; `common_sense.yaml` `unclear`, `ask_meaning`; method `reask` |
| **goal levels (ladder)** | Step 01 digs the goal in 3 rungs. **Level 1 / surface**: more money, financial / time / location freedom → asked "What are you hoping to achieve with more money?" in their words (`goal_practical`). **Level 2 / practical**: what it does for them day to day ("not stressed every time I buy something") → `goal_identity`. **Level 3 / identity**: who they become ("proud of myself", "a provider") → 02. An answer already at level 2 or 3 skips the rungs it climbed. | `cat.yaml` steps `01`, `goal_practical`, `goal_identity`; labels `surface`, `practical`, `identity` |
| **interruption / common sense** | Off-script remarks (pause, repeat, "are you a bot") answered in one line. | `config/script/common_sense.yaml` |
| **nudge** | "what's next?", "go on": cut off the end of a reply, or answered with `nudge.reply`. | `common_sense.yaml` |
| **park** | Before the price, an objection is acknowledged and comes back later (`revisit_step`). | `engine.py` `park` |
| **objection matrix** | After the price, an objection enters its branch of the coach's matrix: ordinary script steps shared by every method, whose `exits` point them at the method's own steps. Past `objection_entries` in one call, the follow-up is booked. | `script/objection_matrix.yaml`, `engine.py` `object_to` |
| **ready** | Keen-buyer shortcut that jumps to payment. | method `ready` |
| **fact / uncovered question** | A product question answered from a fact, else one checked AI line from `about`, else `uncovered_fallback`. | `seller.py`, `engine.yaml` |
| **ack** | One checked AI sentence showing their answer was heard. | `engine.yaml` `ack*` |
| **echo budget / moment / quote** | How often their own words are said back: always at a **moment** step (`moment: true`, the goal question), else a short **quote** within the limits in `echo.py`'s docstring. A refused blank → `say_plain`. | `echo.py`, `engine.yaml` `echo_*`, method `moment` |
| **meaning bank / meaning line** | Prewritten lines for what an answer means (family duty, bills, no time, ...), picked by the matcher; said in its own bubble before the next question, each once a call. Shows they were heard without quoting them. | `config/script/meanings.yaml`, `meanings.py` |
| **route min_score** | A floor on a labelled route: a weaker match is no match (the judge is never offered it), so the step's other answer path takes it. | method `listen.<label>.min_score` |
| **tone marks** | `_word_` stress (italics), `==words==` the key thing (soft highlight), `¶` a pause (new bubble after typing dots). One stress a line at most; AI, coach and voice get `plain` text. | `tone.py`, web `lib/tone.ts` |
| **concept / listen call** | What a step is after (its `note`, else its name). On a step that captures an answer and takes any reply, one AI call hears for it: answered → ack; missed → a fresh **probe** for the concept (never one already said), up to `misses` times, then the call moves on without an answer. AI down → the step's own probes or line, as before. | `listen.py`, `engine.yaml` `listen*`, `misses` |
| **verdict / heard as** | What one reply was heard as (nudge, shrug, interruption, objection, question, answer), decided once per turn before anything is said back. Its `heard_as` goes in the turn log. | `verdict.py` `Ear`, `Verdict` |
| **voice** | The only door to the AI: four named calls (listen, ack, answer, judge). Owns the prompts, the checks and the per-turn breaker; tests swap in a fake. | `voice.py` |
| **close call / judge** | Two answers score too close (`margin`, `near_miss`), so an LLM picks the label. | `judge.py` |
| **filler** | A reply that says nothing ("ok"); **filler tags** like "you know?" are not questions. | `engine.yaml` |
| **draft** | Marks a line not taken word for word from the source script. Only these may change. The app ignores the marker. | `config/methods/*.yaml` |

## Feedback to the learner

| Term | Meaning | Owner |
|---|---|---|
| **rating** | 1 to 5, one sell-mode turn. | `core/turn_rating.py` `rate_turn`, `config/turn_rating.yaml` |
| **signal** | A named thing a turn did (open question, mirroring...) with a weight. Only this meaning. | `turn_rating.yaml` `weights` |
| **score** | 0 to 100, one whole session; also most quiz answers (the stage quiz scores 0, partial or 1; the web shows all as %). | `core/sell_evaluator.py`, `core/quiz.py`, web `quiz/scoring.ts` |
| **grade** | Letter from the score. | `sell_evaluator.py`, web `gradeTone` |
| **criterion** | One weighted area of the session score. | `buyer.yaml` `evaluation.criteria` |
| **evaluation** | Final score, grade and outcome. Shown inline, as a modal or in the panel (`evalDisplay`). | `evaluate_sell_session` |
| **review** ("Walk it back") | Turn-by-turn replay with reasons. A **pivotal turn** cost ground. **Redo** retries one. | `core/session_review.py`, `BuyerSession.redo` |
| **hint** | One-line sell-mode tip after a turn. | `buyer_rules.coaching_hint` |
| **coach** | Buy-mode guidance: **coach notes** per step and answers to "Ask the coach" in a **coach style** (tactical, socratic, teacher). Wire key is still `training`. | `core/coach.py`, `config/coach.yaml` |
| **quiz** | Buy mode: name the stage, next move, direction. Sell mode: rewrite one of your turns. | `core/quiz.py`, `config/quiz.yaml` |
| **drill** | A strong line with its key move blanked, brought back on a spaced schedule. | `core/drills.py`, `config/drills.yaml` |

## Plumbing

| Term | Meaning | Owner |
|---|---|---|
| **provider** | One LLM service behind the shared interface. **Router** tries them in order. **LLM profile**: named call settings, `**LLM["buyer_reply"]`. | `core/providers/`, `core/services/provider_router.py`, `config/limits.yaml` |
| **session store** | Live sessions with an idle timeout: `seller_sessions`, `buyer_sessions`. | `backend/security.py` `SessionStore` |
| **rate bucket** | Request limit per route group: `buy_init`, `buy_chat`, `sell`. | `limits.yaml` `rate_limits` |
| **hands-free** | Speak, it sends, the reply is read aloud. | web `handsFree` |
| **tokens** | Every colour, size and timing, once. | `web/src/styles/tokens.css` |

## Naming rules

**Python**
- Files `snake_case.py`, named for what they own: `buyer_*` = sell-mode AI buyer, `seller_*` / `script_engine/` = buy-mode AI seller, `sell_*` = sell-mode services.
- Functions: `load_*` read YAML, `build_*` assemble a result, `rate_*` / `score_*` grade, `_name` private. Classes are nouns (`BuyerState`, `SessionStore`); exceptions say what went wrong (`UnknownPersona`).
- Session variables are named for the AI: `seller` (buy), `buyer` (sell). Ids are `session_id`.
- Constants `UPPER_CASE`, only read from config: tunable numbers come from `config/limits.yaml` via `core/constants.py`.

**Config** (`config/`)
- One file per owner, named like its module: `buyer.yaml` → `buyer_session.py`, `turn_rating.yaml` → `turn_rating.py`, `quiz.yaml` → `quiz.py`, `coach.yaml` → `coach.py`, `drills.yaml` → `drills.py`, `script/engine.yaml` → `script_engine/`.
- Keys `snake_case`. All learner-facing wording and word lists live here, not in code.

**API**
- Path `/api/<mode>/<action>`; JSON keys `snake_case`. The web client names each call mode + action: `buyChat` = `/api/buy/chat`, `sellReview` = `/api/sell/review`.

**Web** (`web/src/`)
- Components `PascalCase.tsx` with `PascalCase.module.css` imported as `s`; hooks `useX`; contexts `XContext.tsx` exporting `XProvider` and `useX`.
- Pure helpers `camelCase.ts`, checked by a sibling `*.check.ts` (`npm run check`).
- Tunables and storage keys in `lib/config.ts`. Renaming a storage key keeps its old string so saved settings survive.

**Tests**: `tests/test_<module>.py`; shared stubs and fixtures live in `tests/conftest.py`.

**Comments**: only where a link is not visible from the line itself (a value that must match another file, a string-keyed lookup, an order that matters). Never restate the code.

## Never use

| Don't say | Say |
|---|---|
| practice (as a page or mode) | buy mode / sell mode |
| prospect (as a mode, or the sell-mode AI) | buyer |
| training, trainer, trainee | coach, learner |
| chatbot, bot (for the engine) | seller / buyer |
| score (for one turn) | rating |
| signal (for a script answer) | label |
| em dash | comma, colon or full stop |
