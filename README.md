# Eloquence: AI Sales Training Tool

Practise real sales conversations against an AI buyer, then see exactly where the deal was won or lost.

Final-year project. Flask backend, plain JavaScript frontend, LLM-driven roleplay with deterministic scoring.

## What it does

| Mode | You are | The AI is |
|---|---|---|
| **Seller bot** | the customer | a salesperson that follows a staged sales flow |
| **Prospect mode** | the salesperson | a buyer with its own needs, objections and patience |

After a prospect session you get:

- **Turn-by-turn review**: every line rated, with the reason and how buyer readiness moved
- **Pivotal moments**: the turns that decided the outcome
- **Script drills**: strong lines with the key move blanked out, for recall practice
- **Quiz**: identify the stage, the next move and the direction of the conversation

## How it works

- **Stage machine**: conversations move through Intent, Logical, Emotional, Pitch, Objection and Outcome. A stage only advances when the buyer's signals earn it.
- **Buyer profiles**: Easy, Medium and Hard buyers, grounded in published buyer typology research. Readiness, disclosure, objections and patience are all set in config.
- **Deterministic judge**: scoring does not depend on the LLM, so any saved session can be reviewed again with the same result.
- **Provider fallback**: Groq first, SambaNova as backup, so a session survives one provider going down.
- **Config driven**: products, objections, signals and drills live in `config/*.yaml`. No code change needed to add a product.

## Stack

Python, Flask, Groq and SambaNova LLM APIs, YAML config, vanilla JS with browser speech input, pytest.

## Run it

```bash
pip install -r requirements.txt
echo "GROQ_API_KEY=your_key" > .env    # free key: https://console.groq.com/keys
python backend/app.py                  # http://localhost:5000
```

Optional: `SAMBANOVA_API_KEY` for the backup provider.

## Tests

```bash
pytest
```

## Layout

```
backend/   Flask app, routes, security (rate limits, input checks, sessions)
core/      conversation engine, stage machine, buyer, judge, quiz, drills
config/    products, buyer profiles, objections, signals, drills
frontend/  templates and static JS/CSS
tests/     unit and route tests
```
