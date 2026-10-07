# Eloquence web app: core flow

**What it does:** the practice screen for Eloquence (sales roleplay with an AI buyer and a live coach), built in Next.js and served by Flask at `/`.

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
6. **Show progress**: sidebar stage tracker, coach panel and buyer panel read the same store (`src/features/sidebar`, `coach`, `sell`). Why: one source of truth.
7. **Learn after**: evaluation, "Walk it back", quiz and drills (`src/features/sell`, `quiz`). Why: turn a session into practice.

## Glossary (words the code uses)
- **mode**: what the learner does, `"buy" | "sell"` (`Mode` in `SessionContext.tsx`). Each has its own page.
- **buy mode** (`/buy/`, `/api/buy/*`): you are the customer; the AI seller sells to you.
- **sell mode** (`/sell/`, `/api/sell/*`): you are the salesperson; the AI buyer answers (`sellSession`, set up in `BuyerSetup`).
- **old addresses**: `/practice/` and `/practice/sell/` redirect to `/buy/` and `/sell/` (`public/vercel.json`).
- **stage / strategy**: where the sale is, and which approach (`labels.ts`).
- **training**: the coach's notes after each reply.
- **readiness**: how close the buyer is to buying (0–1).
- **historyIndex**: a message's position in the server's history; edits use it.
- **epoch**: counter bumped when the conversation is replaced; late replies with an old epoch are ignored.
- **tokens**: every colour, size and timing, defined once in `src/styles/tokens.css`.
- **ui kit**: shared components in `src/components/ui` (Button, Dialog, Notice…).
- **config**: every tunable number and storage key, in `src/lib/config.ts`.
