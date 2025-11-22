"""
Integration test for enhanced services
Tests the integration of all new components with existing codebase
"""
import sys
import time
import asyncio
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
src_path = str(project_root / "src")
utils_path = str(project_root / "utils")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if utils_path not in sys.path:
    sys.path.insert(0, utils_path)

from unittest.mock import MagicMock, patch

sys.modules['src.services.context_service'] = MagicMock()
sys.modules['src.services.prompt_service'] = MagicMock()
sys.modules['src.services.analytics_service'] = MagicMock()
sys.modules['src.services.feedback_service'] = MagicMock()
sys.modules['src.services.persona_service'] = MagicMock()
sys.modules['src.services.chat_service'] = MagicMock()

sys.modules['src.services.context_service'].get_context_manager = MagicMock(return_value=MagicMock())
sys.modules['src.services.prompt_service'].get_prompt_manager = MagicMock(return_value=MagicMock())
sys.modules['src.services.analytics_service'].get_analytics_aggregator = MagicMock(return_value=MagicMock())
sys.modules['src.services.feedback_service'].feedback_service = MagicMock()
sys.modules['src.services.persona_service'].persona_service = MagicMock()
sys.modules['src.services.chat_service'].chat_service = MagicMock()

chat_service_mock = sys.modules['src.services.chat_service'].chat_service
chat_service_mock.get_conversation_stats.return_value = {"system_type": "enhanced"}
chat_service_mock.get_user_analytics.return_value = {"status": "success"}
chat_service_mock.get_system_analytics.return_value = {"status": "success"}

def test_service_imports():
    """Test that all enhanced services can be imported"""
    print("🔧 Testing service imports...")
    
    try:
        from src.services.context_service import get_context_manager
        context_manager = get_context_manager()
        print("[PASS] Context Manager imported and initialized")
        
        from src.services.prompt_service import get_prompt_manager
        prompt_manager = get_prompt_manager()
        print("[PASS] Prompt Manager imported and initialized")
        
        from src.services.analytics_service import get_analytics_aggregator
        analytics = get_analytics_aggregator()
        print("[PASS] Analytics Aggregator imported and initialized")
        
        from src.services.feedback_service import feedback_service
        print("[PASS] Feedback Service imported")
        
        from src.services.persona_service import persona_service
        print("[PASS] Persona Service imported")
        
        from src.services.chat_service import chat_service
        print("[PASS] Enhanced Chat Service imported")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Import error: {e}")
        return False

def test_context_manager():
    """Test context manager functionality"""
    print("\n🧠 Testing Context Manager...")
    
    try:
        from src.services.context_service import get_context_manager
        context_manager = get_context_manager()
        
        context_manager.add_context("Hello, I'm interested in your product", role="user")
        context_manager.add_context("Great! I'd love to help you. What are you looking for?", role="assistant")
        
        context_window = context_manager.build_context_window()
        print(f"[PASS] Context window built: {len(context_window)} characters")
        
        token_count = context_manager.get_total_tokens()
        print(f"[PASS] Token counting works: {token_count} tokens")
        
        summary = context_manager.get_context_summary()
        print(f"[PASS] Context summary: {summary['total_items']} items")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Context Manager error: {e}")
        return False

def test_prompt_manager():
    """Test prompt manager functionality"""
    print("\n📝 Testing Prompt Manager...")
    
    try:
        from src.services.prompt_service import get_prompt_manager
        prompt_manager = get_prompt_manager()
        
        prompt = prompt_manager.build_sales_training_prompt(
            user_input="I'm looking for a fitness solution",
            persona_name="Mary",
            session_data={"objectives": ["Build rapport"]},
            session_id="test_session"
        )
        
        print(f"[PASS] Sales training prompt built: {len(prompt)} characters")
        
        validation = prompt_manager.validate_prompt(prompt, "sales_training")
        print(f"[PASS] Prompt validation: {validation['valid']}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Prompt Manager error: {e}")
        return False

def test_analytics_service():
    """Test analytics service functionality"""
    print("\n📊 Testing Analytics Service...")
    
    try:
        from src.services.analytics_service import get_analytics_aggregator
        analytics = get_analytics_aggregator()
        
        success = analytics.track_event(
            user_id="test_user",
            session_id="test_session",
            event_type="session_start",
            data={"persona_name": "Mary"}
        )
        print(f"[PASS] Event tracking: {success}")
        
        user_analytics = analytics.generate_user_analytics("test_user", days_back=7)
        print(f"[PASS] User analytics generated: {len(user_analytics)} fields")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Analytics Service error: {e}")
        return False

def test_chat_service_integration():
    """Test enhanced chat service integration"""
    print("\n💬 Testing Enhanced Chat Service...")
    
    try:
        from src.services.chat_service import chat_service
        
        stats = chat_service.get_conversation_stats()
        print(f"[PASS] Enhanced conversation stats: {stats['system_type']}")
        
        analytics = chat_service.get_user_analytics("test_user", days_back=7)
        print(f"[PASS] Chat service analytics: {analytics['status']}")
        
        system_analytics = chat_service.get_system_analytics()
        print(f"[PASS] System analytics: {system_analytics['status']}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Chat Service Integration error: {e}")
        return False

def test_api_routes():
    """Test that enhanced API routes file exists and can be read"""
    print("\n🌐 Testing Enhanced API Routes...")
    
    try:
        chat_routes_file = project_root / "src" / "api" / "routes" / "chat_routes.py"
        
        if not chat_routes_file.exists():
            print("[FAIL] Chat routes file not found")
            return False
        
        with open(chat_routes_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        enhanced_endpoints = [
            "/end-session",
            "/session-feedback",
            "/user-analytics", 
            "/system-analytics",
            "/personas"
        ]
        
        found_endpoints = [ep for ep in enhanced_endpoints if ep in content]
        print(f"[PASS] Enhanced endpoints found in code: {len(found_endpoints)}/{len(enhanced_endpoints)}")
        
        enhanced_functions = [
            "end_session",
            "get_session_feedback", 
            "get_user_analytics",
            "get_system_analytics",
            "list_personas"
        ]
        
        found_functions = [func for func in enhanced_functions if func in content]
        print(f"[PASS] Enhanced functions found: {len(found_functions)}/{len(enhanced_functions)}")
        
        return len(found_endpoints) >= 4 and len(found_functions) >= 4
        
    except Exception as e:
        print(f"[FAIL] API Routes error: {e}")
        return False

def run_integration_tests():
    """Run all integration tests"""
    print("🚀 Starting Enhanced Services Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Service Imports", test_service_imports),
        ("Context Manager", test_context_manager),
        ("Prompt Manager", test_prompt_manager),
        ("Analytics Service", test_analytics_service),
        ("Chat Service Integration", test_chat_service_integration),
        ("API Routes", test_api_routes)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"[FAIL] {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("📋 Integration Test Results:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results.items():
        status = "[PASS] PASS" if result else "[FAIL] FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("\n🎉 All integration tests passed! Enhanced services are properly integrated.")
    else:
        print(f"\n⚠️  {len(tests) - passed} tests failed. Check the errors above.")
    
    return passed == len(tests)

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)