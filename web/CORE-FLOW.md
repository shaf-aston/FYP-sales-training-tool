# Eloquence web app: core flow

**What it does:** the Eloquence app (sales roleplay in buy mode and sell mode), built in Next.js and served by Flask at `/`. Terms: [GLOSSARY](../GLOSSARY.md).

## Run it
```bash
# 1. backend (repo root): serves the API and the built app
python backend/app.py                 # http://localhost:5000/
# 2. frontend (web/)
npm install
npm run dev                           # http://localhost:3000/  (proxies /api to Flask)
npm run build                         # static export to web/out, which Flask serves at /  (commit web/out after building)
npm run check                         # types + lint + the three logic checks
```

## Core flow
1. **Page opens**: `/` is the landing page (`src/features/landing/`, copy in `content.ts`); `/buy/` (`src/app/buy/page.tsx`) and `/sell/` (`src/app/sell/page.tsx`) render `AppShell` with `mode="buy"` or `mode="sell"`, which stacks the providers and lays out panels (`src/features/shell/AppShell.tsx`). Why: one place decides layout.
2. **Connect**: in buy mode `SessionProvider` restores the saved session or starts a new one; in sell mode it waits for the buyer setup (`src/features/session/SessionContext.tsx`). Why: the one owner of conversation state.
3. **Talk to the server**: every request goes through `api.*` (`src/lib/api/client.ts`). Why: one swappable seam; nothing else calls `fetch`.
4. **Type or speak**: the message box text lives in `DraftContext` (`src/state/DraftContext.tsx`); voice writes into it (`src/features/voice/`). Why: keyboard and mic share one draft.
5. **Send**: `send()` adds the message at once, calls the API, rolls back on failure, and drops replies from a conversation that was replaced. Why: feels instant, never shows the wrong reply.
6. **Show progress**: the sidebar's stage card (buy mode), the coach panel and the sidebar's Buyer tab (sell mode: `BuyerTab` shows the setup form, then `BuyerProfile` with a folded "New buyer" form; the form picks a buyer or builds one from a real call, `src/features/calls/`) read the same store (`src/features/sidebar`, `coach`, `sell`). Why: one source of truth.
7. **Learn after**: evaluation, "Walk it back", quiz and drills (`src/features/sell`, `quiz`), and Skill Radar (`src/features/skills`: every evaluation is recorded by `useEvaluation` into `skillStore`). Why: turn a session into something to learn from, and show progress across sessions.
8. **Keep it (optional)**: `AccountProvider` asks `/api/account/me` once; the ⋯ menu opens `AccountDialog` (log in or sign up, team, your data). While logged in, `useSkillSync` sends the device's skill log up, takes the account's log back, then sends each new scored session; "From a real call" lists saved prospects (`src/features/account/`, `calls/SavedProspects.tsx`). Why: everything works logged out; an account only keeps progress across devices.

## Web-only words
Shared terms (modes, stage, readiness, coach notes...) are in [GLOSSARY](../GLOSSARY.md). Only the web has these:
- **historyIndex**: a message's position in the server's history; edits use it.
- **epoch**: counter bumped when the conversation is replaced; late replies with an old epoch are ignored.
- **sellSession**: the live AI buyer in sell mode, set up in `BuyerSetup` inside the sidebar's Buyer tab.
- **evalStore**: one shared evaluation result, read by the profile, the inline card and the dialogs.
- **skillStore**: every scored session's skill scores on this device (`skillLog.v1`), read by Skill Radar; replaced by the account's log after login. Pure maths in `skillLog.ts` and `radar.ts`, each with a `.check.ts`.
- **tokens**: every colour, size and timing, defined once in `src/styles/tokens.css`.
- **ui kit**: shared components in `src/components/ui` (Button, Dialog, Notice...).
- **config**: every tunable number and storage key, in `src/lib/config.ts`.
