**Project Overview**
- **Purpose:** Build a guided, human-feeling sales conversation assistant that follows the IMPACT framework while using an LLM for natural language understanding and generation.
- **Primary goals:** capture user intent, extract problems/goals/emotions, move through stages (Intent → Logical → Emotional → Pitch), and keep the conversation natural.

**Requirements**
- **Free:** Use Groq + Llama (no paid infra required).
- **Dependencies:** See `requirements.txt` (groq, flask, flask-cors).
- **Runtime:** Python 3.10+ recommended, Windows-friendly.

**Core Components**
- **Brain:** LLM via Groq API (generation + understanding).
- **Memory:** Conversation state and extracted fields in `chatbot.py`.
- **Director:** Stage manager / heuristics inside `chatbot.py` that decide transitions.
- **Interface:** `app.py` (Flask) + `templates/index.html` (web UI).

**Quick Setup — Steps 1–2**

Step 1 — Create a virtual environment
- Windows PowerShell:
```powershell
cd "c:\Users\Shaf\Downloads\Final Year Project pack folder\Sales roleplay chatbot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Step 2 — Install dependencies and get API key
- Install packages in the venv:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
- Get a free Groq API key: https://console.groq.com → Create API Key → paste into the web UI when you run `app.py`.

**Rationale**
Keep documentation minimal so setup and demonstration are frictionless for your FYP: concise instructions map directly to the implemented files (`chatbot.py`, `app.py`, `templates/index.html`) and to the project's goals (structure + natural conversation).

**Requirements Being Met**
- **Free:** Uses Groq's free tier for Llama inference — no paid infra required.
- **Simple:** Minimal codebase (three main source files + static HTML) and single venv setup.
- **Efficient:** Uses a hosted LLM for language understanding so the project avoids building complex NLP pipelines.
- **Effective:** State-machine + prompt templates extract intent, problems, emotions and guide users through the IMPACT stages.

**Tech Stack**
- **Language:** Python 3.10+
- **Backend:** Flask (`app.py`)
- **LLM / Inference:** Groq client (Llama 3.2 via Groq API)
- **Frontend:** Plain HTML/CSS/vanilla JS (`templates/index.html`)
- **Packaging / deps:** `requirements.txt`, virtualenv (`.venv`)

**How the IMPACT formula is used (concise)**
- The code implements four stages: `intent` → `logical` → `emotional` → `pitch`.
- Each stage has a stage-specific system prompt (in `chatbot.py`) that tells the LLM what to ask and what to extract.
- Conversation state holds extracted fields (desired outcome, current strategy, consequences, etc.) used to populate prompts and make decisions.
- Simple heuristics (keyword/signature phrases in assistant responses) trigger stage transitions; this keeps the flow natural while ensuring the script's coverage.

**Architecture Notes**
- The project follows `Single Responsibility Principle` and `modular design`: `chatbot.py` handles conversation logic, `app.py` handles HTTP/UI, and templates handle presentation.
- This results in `high cohesion` within modules and `loose coupling` between frontend, backend, and LLM layer, making changes safe and localised.