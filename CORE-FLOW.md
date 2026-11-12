# CORE-FLOW

Practise a sales conversation against an AI, then see each turn rated and why.

Run it: see [README](README.md#-run-it). Words: see [GLOSSARY](GLOSSARY.md).

## Two modes, two engines

Modes are named for what the learner does.

| Mode | You are | The AI is | Engine | Page | API | Routes |
|---|---|---|---|---|---|---|
| Sell mode | salesperson | buyer | `core/sell_mode/buyer_session.py` `BuyerSession` | `/sell/` | `/api/sell/*` | `backend/routes/sell.py` |
| Buy mode | customer | seller | `core/buy_mode/seller_bot.py` `SellerBot` | `/buy/` | `/api/buy/*` | `backend/routes/buy.py` |

Shared routes: `backend/routes/knowledge.py` (`/api/knowledge`), `backend/routes/monitoring.py` (`/api/health`, `/api/feedback`). Open the engine for the mode you are working on. Nothing else decides the turn.

## Where things live

Each folder holds one job; its `__init__.py` says which. Imports point down or into `infra/`, never across modes.

```
core/
  infra/        plumbing, no sales knowledge: env, constants, loader, utils, embedder (the one local meaning model), similarity (meaning match), logs/, providers/ (LLM, speech, router)
  training/     learner tools both modes use: turn_rating, quiz, drills, team_insights (a manager's view)
  sell_mode/    learner sells, AI buys: buyer_*, sell_service, sell_evaluator, session_review, knowledge, real_calls, custom_buyer
  calls/        an uploaded real call, no AI: transcript (parsers), roles (rep / prospect), profile, reader (the one entry)
  accounts/     what is kept for a learner, SQLite: db (file, migrations), passwords, users, teams, library
  sop/          a team's sales SOP, no AI: document (txt/md/docx/pdf), outline, checklist, adherence
  buy_mode/     learner buys, script sells: seller_bot, flow, coach, stage
    script_engine/  seller (one turn), engine (next line), method (load YAML), config (check YAML), rep_words
      hear/     what the reply meant: verdict, recognise, meanings, shrug
      ai/       the only door to the AI: voice, line, gate, checks, judge, listen
      words/    writing lines: fill, echo, tone
backend/        transport: app, routes/, security
```

## Core flow (sell mode)

| # | Step | File | Why it exists |
|---|---|---|---|
| 1 | Browser posts the salesperson's line | `web/src/lib/api/client.ts` (`/api/sell/chat`) | The one place the UI talks to the API. |
| 2 | Route checks rate limit, session, message | `backend/routes/sell.py` `chat`; `backend/routes/_utils.py` `with_session` / `validate_message` | Transport. Shapes JSON, holds no sales logic. Sessions live in `app.extensions["sessions"]` (`Sessions(seller, buyer)`, two `SessionStore`s named for the AI's side). |
| 3 | Engine runs the turn | `core/sell_mode/buyer_session.py` `BuyerSession.process_turn` (and `redo`, which rolls itself back on failure); setup in `core/sell_mode/sell_service.py`, state in `core/sell_mode/buyer_state.py`, logs and analytics in `core/sell_mode/buyer_record.py` | Orchestrates: take readiness from the transcript replay (`session_review.build_review`, the same one the review shows, so live play and review cannot disagree), pick objection pacing, store history, save. |
| 4 | Pure rules decide | `core/training/turn_rating.py` (rating), `core/sell_mode/buyer_rules.py` (sold / walked / coaching hint), `core/sell_mode/buyer_moves.py` (the buyer's move), `core/sell_mode/buyer_lines.py` (a real prospect's line for it), `core/sell_mode/buyer_prompt.py` (buyer system prompt), `core/sell_mode/buyer_guardrails.py` (checks each AI reply) | Deterministic. No I/O, no HTTP, easy to test. The move (share, guard, stall, ask, lean in) comes from readiness, the seller's line and its turn_rating signals (`buyer.yaml` `moves`); a line from `config/prospect_lines.yaml` says it when one fits (filled from the persona, never twice a call, an answer's line close enough in meaning to the question), else the AI words it, told the move. The objection pacer adds the turn's objection after either. Seeded by session and turn, so a replay goes the same way; each turn's `move` and `source` (bank / ai) are logged. |
| 5 | Router picks a provider | `core/infra/providers/router.py` `complete` | Tries providers in order, falls back on failure. |
| 6 | Provider calls the LLM | `core/infra/providers/factory.py` → `providers/llm/groq.py` behind `providers/base.py` | Swap seam: every provider has the same interface. |
| 7 | Review and analytics | `core/sell_mode/session_review.py` (per-turn replay), `core/sell_mode/sell_evaluator.py` (final score + grade), `core/infra/logs/events.py` (events to the log and `data/logs/events/`) | Everything shown after the session is rebuilt from the saved transcript. |

Buy mode: `buy.py` → `SellerBot.chat` → `core/buy_mode/script_engine/` (scripted lines for the products in `config/script/engine.yaml`, listed by `GET /api/buy/products` and picked in the ⋯ menu under "Call type"; `/init` takes the id as `product_type`, any other product gets `default_product`. AI only answers uncovered product questions, acknowledges what they said and judges close calls, and every AI sentence goes through `ai/line.py` `checked_line`). `flow.py` `CallFlow` keeps the call's history and stage. Coach notes come from the script step; `coach.py` answers the learner's questions.

One seller turn (`core/buy_mode/script_engine/seller.py` `ScriptSeller.reply`; every word and list in YAML). Who does what:
`verdict.py` `Ear.hear` decides what the reply was heard as, in the order below, and returns one `Verdict` → `seller.py` answers that verdict → `engine.py` (pure functions) picks the next line → `voice.py` `Voice` is the only door to the AI (listen / ack / answer / judge, every prompt and check, shut for the rest of a turn after one failure). `shrug.py` says whether a reply said nothing and how to ask what they meant. `config.py` checks `engine.yaml` when a seller is built (key types, prompt blanks) and names every problem at once.

Once the call has ended (a step with nowhere to go: paid, or the follow-up booked) every reply gets `ended`.

0. `reply.py` `Reader` reads the reply once, and every rule below reads its parts: cut at `clause_breaks` (punctuation only before a space, so "2.5k" stays whole), a nudge cut off its end ("credit, what's next?"), each part a **hedge** ("idk", by meaning: left out), a **tag** ("you know?"), a **question** (opens like one, or ends in "?" after a question word or helper verb), a **rise** (ends in "?" but states: content when short and of the step's `needs` shape, "dunno, a year?", or right after a hedge, "lol idk, money?"; else a question), or **content**. Content beside a question ("i guess 3 years, what about you?", "nothing, why do you ask?", "two years, and what's the price") keeps the answer and says the question's one line in front of the next question: a fact, a sense marked `with_answer` (small talk, thanks, "is this a bot?"), a worry before the price (parked), or the AI's answer from the facts. The question leads instead (the answer is not kept) after a pause, when the content is itself a worry or sense ("that's a lot mate", "shut up"), says nothing ("fine"), or is no answer to the step, for a worry after the price, `ready`, or a sense about the question itself ("can you say that again"). A fact beside an answer that reaches the price step is left out: that step tells the offer.
1. A reply that says nothing ("ok") is heard as an answer only, unless it reads as `ready` ("yes I'm in").
2. `hear_ahead` (not on questions): an answer to a later step given early (a step's `answered_by`, e.g. "I want 5k a month", or a reply that is only the figure: "five grand a month", "like 5 grand") is kept, and that step is skipped when reached.
3. One recognise pass over interruptions (`script/common_sense.yaml`), product facts, objections and the keen-buyer `ready` examples. Each (except a product fact, never an answer) must beat one bar: how surely the reply is one of the step's own labelled answers, and `interrupt_threshold` too where the other reading has no score of its own (a step that takes any reply, or a plain question, answered as asked); `ready` and items with `min_score` must also clear their floor. A reply without the step's `needs` shape ("I don't have time for this" to "how long?") can't be its answer, so there the catch-all sets no bar. Before the price, an objection scoring just under its floor (from `early_objection_judge_score`) is the AI's call: objection or answer to the question asked; AI down = answer. A shrug in front ("I don't know, enough to live") is left out of this pass: "I don't know" alone reads as "what do you mean?".
4. A shortcut → `jump` to its `then` (parked worries dropped): a keen buyer before the pitch (`ready`), or a reply already about paying from the price to the soft close (`pays`, `like: pay_now`). Interruption → its reply, then its `after`: ask the step again in the words last used (`asked_line`; a second side reply in a row gets other words or moves on, never the same line three times), wait, rephrase, (frustration on a step with no other words) `move_on` without saving or acking, or ("bye") the method's follow-up step. Objection → parked before the price; after it, its matrix branch (`object_to`). Fact → its answer, then the step again; a fact marked `bridge` ("who are you") on a step with a `bridge` question (the very start) asks that getting-to-know-you question instead, hears the reply without saving it (`bridge_ack`), then asks the step. A fact asked a second time before the price gets its short `again` line (else `told_again`), never the same long answer twice.
5. A question that matches none of the step's own answers is an uncovered product question → one AI answer from the offer's `about` and what they told us, checked (no number counting something the facts don't, `answer_banned_words`, no early price, `NOT_COVERED` → `uncovered_fallback`), then the step again.
6. Otherwise the reply answers the step ("yeah makes sense, what's next?" at the temp check too). On a step with labelled answers the embedder picks the route (the AI judges a close call). On a step that captures an answer and takes any reply, one AI **listen call** (`listen.py`) hears for the step's concept (its `note`): answered → its ack line; missed ("k", a dodge) → one fresh checked probe for the concept (one question, no price, no new number, not the same words), asked `misses` times, then the call moves on without saving an answer. AI down or off-format → the step's own probes or line, as before. Otherwise the "I heard you" line is one checked AI sentence that may link to earlier answers; if the reply also asked something, the AI answer to it takes that place when the facts cover it. A nudge ("what's next?", "go on") is cut off the end of a reply first; a reply that is only a nudge gets `nudge.reply` and the step in other words, or the next step. A `{blank}` from a step marked `echo` takes their own words by rule, no AI ("I want financial freedom" → "...to achieve financial freedom?"; lead-ins in `echo_drop_starts` dropped, too long or verb-first or "my ..." → the plain line). A step with `needs` (a regex: the money question needs a figure, the time question a span of time, the goal steps anything but shrugs and figures) hears a reply without it as a miss, asked again then moved on unsaved; a route with `keep: false` needs none. Every step has one **ask budget** (`_limit`): `misses` re-asks for a step that captures an answer, else one per probe; "What do you mean?" (`rephrase`) gets one more, then the call moves on too (by `stuck`, else past the step unsaved), so no question is asked a fourth time. A hedge ("not sure") is not knowing, never "what do you mean?". A step marked `shrug_moves_on` (a rhetorical question its next line answers) moves on after a shrug, never asked again. Call-wide memory keeps it from sounding like a loop: a **lead line** (a `reask` lead, a rephrase reply) is said at most `lead_repeats` times a call, then left out; a step landed on `max_visits` times a call books the `follow_up` instead (going round in circles); and the very same message is never sent twice in a row on a step (it moves on instead). A question that surely picks one of the step's answers on its own is that answer, heard alone ("yeah I'm in, how do I pay?" at the soft close pays), unless the rest takes it back ("no, credit?") or is a worry. "what about you" asks, "?" or not. A step's `plain_if` (a regex) says the plain line when their words match it ("how much each month to make more money?" asks money for money). Once a step's probes run out it is asked in its earlier words in turn (the question, then the probes), never the line just said. A step's own `reask` leads replace the method's ("financial freedom" again at the practical goal is an answer, so not "No rush"). A route with `keep: false` (a vague answer, backing out) is never saved as their answer. Any AI call can fail: the plain script line is said, and the AI rests server-wide only after `ai_fail_limit` failures in a row.
7. How much of their words comes back is the **echo budget** (`echo.py`), no AI: their exact words only on a step marked `moment` (the goal question), else a short term within the limits in its docstring. A line whose blank the budget refuses is said as its `say_plain`. What shows they were heard is then, in order: the step's own ack ("24 months... Damn."); a **meaning line** (`meanings.py`, `script/meanings.yaml`: the matcher reads what the answer means, e.g. "my mum's relying on me" → "So this isn't really about the money.¶It's about ==them==.", each line once a call; also when the step is asked again, in place of a `reask` lead); the AI's "I heard you" line, asked for only when the budget lets it say their words, and dropped if it quotes more than the budget allows; a line already in their words ("What do you mean by ...?", an AI probe) counts as the message's quote; else nothing, just the next question. A route's `min_score` treats a weak match as no match ("my dad got sick" is not a failed attempt).
8. Lines carry **tone marks** (`tone.py`): `_word_` stress (italics), `==words==` the key thing (soft highlight), `¶` a pause (a new bubble after typing dots). At most one stress a line. The AI, the coach and the voice get the words without the marks (`plain`, web `lib/tone.ts` `speakable`).

## Config

Every tunable number lives in `config/limits.yaml` (also the security headers and env-var defaults); `core/infra/constants.py` is its only reader and refuses zero or negative values at start-up. LLM calls take a named profile from it (`**LLM["buyer_reply"]`), never literal numbers. Error text for the API lives in `backend/messages.py`.

Each module reads its own file, named like it: `buyer_session.py` / `buyer_prompt.py` / `sell_evaluator.py` → `buyer.yaml` (personas, difficulty profiles, prompt, `evaluation:`), `buyer_products.yaml`, `buyer_guardrails.py` → `buyer_guardrails.yaml`, `turn_rating.py` → `turn_rating.yaml`, `script_engine/` → `script/engine.yaml`, `methods/`, `offers/`, `script/common_sense.yaml`, `coach.py` → `coach.yaml`, `quiz.py` → `quiz.yaml`, `drills.py` → `drills.yaml`, `knowledge.py` → `knowledge_fields.yaml`. All go through `core/infra/loader.py` `load_yaml` (cached, returns a copy).

Questions: `hear/reply.py` `Reader` decides which parts of a buy-mode reply ask something (`core/infra/utils.py` `opens_question` reads the opening words); sell-mode turn rules keep their own lists in `turn_rating.yaml`. Analytics: every event goes through `SessionAnalytics.record`, with `mode: buy | sell`. Logs: see below.

Environment: `core/infra/env.py` is the only module that touches the environment (and loads `.env`); its defaults live in `config/limits.yaml`.

## Reading a conversation

Every buy-mode turn writes one log line from `core/buy_mode/seller_bot.py`:

`turn 3 | step 08 -> 08 | heard as sense:clarify | user: '...' | bot: '...'`

`heard as` is the path the reply took in `ScriptSeller.reply` (`seller.last_turn`):
`answer:<label>` / `answer:any` / `answer:unclear`, `sense:<name>`, `objection:<name>`, `fact:<name>`,
`ready:prospect`, `question`, `nudge`, `says_nothing`, `misses` (the listen call heard no answer), `hesitates`.
An answer with a question beside it adds what the question was heard as: `answer:any+fact:price`, `answer:unclear+question`.

Try the seller from the terminal (real recogniser, no AI, so plain script lines): `python scripts/chat_cli.py "more money" "to pay bills"`, or `--file replies.txt`.
The same fields go into the `conversation_turn` analytics event. To read a whole call: `python scripts/show_convo.py data/logs/events [session_id]`.

## Logs and timings

`core/infra/logs/` is the one place the app writes down what it did. `store.py` is the only writer: `data/logs/<stream>/<UTC day>.jsonl` (folder: `LOGS_DIR`, default in `limits.yaml`), plus a log line.

| Stream | Made by | Holds |
|---|---|---|
| `events/` | `events.py` `SessionAnalytics.record` | what happened in each chat |
| `timings/` | `timing.py` `span` / `@timed` | how long each step took, nested: request > turn > script step > `llm` call |
| `feedback/` | `feedback.py` `save_feedback` (from `/api/feedback`) | ratings and comments, with their session |

`backend/request_log.py` switches logging on and wraps every `/api` request in the outer span (request id, session id, route, status; `Server-Timing` and `X-Request-ID` headers back to the browser). To time a new step, put `@timed` on it. Read the numbers: `python scripts/timings_report.py data/logs/timings [session_id]`.

## Uploaded calls

A learner pastes or uploads a real call's transcript. `backend/routes/calls.py` hands it to `core/calls/reader.py`
`read_call`, which never calls the AI and never stores anything:

1. `transcript.py` `parse`: cleaned lines (BOM, line endings, `noise` from `calls.yaml`) go through `PARSERS` in order;
   the first layout that finds two or more speakers wins. Turns by one speaker in a row are merged.
2. `roles.py` `assign_roles`: the rep is the speaker the learner names, else the one asking the most questions
   (`sure` only with a clear lead), else the first speaker. The prospect is whoever else talked most.
3. `profile.py` `build_profile`: `calls.yaml` patterns over the prospect's own sentences give background, needs, pains,
   budget (a sum said next to spending words), objections (typed like buyer.yaml concerns), difficulty and
   personality, each with its `evidence`.

`/api/calls/review` replays the call as a sell-mode transcript (`CallReading.history`: rep = learner side) through
`sell_service.review_transcript`, the same review a practice session gets. Practising against the prospect is
`/api/sell/init` with `custom_buyer`: `custom_buyer.py` checks it, the buyer opens with `custom_opening_lines` and raises
the call's objections (`BuyerSession(objection_bank=...)`). With `replay` (the call up to a turning point, ending
with the prospect) the session starts there instead: `BuyerSession.continue_from` settles readiness and counts from
that transcript the same way a rewind does (`_settle`), and the prospect's last line is what the learner answers.

**A recording instead of a transcript**: `/api/calls/transcribe` sends the audio to speech-to-text
(`core/infra/providers/transcribe.py`, Groq Whisper), then `core/calls/audio.py` has the AI label each segment Speaker A
or B (the one AI step in calls) and writes ordinary `[m:ss] Speaker A: ...` lines. The learner checks them and reads
the call like any transcript. Only this route accepts bodies past the 1 MB cap (`transcription.max_upload_bytes`).

**A recording past 25 MB** (Groq's per-file limit, `transcription.max_bytes`): `core/calls/audio_parts.py`
`transcribe_in_parts` copies it into a temporary folder and has ffmpeg (no shell, `split_timeout_seconds`) cut it into
`part_seconds` parts, each re-encoded as mono 16 kHz mp3 at `part_kbps` so it fits the limit. Each part is transcribed,
its segments are shifted by the part's start (ffmpeg's own part list), and the speakers are labelled once over the
joined call, so A and B stay the same people from start to end. The folder is always deleted. A recording at or under
the limit is still one request. Without ffmpeg on the server (`can_split`), the limit is 25 MB as before
(`AUDIO_TOO_BIG`, 413); a file ffmpeg cannot decode is `AUDIO_UNREADABLE` (400).

**Adding a transcript format**: write one parser in `transcript.py` (`(lines, cfg) -> list[Turn] | None`), add it to
`PARSERS` before any looser layout that could claim its text, and add a sample of the real export to
`tests/test_calls_transcript.py`. Junk lines a tool adds go in `calls.yaml` `noise`.

## SOP review

`backend/routes/sop.py` `/read` turns a file (or pasted text) into blocks (`document.py`, one reader per format in
`READERS`), stages and steps (`outline.py`: each top-level heading is a stage, a lone title is skipped), and a
checklist of what a good call covers (`checklist.py`, `config/sop.yaml` `elements`): cues first, meaning only as a
strict fallback. `/check` takes that outline back with a call and says which steps the rep carried out
(`adherence.py`: each step searched for in the rep's lines with bge's query instruction, thresholds in
`sop.yaml`). Meaning comes from the shared embedder (`core/infra/embedder.py`), passed in as `embed`, so `core/sop` imports no mode.

## Rep's words (buy mode)

The rep can ask the script's questions in a top rep's words (a real call) or the team SOP's. `/api/buy/words` takes a
call (read by `core/calls`: the rep's turns) or an SOP outline (from `/api/sop/read`; an instruction such as "Ask what
they want" is said as "What do you want?" by `core/sop/spoken.py`), finds their questions and matches each to the
script step that asks the same thing (`script_engine/rep_words.py`: the shared embedder, one question per step, the
call's own path before the objection talks; below `sure_score` both must ask for the same sort of answer). The web
sends the chosen `{step: question}` to `/api/buy/init` as `words`, and `build_seller` runs the script with those
lines swapped in (`with_words`). Only the wording changes: what each step listens for, where it goes and the checks
around the AI stay the script's. So a step that hears yes or no ("go on" as yes) takes only a yes/no question, and
one that offers choices ("Credit or debit?") only a question that offers them. Only the step's own question changes:
a route's lead into it, its probes and its other wordings when asked again stay the script's. `/init` keeps the
`label` sent with the words ("Maya", "your SOP") and returns it as `words_label`; a restore sends the tab's product,
words and label too, which start a new call when the server no longer has that one. Thresholds in `limits.yaml`
`rep_words`, measured in `tests/test_rep_words.py`.

When the source asks a step's question twice in different words, the second is that step's probe (`Match.probe`,
shown under the match as "Asked again"); the web sends the kept ones as `probes` with `words`, and `with_words` says
them first when the step is asked again. A choice (`{product, label, words, probes}`) can be kept past the tab:
saved to the account (`/api/account/words`, checked against today's script by `seller.checked_words`), or set by a
manager as the team's (`/api/team/words`, members read it in `/api/account/me` `team.words`). The tab's words live in
sessionStorage `buyWords`: someone's words, `"none"` for the script's own (an explicit choice that beats the team's),
or nothing, when a new call takes the team's words for that product (`SessionContext` `wordsFor`; the buy call waits
for the account answer). In the chat, a seller line that contains one of the current words or probes gets a tag
naming whose they are; the web finds them, the server sends nothing extra.

## Accounts

Optional: everything works logged out. `backend/auth.py` owns the login cookie (signed, HttpOnly, SameSite=Lax,
Secure) holding the user id and a session version; logging out bumps the version, so every copy of the cookie stops
working. Routes in `backend/routes/account.py` and `team.py` call the stores in `core/accounts/`, which never import
Flask. `db.py` keeps one SQLite file (`DB_PATH`), a short connection per use (`connect(write=True)` takes the write
lock first, so a check-then-insert cannot race), WAL, and `secure_delete`; a migration is appended to `MIGRATIONS`,
never edited once shipped. Deleting an account deletes everything kept for it and checkpoints the log. A team always
keeps a manager (`teams.keep_a_manager`). Managers get insights (`/api/team/insights`, `.csv`):
`core/training/team_insights.py` turns members' synced skill history into levels (recent averages) and coaching
guidelines, every guideline a sentence from `config/insights.yaml` filled with the numbers that triggered it. Wrong passwords are capped per email (`auth.LoginThrottle`).

## Adding a product or script

New offer → `config/offers/<name>.yaml`; new script → `config/methods/<name>.yaml`; then one line under `products:` in `config/script/engine.yaml` (`<product>: {offer: <name>, method: <name>}`). No code changes.
