import os
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT

# Define paths for various directories
LOGS_DIR = BASE_DIR / "logs"
MODEL_CACHE_DIR = BASE_DIR / "models"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"
SRC_DIR = PROJECT_ROOT / "src"
UTILS_DIR = PROJECT_ROOT / "utils"

HF_HOME = BASE_DIR / "cache" / "huggingface"
os.environ["HF_HOME"] = str(HF_HOME)
HF_HOME.mkdir(parents=True, exist_ok=True)

for directory in [LOGS_DIR, MODEL_CACHE_DIR, TEMPLATES_DIR, STATIC_DIR, DATA_DIR, HF_HOME]:
    directory.mkdir(exist_ok=True)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
