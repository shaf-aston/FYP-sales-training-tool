from groq import Groq
import os
import sys
from dotenv import load_dotenv

# Load .env into environment (so scripts run from terminal pick up the key)
load_dotenv()

# Use GROQ API key from environment (.env)
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    print("Error: GROQ_API_KEY not set in environment. Set it in your .env or environment variables.")
    sys.exit(1)

client = Groq(api_key=api_key)

try:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "i want to make more money, are you using a sales script?"}],
        max_tokens=20
    )
    print("Model works. Sample output:", resp.choices[0].message.content)
except Exception as e:
    print("Error verifying model:", e)
