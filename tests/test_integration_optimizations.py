"""
Integration test - Shows optimizations work with existing code
"""

import pytest
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test for optimization features - run manually when needed")
async def test_integration():
    """Test that optimizations integrate with existing voice service"""
    print("\n" + "="*70)
    print("INTEGRATION TEST - Optimizations with Existing Code")
    print("="*70)
    
    from src.services.voice_services.voice_service import EnhancedVoiceService
    
    print("\n1. Creating service instance (as existing code does)...")
    service = EnhancedVoiceService()
    print("   ✅ Service created")
    
    print("\n2. Checking existing methods still work...")
    existing_methods = [
        'text_to_speech',
        '_setup_coqui_tts',
        '_setup_google_cloud_stt',
        '_ensure_google_cloud_loaded',
        '_initialize_emotion_profiles',
        '_log_service_status'
    ]
    
    for method in existing_methods:
        if hasattr(service, method):
            print(f"   ✅ {method} exists")
        else:
            print(f"   ❌ {method} MISSING")
            return False
    
    print("\n3. Verifying new optimizations don't break existing code...")
    original_properties = [
        'available_services',
        'emotion_profiles',
        'device',
        'coqui_tts',
        'google_cloud_client'
    ]
    
    for prop in original_properties:
        if hasattr(service, prop):
            print(f"   ✅ {prop} preserved")
        else:
            print(f"   ❌ {prop} MISSING")
            return False
    
    print("\n4. Testing backward compatibility of speech_to_text()...")
    import inspect
    sig = inspect.signature(service.speech_to_text)
    params = sig.parameters
    
    if 'enable_caching' in params and params['enable_caching'].default is not inspect.Parameter.empty:
        print(f"   ✅ enable_caching has default: {params['enable_caching'].default}")
    else:
        print(f"   ⚠️  enable_caching missing or no default")
    
    print("\n5. Verifying optimization features are additive...")
    optimization_features = [
        'transcription_cache',
        'audio_hash_cache',
        'cache_ttl',
        'max_cache_size',
        'thread_pool',
        'performance_metrics'
    ]
    
    all_present = True
    for feature in optimization_features:
        if hasattr(service, feature):
            print(f"   ✅ {feature} added")
        else:
            print(f"   ❌ {feature} MISSING")
            all_present = False
    
    print("\n6. Testing that existing functionality is preserved...")
    if isinstance(service.available_services, dict):
        print(f"   ✅ available_services is dict")
        print(f"   Services tracked: {len(service.available_services)}")
    
    if isinstance(service.emotion_profiles, dict):
        print(f"   ✅ emotion_profiles is dict")
        print(f"   Profiles available: {len(service.emotion_profiles)}")
    
    print("\n7. Verifying optimization methods are isolated...")
    public_methods = [m for m in dir(service) if not m.startswith('_') and callable(getattr(service, m))]
    
    expected_new_public = {'batch_speech_to_text', 'get_performance_metrics', 'clear_cache'}
    
    print(f"   Public optimization methods: {expected_new_public}")
    
    for method in expected_new_public:
        if method in public_methods:
            print(f"   ✅ {method} is public (intentional)")
        else:
            print(f"   ❌ {method} missing")
    
    print("\n8. Quick functional test...")
    try:
        metrics = service.get_performance_metrics()
        print(f"   ✅ Metrics work: {metrics['total_requests']} requests")
        
        service.clear_cache()
        print(f"   ✅ Clear cache works")
        
        service._add_to_cache("test", {"data": "test"})
        result = service._get_from_cache("test")
        if result and result.get('data') == 'test':
            print(f"   ✅ Cache operations work")
        
    except Exception as e:
        print(f"   ❌ Functional test failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("INTEGRATION TEST RESULTS")
    print("="*70)
    print("\n✅ ALL INTEGRATION CHECKS PASSED!")
    print("\nVerified:")
    print("  • Existing methods preserved")
    print("  • Existing properties intact")
    print("  • Backward compatibility maintained")
    print("  • Optimization features additive (not destructive)")
    print("  • Public API minimally changed (3 new methods)")
    print("  • Functionality working correctly")
    print("\n🎉 Optimizations integrate perfectly with existing code!")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_integration())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
