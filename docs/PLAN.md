# What's left: step-by-step plan

Status on 12 Nov 2026: all 10 roadmap steps are built, and 57 of 66 sub-steps are done (`docs/roadmap.html`).
This plan covers everything still open, in build order. Done items are marked **✓ done** with where they landed.

Each item lists **why**, **steps**, **files**, **done when** and **needs**.
- **Method:** R = rules, M = our own model (Kaggle), G = Groq. Rules come first; Groq only where new sentences must be written.
- **Needs:** "nothing" means it can be built now; anything else names what is blocking it.

---

## Phase 0: finish step 2 (now) · ✓ done
PR #101 merged after the independent review's fixes; the live check passed (the first question is Maya's, and her
words survive a reload). Step 2's polish item is ticked.

1. **Merge PR #101 (Rep's words).**
   - Fix whatever the independent review confirms, then merge once CI is green.
   - Check it live: buy mode → Tools → Rep's words → sample call → start. The first question should be Maya's.
   - Done when the production `/api/health` shows the merge commit and the live check passes.
2. **Tick the step 2 polish item** on the roadmap. It is the only step 2 sub-step left: "Finish and polish the flow".
   It is covered by 2.1–2.3 below.

## Phase 1: no blockers, highest value first

### 1.1 Sell-mode buyer: rules choose the move (roadmap step 3) · R, then M, then G
**✓ steps 1–5 and 7 done** (`buyer_moves.py`, `buyer_lines.py`, `config/prospect_lines.yaml`): moves are share, guard,
stall, ask and lean in (the objection pacer still adds objections). In the scripted test call, 70%+ of replies come from the
bank with the real model, and a session replays the same way. Step 6 runs on rough bands until the real calls arrive.
**Why:** Groq still writes the middle of every buyer reply. Moving the decision to rules makes replies faster, free,
the same on every run, and easier to tune.

Steps:
1. **Pick the move by rules.**
   - Add `core/sell_mode/buyer_moves.py`: `next_move(state, turn_signals) -> Move`.
   - Moves: object, ask, warm up, stall, agree. The choice comes from readiness, the objection pacer, the turn number and the rep's last line (`turn_rating` signals).
   - The thresholds go in `config/buyer.yaml` `moves`.
2. **Tell Groq the move.** Add the move to the prompt in `buyer_prompt.py`, so Groq only words a reply that is already decided. This is the first visible win, with nothing else replaced yet.
3. **Build a bank of real prospect lines.**
   - Write `config/prospect_lines.yaml` with lines per move × topic (price, time, partner, trust, fit, need).
   - Start with 10–20 lines per cell from the existing objections (`config/real_objections.json`) plus hand-written ones in the house voice.
4. **Choose a line.**
   - Add `core/sell_mode/buyer_lines.py` `pick_line(move, topic, history, embed)`: lines for the move, ranked by meaning against the rep's last line (shared embedder), never repeating within a call.
   - Use the line only if its score is at least a threshold. Otherwise Groq writes it, told the move (G).
5. **Fill the line's blanks** (persona name, their product, their budget) by rules, the way buy mode's `fill.py` does.
6. **Measure realism** by rules: reply length, questions per turn and objection rate. Compare these to the real calls in 3.2. The test asserts each stays within a band.
7. **Roles switch.** The header already has "Switch to selling / buying", so check it and tick the sub-step.

**Files:** `core/sell_mode/buyer_session.py`, `buyer_prompt.py`, new `buyer_moves.py` and `buyer_lines.py`, `config/buyer.yaml`, `tests/test_buyer_*`.

**Done when:**
- Most replies (target 70%+) come from the line bank in a scripted test run.
- The same session replays the same way.
- Sell-mode tests are green, and the latency median falls.

**Needs:**
- Nothing for steps 1–5.
- Step 6 needs the real calls from 3.1 for its reference numbers; rough bands can be used until then.

### 1.2 Platform hardening · R
**✓ 1 (backups), 3 (real IP) and 4 (embedder) done** in PR #102. The VM also had its database file readable by every
user; it is now 0600. 2 needs the Vercel deploy hook; 5 is below.
1. **Database backups.**
   - Nightly `sqlite3 .backup` on the VM with 7 days kept, as a systemd timer installed by `scripts/deploy_vm.sh`.
   - Done when a restore of last night's backup on a copy works.
   - Needs nothing: it goes through the `vm-run` workflow.
2. **Deploy order.**
   - The web (Vercel) can be live before the API (VM). Gate the Vercel deploy on the API by turning off Vercel's git auto-deploy (`vercel.json` `git.deploymentEnabled: false`) and calling a Vercel deploy hook at the end of `deploy.yml`.
   - Needs the user to create a deploy hook in Vercel and save it as the GitHub secret `VERCEL_DEPLOY_HOOK`.
3. **The visitor's real IP behind the proxies.**
   - Rate limits and the login throttle should read the client IP from Caddy's `X-Forwarded-For`, but only when it comes from Caddy (`TRUST_PROXY_HEADERS=1` on the VM).
   - Done when two requests from different IPs hit separate rate buckets.
   - Needs nothing.
