# Sales Chatbot - IMPACT Framework

## Quick Start (3 Steps)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Free API Key
- Go to https://console.groq.com
- Sign up (free, no credit card)
- Create API key
- Copy it

### 3. Run
```bash
python app.py
```

Open browser: http://localhost:5000

---

## Project Structure
```
sales-chatbot/
├── chatbot.py           # Core logic (IMPACT stages)
├── app.py               # Flask web server
├── requirements.txt     # Dependencies
├── README.md           # This file
└── templates/
    └── index.html      # Chat interface
```

---

## Technologies & Requirements

- **Python:** 3.12+ recommended (create a virtualenv).
- **Core libraries:** Flask for the web UI; other deps in `requirements.txt`.
- **LLM & API:** Groq API (Llama 3.2 via Groq) — requires a Groq API key.
- **Speech (optional):** Vosk offline model included for local ASR.
- **Frontend:** Simple HTML/JS in `templates/` and `static/` for the chat UI.
- **Install:** `pip install -r requirements.txt` and set the Groq API key.
 
## Overview & How to Use (high level)

- **Purpose:** A conversational sales assistant that guides a buyer through four structured stages (IMPACT) using an LLM and a lightweight Flask UI.
- **Quick run:**
    - Install deps: `pip install -r requirements.txt`
    - Set API key: `GROQ_API_KEY` environment variable
    - Start server: `python app.py`
    - Open: `http://localhost:5000`
- **What each part does (high level):**
    - `app.py` — runs the Flask server, serves the UI, and forwards user messages to the bot logic.
    - `chatbot.py` — core logic: builds prompts, manages conversation history, and implements the IMPACT state machine (Intent → Logical → Emotional → Pitch).
    - `templates/` & `static/` — frontend UI and client-side scripts (chat interface and optional audio in `static/speech.js`).
    - Offline server-side Vosk support has been removed from this copy to save space; the browser-side Web Speech API (`static/speech.js`) still provides voice input when supported by the browser.
- **Conversation flow (simple):**
    1. User sends a message from the browser to `app.py`.
    2. `chatbot.py` appends to history, selects the current IMPACT stage, and builds a prompt.
    3. LLM (Groq) returns a response; `chatbot.py` inspects the reply to decide whether to advance stages or ask a follow-up.
    4. Response returned to the browser and displayed in the chat UI.
- **Where to tweak behavior:** adjust temperature and prompt templates in `chatbot.py`; change the server port in `app.py`.
- **Notes:** This is intentionally high-level. Tell me which part you want expanded (e.g., prompt templates, state transitions, or deploy steps).

## Test Without Web Interface
```bash
python chatbot.py
```

---

## How It Works

**State Machine with 4 Stages:**
1. **Intent** - What do they want?
2. **Logical** - What's their current approach?
3. **Emotional** - Why now? What if they don't fix it?
4. **Pitch** - Commit to change

**Stage transitions triggered by AI response signals:**
- Intent → "got it, that makes sense..."
- Logical → "ok, I see the issue..."
- Emotional → "that's a powerful reason..."


---

## For FYP Defense

**What you built:**
"Conversational AI sales assistant using LLM-powered dialogue with structured stage management."

**Technical approach:**
"State machine architecture with dynamic prompt engineering, conversation history management, and heuristic-based stage transitions, powered by Llama 3.2 via Groq API."

**Innovation:**
"Combines structured sales methodology with natural language generation, eliminating rigid form-based interactions while maintaining systematic information extraction."

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Module not found | `pip install -r requirements.txt` |
| Invalid API key | Check console.groq.com |
| Port 5000 in use | Change to 5001 in app.py |
| Weird responses | Adjust temperature in chatbot.py |
