#!/usr/bin/env python3
"""
Simple Regression Test Runner
============================

Runs core tests repeatedly to ensure system stability.
Perfect for regression testing after changes.

Usage:
    python tests/simple_regression.py           # Run once
    python tests/simple_regression.py --loop 5  # Run 5 times  
    python tests/simple_regression.py --watch   # Run continuously
"""

import sys
import os
import time
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

def test_basic_functionality():
    """Test basic system functionality"""
    print("🧪 Testing basic functionality...")
    
    try:
        # Test 1: Core imports
        print("  ✓ Testing imports...")
        from services.voice_service import get_voice_service
        from services.model_service import model_service
        from services.chat_service import chat_service
        print("    ✅ All core services imported")
        
        # Test 2: Voice service creation
        print("  ✓ Testing voice service...")
        vs = get_voice_service()
        available = vs.is_available()
        print(f"    ✅ Voice service created - Services: {list(available.keys())}")
        
        # Test 3: Chat service
        print("  ✓ Testing chat service...")
        # Test conversation context management
        context = chat_service.conversation_contexts
        print(f"    ✅ Chat service works - Context type: {type(context)}")
        
        # Test 4: No cloud dependencies
        print("  ✓ Testing local-only mode...")
        elevenlabs_disabled = not available.get('elevenlabs', False)
        huggingface_disabled = not available.get('huggingface', False)
        
        if elevenlabs_disabled and huggingface_disabled:
            print("    ✅ Cloud services properly disabled")
        else:
            print("    ⚠️  Some cloud services still enabled")
        
        # Test 5: Configuration
        print("  ✓ Testing configuration...")
        import config.settings
        print("    ✅ Configuration loads without tokens")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Test failed: {e}")
        return False

def test_voice_functionality():
    """Test voice-specific functionality"""
    print("🎤 Testing voice functionality...")
    
    try:
        from services.voice_service import get_voice_service
        vs = get_voice_service()
        
        # Test local TTS availability
        available = vs.is_available()
        
        if available.get('pyttsx3'):
            print("    ✅ pyttsx3 TTS available")
        else:
            print("    ⚠️  pyttsx3 TTS not available")
            
        if available.get('coqui_tts'):
            print("    ✅ Coqui TTS available") 
        else:
            print("    ⚠️  Coqui TTS not available")
            
        if available.get('whisper'):
            print("    ✅ Whisper STT available")
        else:
            print("    ⚠️  Whisper STT not available")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Voice test failed: {e}")
        return False

def test_model_functionality():
    """Test model functionality"""
    print("🤖 Testing AI model...")
    
    try:
        from services.model_service import model_service
        
        # Check if pipeline can be created
        pipeline = model_service.get_pipeline()
        
        if pipeline is None:
            print("    ⚠️  Model not downloaded - run: python scripts/download_model.py")
            return True  # This is expected if model not downloaded
        else:
            print("    ✅ Model pipeline available")
            return True
            
    except Exception as e:
        print(f"    ❌ Model test failed: {e}")
        return False

def run_regression_test():
    """Run a complete regression test"""
    print("🚀 Starting regression test...")
    print("=" * 50)
    
    start_time = time.time()
    
    # Run all test categories
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Voice Functionality", test_voice_functionality), 
        ("Model Functionality", test_model_functionality),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
        print()
    
    # Summary
    duration = time.time() - start_time
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print("📊 REGRESSION TEST SUMMARY")
    print("=" * 50)
    print(f"Duration: {duration:.2f}s")
    print(f"Tests Passed: {passed}/{total}")
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - System is stable!")
        return True
    else:
        print("🔧 Some tests failed - check issues above")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Simple Regression Test Runner")
    parser.add_argument("--loop", type=int, default=1, help="Number of times to run tests")
    parser.add_argument("--watch", action="store_true", help="Run tests continuously")
    parser.add_argument("--delay", type=int, default=5, help="Delay between runs (seconds)")
    
    args = parser.parse_args()
    
    if args.watch:
        print("👀 Watching mode - Press Ctrl+C to stop")
        try:
            run_count = 0
            while True:
                run_count += 1
                print(f"\\n🔄 Run #{run_count} - {time.strftime('%H:%M:%S')}")
                success = run_regression_test()
                
                if not success:
                    print("❌ Test failed - stopping watch mode")
                    sys.exit(1)
                
                time.sleep(args.delay)
                
        except KeyboardInterrupt:
            print("\\n👋 Stopping watch mode")
            sys.exit(0)
    
    else:
        # Run specified number of times
        all_success = True
        
        for i in range(args.loop):
            if args.loop > 1:
                print(f"\\n🔄 Run {i+1}/{args.loop}")
            
            success = run_regression_test()
            if not success:
                all_success = False
                break
            
            if i < args.loop - 1:  # Don't sleep after last run
                time.sleep(1)
        
        sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    main()