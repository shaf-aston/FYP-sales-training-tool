#!/usr/bin/env python3
"""
Test script to validate core functionality preservation
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("Testing basic functionality preservation...")
print("=" * 60)

# Test 1: Basic imports
print("\n1. Testing basic imports...")
try:
    from src.services.voice_services.stt_service import EnhancedSTTService
    from src.services.voice_services.tts_service import EnhancedTTSService
    from src.services.voice_services.voice_service import EnhancedVoiceService
    print("[PASS] Core voice services can be imported")
except Exception as e:
    print(f"[FAIL] Core import failed: {e}")

# Test 2: Legacy compatibility 
print("\n2. Testing legacy compatibility...")
try:
    from src.services.voice_services import get_voice_service
    from src.services.voice_services.voice_config import VoiceEmotion
    print("[PASS] Legacy imports work")
except Exception as e:
    print(f"[FAIL] Legacy import failed: {e}")

# Test 3: Service instantiation
print("\n3. Testing service instantiation...")
try:
    # Test STT service
    stt_service = EnhancedSTTService()
    print("[PASS] STT service can be instantiated")
    
    # Test TTS service
    tts_service = EnhancedTTSService()
    print("[PASS] TTS service can be instantiated")
    
    # Test unified voice service
    voice_service = EnhancedVoiceService()
    print("[PASS] Voice service can be instantiated")
except Exception as e:
    print(f"[FAIL] Service instantiation failed: {e}")

# Test 4: Configuration access
print("\n4. Testing configuration access...")
try:
    from config.config_loader import config
    print(f"[PASS] Config loaded: {config.app.title if hasattr(config, 'app') else 'Basic config'}")
except Exception as e:
    print(f"[FAIL] Config access failed: {e}")

# Test 5: Model management
print("\n5. Testing AI model integration...")
try:
    from src.services.ai_services.model_service import model_service
    model_name = model_service.get_model_name()
    print(f"[PASS] AI model service available: {model_name}")
except Exception as e:
    print(f"[FAIL] AI model integration failed: {e}")

# Test 6: Core functionality methods
print("\n6. Testing core functionality methods...")
try:
    # Create voice service
    voice_service = EnhancedVoiceService()
    
    # Check STT methods
    if hasattr(voice_service, 'speech_to_text'):
        print("[PASS] STT method available")
    else:
        print("[FAIL] STT method missing")
    
    # Check TTS methods
    if hasattr(voice_service, 'text_to_speech'):
        print("[PASS] TTS method available")
    else:
        print("[FAIL] TTS method missing")
    
    # Check confidence scoring
    if hasattr(voice_service, '_generate_confidence_feedback'):
        print("[PASS] Confidence scoring available")
    else:
        print("[FAIL] Confidence scoring missing")
        
    # Check metrics
    if hasattr(voice_service, 'get_service_info'):
        print("[PASS] Metrics collection available")
    else:
        print("[FAIL] Metrics collection missing")

except Exception as e:
    print(f"[FAIL] Functionality check failed: {e}")

# Test 7: Check STT backends and confidence scoring
print("\n7. Testing STT backends and confidence scoring...")
try:
    stt_service = EnhancedSTTService()
    
    # Check available backends
    stats = stt_service.get_stats()
    if 'backend_failures' in stats:
        print("[PASS] Backend failure tracking available")
    else:
        print("[FAIL] Backend failure tracking missing")
    
    # Check confidence calculation
    if hasattr(stt_service, 'transcribe_audio'):
        print("[PASS] Main transcribe method available")
    else:
        print("[FAIL] Main transcribe method missing")
        
    # Check WER calculation
    from src.models.stt.models import STTResult
    dummy_result = STTResult(text="test", confidence=0.8)
    if hasattr(dummy_result, 'calculate_wer'):
        print("[PASS] WER calculation available")
    else:
        print("[FAIL] WER calculation missing")

except Exception as e:
    print(f"[FAIL] STT backend check failed: {e}")

# Test 8: Check TTS quality metrics
print("\n8. Testing TTS quality metrics...")
try:
    tts_service = EnhancedTTSService()
    
    # Check voice profiles
    if hasattr(tts_service, 'VOICE_PROFILES'):
        profiles = list(tts_service.VOICE_PROFILES.keys())
        print(f"[PASS] Voice profiles available: {profiles}")
    else:
        print("[FAIL] Voice profiles missing")
    
    # Check MOS evaluation
    if hasattr(tts_service, 'mos_evaluator'):
        print("[PASS] MOS evaluation available")
    else:
        print("[FAIL] MOS evaluation missing")
        
    # Check format support
    if hasattr(tts_service, 'get_supported_formats'):
        formats = tts_service.get_supported_formats()
        print(f"[PASS] Format support: {formats}")
    else:
        print("[FAIL] Format support missing")

except Exception as e:
    print(f"[FAIL] TTS quality check failed: {e}")

# Test 9: Session management and conversation tracking
print("\n9. Testing session management...")
try:
    from src.services.ai_services.chat_service import ChatService
    chat_service = ChatService()
    
    if hasattr(chat_service, 'active_sessions'):
        print("[PASS] Session management available")
    else:
        print("[FAIL] Session management missing")
    
    if hasattr(chat_service, 'get_langchain_status'):
        print("[PASS] LangChain integration available")
    else:
        print("[FAIL] LangChain integration missing")

except Exception as e:
    print(f"[FAIL] Session management check failed: {e}")

# Test 10: Error handling and fallbacks
print("\n10. Testing error handling...")
try:
    import src.fallback_responses as fallback
    
    if hasattr(fallback, 'get_fallback'):
        print("[PASS] Fallback responses available")
    else:
        print("[FAIL] Fallback responses missing")

except Exception as e:
    print(f"[FAIL] Error handling check failed: {e}")

print("\n" + "=" * 60)
print("Functionality preservation test complete!")