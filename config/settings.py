"""
Shim so imports like `from config.settings import ...` work when code lives in src.config.settings
"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src_path = root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Re-export everything from the real settings
from src.config.settings import *  # noqa: F401,F403