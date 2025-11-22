"""
Application configuration settings
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch BASE_MODEL from environment variables
from .model_config import BASE_MODEL  # Corrected relative import
from .paths import PROJECT_ROOT, SRC_DIR, UTILS_DIR, LOGS_DIR, MODEL_CACHE_DIR, TEMPLATES_DIR, STATIC_DIR, DATA_DIR

SESSIONS_DB_PATH = Path(os.environ.get("SESSIONS_DB_PATH", str(DATA_DIR / "sessions.db")))
QUALITY_DB_PATH = Path(os.environ.get("QUALITY_DB_PATH", str(DATA_DIR / "quality_metrics.db")))

DEFAULT_MODEL = BASE_MODEL
MAX_CONTEXT_LENGTH = 4

ENABLE_4BIT = os.environ.get("ENABLE_4BIT", "0") == "1" 
ENABLE_ACCELERATE = os.environ.get("ENABLE_ACCELERATE", "0") == "1" 
ENABLE_OPTIMUM = os.environ.get("ENABLE_OPTIMUM", "1") == "1" 

APP_TITLE = "AI Sales Training Chatbot"
APP_VERSION = "2.0.0"
HOST = "0.0.0.0"
PORT = 8000

CORS_ORIGINS = [
  "http://localhost:3000",
  "http://localhost:5173",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173"
]

# STT/TTS Settings
ENABLE_TTS = os.environ.get("ENABLE_TTS", "1") == "1"
ENABLE_STT = os.environ.get("ENABLE_STT", "1") == "1"
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
DEFAULT_CONVERSATION_LIMIT = 10

PERFORMANCE_STATS = {
  "total_requests": 0,
  "ai_generations": 0,
  "total_response_time": 0.0,
  "total_ai_time": 0.0,
  "average_response_time": 0.0,
  "average_ai_time": 0.0,
  "last_request_time": None,
  "startup_time": 0,
  "ai_failures": 0
}