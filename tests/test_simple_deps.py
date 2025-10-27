#!/usr/bin/env python3
"""
Simple dependency checker - Windows compatible
"""

import sys
import os
import importlib
from pathlib import Path

def check_package(package_name, display_name):
    """Check if a package is available"""
    try:
        module = importlib.import_module(package_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"[OK] {display_name}: {version}")
        return True
    except ImportError:
        print(f"[MISSING] {display_name}: Not available")
        return False

def main():
    """Run simple dependency check"""
    print("Sales Roleplay Chatbot - Dependency Check")
    print("=" * 50)
    
    # Core dependencies
    print("\nCore Dependencies:")
    core_deps = [
        ("torch", "PyTorch"),
        ("transformers", "Transformers"),
        ("fastapi", "FastAPI"),
        ("numpy", "NumPy"),
        ("pydantic", "Pydantic")
    ]
    
    core_available = 0
    for package, display in core_deps:
        if check_package(package, display):
            core_available += 1
    
    # Optional dependencies
    print("\nOptional Dependencies:")
    opt_deps = [
        ("accelerate", "Accelerate"),
        ("bitsandbytes", "BitsAndBytes"),
        ("optimum", "Optimum"),
        ("whisper", "Whisper"),
        ("librosa", "Librosa"),
        ("scipy", "SciPy")
    ]
    
    opt_available = 0
    for package, display in opt_deps:
        if check_package(package, display):
            opt_available += 1
    
    # Special check for Coqui TTS
    print("\nVoice Dependencies:")
    try:
        from TTS.api import TTS
        print("[OK] Coqui TTS: Available")
        tts_available = True
    except ImportError:
        print("[MISSING] Coqui TTS: Not available")
        tts_available = False
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Core Dependencies: {core_available}/{len(core_deps)}")
    print(f"Optional Dependencies: {opt_available}/{len(opt_deps)}")
    print(f"TTS Available: {'Yes' if tts_available else 'No'}")
    
    if core_available == len(core_deps):
        print("\nStatus: READY - All core dependencies available")
        if opt_available >= len(opt_deps) // 2:
            print("Bonus: Good optional dependency coverage")
        return True
    else:
        print("\nStatus: NEEDS SETUP - Missing core dependencies")
        print("Run: pip install -r requirements.txt")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)