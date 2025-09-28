# Project path utilities
import os
import sys
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Other important paths
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCKER_DIR = PROJECT_ROOT / "docker"
MODEL_CACHE_DIR = PROJECT_ROOT / "model_cache"
UTILS_DIR = PROJECT_ROOT / "utils"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# Ensure directories exist
for directory in [LOGS_DIR, MODEL_CACHE_DIR, TEMPLATES_DIR, STATIC_DIR]:
    directory.mkdir(exist_ok=True)

# Add src directory to Python path for imports
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
