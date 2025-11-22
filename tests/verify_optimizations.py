"""
Quick verification script to test all optimizations
"""
import sys
import time
import requests
import json

def test_backend_alive():
    """Test if backend is running"""
    print("\n🔍 Testing backend connection...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is alive!")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend not reachable: {e}")
        print("💡 Start backend with: uvicorn src.main:app --reload --port 8000")
        return False

def test_chat_endpoint_speed():
    """Test /api/chat endpoint and measure response time"""
    print("\n⚡ Testing /api/chat endpoint speed...")
    
    test_message = {
        "message": "Hello, how are you?",
        "user_id": "speed_test_user"
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            "http://localhost:8000/api/chat",
            json=test_message,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat endpoint working!")
            print(f"⏱️  Response time: {elapsed_time:.2f} seconds")
            
            if elapsed_time < 10:
                print(f"🎉 EXCELLENT! Response under 10 seconds (optimization working!)")
            elif elapsed_time < 15:
                print(f"✅ GOOD! Response under 15 seconds (better than before)")
            else:
                print(f"⚠️  Response still slow (>15s) - may need further optimization")
            
            print(f"📝 Response preview: {data.get('response', '')[:100]}...")
            return True
        else:
            print(f"❌ Chat endpoint returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after 30 seconds")
        print("⚠️  AI model may still be too slow")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_model_config():
    """Test model configuration"""
    print("\n🔧 Testing model configuration...")
    try:
        from config.model_config import get_active_model_config, get_training_config
        
        active_config = get_active_model_config()
        training_config = get_training_config()
        
        print(f"✅ Model config loaded successfully!")
        print(f"📊 Active Model: {active_config['model_type'].upper()}")
        print(f"📁 Model Path: {active_config['model_path']}")
        print(f"⚙️  max_new_tokens: {active_config['generation_config']['max_new_tokens']}")
        print(f"🎓 Training Pipeline: {'ENABLED' if training_config['enabled'] else 'DISABLED'}")
        
        return True
    except Exception as e:
        print(f"❌ Model config error: {e}")
        return False

def test_frontend_endpoint():
    """Test if frontend can reach backend"""
    print("\n🌐 Testing frontend endpoint compatibility...")
    
    test_message = {
        "message": "Test from frontend",
        "user_id": "frontend_test",
        "session_id": "test_session"
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/chat",
            json=test_message,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Frontend-compatible endpoint working!")
            return True
        else:
            print(f"❌ Endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Endpoint test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 OPTIMIZATION VERIFICATION TEST")
    print("=" * 60)
    
    results = {
        "Backend Alive": test_backend_alive(),
        "Model Config": test_model_config(),
        "Chat Endpoint Speed": False,
        "Frontend Compatibility": False
    }
    
    if results["Backend Alive"]:
        results["Chat Endpoint Speed"] = test_chat_endpoint_speed()
        results["Frontend Compatibility"] = test_frontend_endpoint()
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Optimizations working correctly!")
    else:
        print("⚠️  Some tests failed. Check output above for details.")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
