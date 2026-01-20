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

## Cost

**Zero.** Groq provides free access to Llama 3.2 with generous limits.

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
