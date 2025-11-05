"""
Application configuration settings
"""
import os
import sys
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
UTILS_DIR = PROJECT_ROOT / "utils"
LOGS_DIR = PROJECT_ROOT / "logs"
MODEL_CACHE_DIR = PROJECT_ROOT / "model_cache"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"

# Add src directory to Python path for imports
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Database paths (overridable via env)
SESSIONS_DB_PATH = Path(os.environ.get("SESSIONS_DB_PATH", str(DATA_DIR / "sessions.db")))
QUALITY_DB_PATH = Path(os.environ.get("QUALITY_DB_PATH", str(DATA_DIR / "quality_metrics.db")))

# AI Model Configuration
DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
MAX_CONTEXT_LENGTH = 4  # Keep last 4 exchanges per user

# Optimization flags - optimized for CPU performance
ENABLE_4BIT = os.environ.get("ENABLE_4BIT", "0") == "1"  # Disabled by default for CPU
ENABLE_ACCELERATE = os.environ.get("ENABLE_ACCELERATE", "0") == "1"  # Disabled by default
ENABLE_OPTIMUM = os.environ.get("ENABLE_OPTIMUM", "1") == "1"  # Keep this enabled

# FastAPI Configuration
APP_TITLE = "AI Sales Training Chatbot"
APP_VERSION = "2.0.0"
HOST = "0.0.0.0"
PORT = 8000

# CORS Configuration
CORS_ORIGINS = [
  "http://localhost:3000",
  "http://localhost:5173",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173"
]

# Performance tracking initialization
PERFORMANCE_STATS = {
  "total_requests": 0,
  "ai_generations": 0,
  "total_response_time": 0.0,
  "total_ai_time": 0.0,
  "average_response_time": 0.0,
  "average_ai_time": 0.0,
  "last_request_time": None,
  "startup_time": 0,  # Will be set at startup
  "ai_failures": 0
}