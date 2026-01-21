# Sales Roleplay Chatbot

Web-based conversational sales assistant implementing the IMPACT framework.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set the Groq API key (export or `.env`):
```bash
GROQ_API_KEY=your_api_key_here
```

3. Run the web server from project root:
```bash
python src/web/app.py
```

Open: http://localhost:5000

## Project Structure

```
sales-roleplay-chatbot/
├── src/
│   ├── chatbot/              # Core chatbot logic
│   │   ├── __init__.py
│   │   ├── chatbot.py        # Main chatbot class
│   │   ├── config.py         # Product configurations
│   │   └── strategies/       # Sales strategies
│   │       ├── __init__.py
│   │       ├── base.py       # Base strategy interface
│   │       ├── consultative.py  # IMPACT framework
│   │       └── transactional.py # Fast-pitch strategy
│   └── web/                  # Web interface
│       ├── __init__.py
│       ├── app.py            # Flask application
│       ├── static/           # Static assets
│       │   └── speech.js
│       └── templates/        # HTML templates
│           └── index.html
├── docs/                     # Documentation
│   ├── Project-doc.md        # Canonical project report
│   └── other docs...
├── requirements.txt          # Python dependencies
└── .env                      # Environment variables (not in git)
```

## Technologies & Requirements

- Python 3.10+
- Flask for the web UI
- Groq API (Llama family models) — requires `GROQ_API_KEY`
- Optional browser Web Speech API for voice input

## Overview & How to Use

- Purpose: Guides a buyer through five structured stages (IMPACT) using an LLM and a lightweight Flask UI.
- Quick run:
	- Install deps: `pip install -r requirements.txt`
	- Set API key: `GROQ_API_KEY` environment variable
	- Start server: `python src/web/app.py`
	- Open: `http://localhost:5000`

## Test Without Web Interface

```bash
python -m src.chatbot.chatbot
```

## For FYP / Defense

- What you built: Conversational AI sales assistant using LLM-powered dialogue with structured stage management.
- Technical approach: State machine architecture + dynamic prompt engineering, powered via Groq API.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Module not found | `pip install -r requirements.txt` |
| Invalid API key | Check console.groq.com |
| Port 5000 in use | Change port in `src/web/app.py` |
| Weird responses | Adjust temperature in `src/chatbot/chatbot.py` |

## Where to Tweak

- Adjust prompt templates and stage signals in `src/chatbot/chatbot.py`.
- Change server options in `src/web/app.py`.

If you want, I can run a quick sanity import/test of `SalesChatbot` next.