4. **Move the shared embedder to `core/infra/embedder.py`.**
   - Buy mode, SOP review and Rep's words all use it; today the routes reach into buy mode for it.
   - Keep the model settings in `script/engine.yaml` until that file is quiet, then move them to `limits.yaml` `embedder`.
   - Needs nothing.
5. **Recordings over 25 MB.** Done.
   - Split them with ffmpeg on the server into 10-minute parts, transcribe each and join them with the times shifted, so speakers are labelled across the whole call (`core/calls/audio_parts.py`; uploads up to 200 MB).
   - Done when a 60-minute MP3 over 25 MB reads: `tests/test_calls_audio_parts.py` makes one and reads it wherever ffmpeg is installed.
   - ffmpeg on the VM: `scripts/install_ffmpeg.sh`, run by every deploy. Until it is there, recordings over 25 MB are refused as before.

### 1.3 Rep's words, round 2 · R
1. **Save a rep's words to the account**, like saved prospects: `library.py` gets a `rep_words` table (migration), with a list, use and delete in the tool.
2. **Team words.** A manager sets the team's words (from their best rep's call or the team SOP), and members' new buy calls use them by default.
3. **Show which lines were someone's words** in the chat: a small "Maya's words" tag on those seller bubbles. The server returns the step per reply.
4. **Probes in their words.** When the source asks a step's question twice in different words, the second becomes that step's probe.

**Done when:** tests are green, and the Playwright journey covers saving and reusing words.

**Needs:** nothing.

### 1.4 Small open items · R
- Accept the Groq voice terms (user, see Phase 5), then confirm read-aloud returns audio (`POST /api/speech` → 200).
- ✓ Stale worktree removed.

## Phase 2: needs the real calls (Fathom export)

**Blocker:** the Fathom vault lives on the user's computer (`../GRWTH OS/vault/raw/fathom`, see `config/buyer.yaml`). Either:
- upload 20–50 call transcripts (text exports) to a private repo folder or a cloud session, or
- serve the folder through Remote Control so a session can read it.

Nothing personal is committed: only derived numbers and anonymised lines.

1. **Calibrate call review** (step 5) on 10–20 real calls.
   - Hand-label each rep turn good / ok / weak.
   - Tune the `turn_rating.yaml` thresholds until agreement is at least 80%, and record the numbers in the yaml comments.
2. **Realism reference for 1.1.6:** reply length, questions per turn and objection rate per real prospect.
3. **Real prospect line bank** for 1.1.3: anonymised prospect lines per move and topic.
4. **Rep's words thresholds re-checked** on real top-rep calls. Today they are measured on written examples.

## Phase 3: our own models (Kaggle) · M

**Blocker:** a Kaggle account with a GPU notebook, plus the labelled data from Phase 2.

Every model is exported small (ONNX or a pickle under 5 MB), runs on the VM CPU, and is opt-in behind config, with rules as the fallback.
1. **Objection classifier** (steps 3, 4, 5).
   - TF-IDF + logistic regression on the labelled Fathom objections, compared with the phrase lists on a held-out 20%.
   - Ship only if F1 is at least 5 points better.
2. **Stage classifier** (steps 2, 5, 9): the same recipe, trained on script lines per stage plus hand-labelled call turns.
3. **Tuned meaning matcher.**
   - Fine-tune bge-small on pairs (script question ↔ how reps say it, from Phase 2 calls).
   - Re-measure the buy-mode hearing tests, SOP adherence and Rep's words; adopt it only if none gets worse.
4. **Speaker separation** for mono recordings: test pyannote on a few labelled recordings, and adopt it only if it runs on the VM in under 2× real time.

## Phase 4: optional Groq extras · G
1. **SOP written critique:** one paragraph from the checklist gaps. The rules decide what is missing; Groq only words it.
2. **Insights in plain English:** a rewrite of the rule-made guidelines, with the original always shown.

Both are off by default, carry an "AI-written" note, and fall back to the rules' text.

## Phase 5: user actions (no code)
1. **Groq console:** accept the terms for `canopylabs/orpheus-v1-english`, so server voice works (now it's the browser voice).
2. **Netlify:** unlink the repo. Its failing checks on PRs are not ours.
3. **Vercel deploy hook** for 1.2.2.
4. **Google login (optional):** an OAuth client ID and secret. Magic links need an email sender (Resend or Postmark API key).
5. **Fathom transcripts** for Phase 2, and **Kaggle** access for Phase 3.

---

## Order of work
1. Phase 0 (today).
2. 1.2.1 backups, then 1.2.3 real IP (small, protects the data).
3. 1.1 steps 1–5 (largest value; one PR per step).
4. 1.3 Rep's words round 2.
5. 1.2.4 embedder move and 1.2.5 long recordings.
6. Phases 2 and 3 as soon as the data and Kaggle access arrive.
7. Phase 4 if wanted.
