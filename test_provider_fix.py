import sys
import os
sys.path.insert(0, os.path.abspath('src'))
from chatbot.providers import create_provider

try:
    p = create_provider()
    print(f"Provider created: {type(p).__name__}")
except Exception as e:
    print(f"Error: {e}")
