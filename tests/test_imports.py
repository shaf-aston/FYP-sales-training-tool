#!/usr/bin/env python3
"""Test script to verify import paths are working correctly."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("Testing imports from utils...")

try:
    from utils.env import setup_model_env
    print("✓ Successfully imported setup_model_env from utils.env")
except ImportError as e:
    print(f"✗ Failed to import from utils.env: {e}")

try:
    from utils.paths import PROJECT_ROOT, LOGS_DIR
    print(f"✓ Successfully imported from utils.paths. Project root: {PROJECT_ROOT}")
    print(f"  Logs directory: {LOGS_DIR}")
except ImportError as e:
    print(f"✗ Failed to import from utils.paths: {e}")

print("\nTesting imports from src...")
try:
    # Add src directory to Python path
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    from fitness_chatbot import app
    print("✓ Successfully imported app from fitness_chatbot")
except ImportError as e:
    print(f"✗ Failed to import from fitness_chatbot: {e}")

print("\nPython path:")
for path in sys.path:
    print(f"- {path}")