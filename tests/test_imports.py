#!/usr/bin/env python3
"""
Simple import test to isolate the issue
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("Testing individual imports...")

# Test 1: Basic service imports
print("\n1. Testing enhanced services...")
try:
    from src.services.voice_services.stt_service import EnhancedSTTService
    print("[PASS] EnhancedSTTService imported successfully")
except Exception as e:
    print(f"[FAIL] EnhancedSTTService failed: {e}")

try:
    from src.services.voice_services.tts_service import EnhancedTTSService
    print("[PASS] EnhancedTTSService imported successfully")
except Exception as e:
    print(f"[FAIL] EnhancedTTSService failed: {e}")

try:
    from src.services.voice_services.voice_service import EnhancedVoiceService
    print("[PASS] EnhancedVoiceService imported successfully")
except Exception as e:
    print(f"[FAIL] EnhancedVoiceService failed: {e}")

# Test 2: Test service instantiation
print("\n2. Testing service instantiation...")
try:
    stt_service = EnhancedSTTService()
    print(f"[PASS] STT service created: {type(stt_service)}")
    
    # Test basic methods
    if hasattr(stt_service, 'transcribe_audio'):
        print("[PASS] transcribe_audio method available")
    if hasattr(stt_service, 'get_stats'):
        print("[PASS] get_stats method available") 
    
    stats = stt_service.get_stats()
    print(f"[PASS] Got stats: {list(stats.keys())[:5]}...")
    
except Exception as e:
    print(f"[FAIL] STT service creation failed: {e}")

try:
    tts_service = EnhancedTTSService()
    print(f"[PASS] TTS service created: {type(tts_service)}")
    
    # Test basic methods
    if hasattr(tts_service, 'synthesize_speech'):
        print("[PASS] synthesize_speech method available")
    if hasattr(tts_service, 'get_stats'):
        print("[PASS] get_stats method available")
    
    stats = tts_service.get_stats()
    print(f"[PASS] Got stats: {list(stats.keys())[:5]}...")
    
except Exception as e:
    print(f"[FAIL] TTS service creation failed: {e}")

try:
    voice_service = EnhancedVoiceService()
    print(f"[PASS] Voice service created: {type(voice_service)}")
    
    # Test basic methods
    if hasattr(voice_service, 'speech_to_text'):
        print("[PASS] speech_to_text method available")
    if hasattr(voice_service, 'text_to_speech'):
        print("[PASS] text_to_speech method available")
    
    info = voice_service.get_service_info()
    print(f"[PASS] Got service info: {list(info.keys())[:5]}...")
    
except Exception as e:
    print(f"[FAIL] Voice service creation failed: {e}")

print("\nImport test complete!")