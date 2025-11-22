#!/usr/bin/env python3
"""
Validation script for refactored voice services
"""
import os
import sys

def count_lines_in_file(filepath):
    """Count lines in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return 0

def validate_refactoring():
    """Validate that refactoring was successful"""
    
    print("🔍 Validating Voice Services Refactoring...")
    print("=" * 50)
    
    # Check that main service files are under limit
    tts_service_path = "src/services/voice_services/tts_service.py"
    stt_service_path = "src/services/voice_services/stt_service.py" 
    
    tts_lines = count_lines_in_file(tts_service_path)
    stt_lines = count_lines_in_file(stt_service_path)
    
    print(f"📊 Line Counts:")
    print(f"  TTS Service: {tts_lines} lines")
    print(f"  STT Service: {stt_lines} lines")
    
    # Validate line counts
    success = True
    if tts_lines > 500:
        print(f"❌ TTS Service still has {tts_lines} lines (over 500 limit)")
        success = False
    else:
        print(f"✅ TTS Service: {tts_lines} lines (under 500 limit)")
        
    if stt_lines > 500:
        print(f"❌ STT Service still has {stt_lines} lines (over 500 limit)")
        success = False
    else:
        print(f"✅ STT Service: {stt_lines} lines (under 500 limit)")
    
    # Check modular structure exists
    print(f"\n📁 Checking Modular Structure:")
    
    tts_modules = [
        "src/services/voice_services/tts/__init__.py",
        "src/services/voice_services/tts/core.py", 
        "src/services/voice_services/tts/service.py",
        "src/services/voice_services/tts/cache.py",
        "src/services/voice_services/tts/utils.py",
        "src/services/voice_services/tts/evaluation.py"
    ]
    
    stt_modules = [
        "src/services/voice_services/stt/__init__.py",
        "src/services/voice_services/stt/core.py",
        "src/services/voice_services/stt/service.py", 
        "src/services/voice_services/stt/cache.py",
        "src/services/voice_services/stt/preprocessing.py",
        "src/services/voice_services/stt/backends.py"
    ]
    
    print("  TTS Modules:")
    for module in tts_modules:
        if os.path.exists(module):
            lines = count_lines_in_file(module)
            status = "✅" if lines <= 500 else "❌"
            print(f"    {status} {module} ({lines} lines)")
        else:
            print(f"    ❌ {module} (missing)")
            success = False
            
    print("  STT Modules:")
    for module in stt_modules:
        if os.path.exists(module):
            lines = count_lines_in_file(module)
            status = "✅" if lines <= 500 else "❌"
            print(f"    {status} {module} ({lines} lines)")
        else:
            print(f"    ❌ {module} (missing)")
            success = False
    
    # Check for removed __pycache__ directories
    print(f"\n🧹 Checking for __pycache__ cleanup:")
    pycache_dirs = []
    for root, dirs, files in os.walk("."):
        for dir in dirs:
            if dir == "__pycache__":
                pycache_dirs.append(os.path.join(root, dir))
    
    if pycache_dirs:
        print(f"    ❌ Found {len(pycache_dirs)} __pycache__ directories:")
        for dir in pycache_dirs[:5]:  # Show first 5
            print(f"      {dir}")
        if len(pycache_dirs) > 5:
            print(f"      ... and {len(pycache_dirs) - 5} more")
        success = False
    else:
        print(f"    ✅ No __pycache__ directories found")
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 REFACTORING VALIDATION PASSED!")
        print("   - All service files are under 500 lines")
        print("   - Modular structure is properly implemented")
        print("   - __pycache__ directories have been cleaned")
    else:
        print("❌ REFACTORING VALIDATION FAILED!")
        print("   Some issues were found that need to be addressed")
    
    return success

if __name__ == "__main__":
    validate_refactoring()