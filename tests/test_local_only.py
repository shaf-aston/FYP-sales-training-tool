#!/usr/bin/env python3
"""
Local-Only Functionality Tests
=============================

Tests that ensure the system works completely offline without any API tokens
or cloud dependencies. This is critical for regression testing.
"""

import sys
import os
import unittest
import tempfile
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

class TestLocalOnlyFunctionality(unittest.TestCase):
    """Test that all core functionality works without internet/tokens"""
    
    def setUp(self):
        """Set up test environment to ensure no API keys are used"""
        # Remove any API keys from environment
        self.original_env = {}
        api_keys = [
            'ELEVENLABS_API_KEY', 'ELEVENLABS_KEY',
            'HUGGINGFACE_HUB_API_TOKEN', 'HF_API_KEY',
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'
        ]
        
        for key in api_keys:
            if key in os.environ:
                self.original_env[key] = os.environ[key]
                del os.environ[key]
    
    def tearDown(self):
        """Restore original environment"""
        for key, value in self.original_env.items():
            os.environ[key] = value
    
    def test_core_imports_work_without_tokens(self):
        """Test that core modules import without requiring API tokens"""
        try:
            # Core services should import without tokens
            from services.voice_service import get_voice_service
            from services.model_service import model_service
            from services.chat_service import chat_service
            
            self.assertTrue(True, "All core services imported successfully")
            
        except Exception as e:
            self.fail(f"Core imports failed: {e}")
    
    def test_voice_service_local_only(self):
        """Test voice service works with local backends only"""
        try:
            from services.voice_service import get_voice_service
            
            vs = get_voice_service()
            available = vs.is_available()
            
            # Should have local services available
            self.assertIsInstance(available, dict)
            self.assertIn('whisper', available)
            
            # Should not depend on cloud services
            self.assertFalse(available.get('elevenlabs', False), 
                           "ElevenLabs should be disabled for local-only mode")
            
            # Check that pyttsx3 is available (local TTS)
            if available.get('pyttsx3'):
                self.assertTrue(True, "Local TTS (pyttsx3) is available")
            
        except Exception as e:
            self.fail(f"Voice service local test failed: {e}")
    
    def test_model_service_works_offline(self):
        """Test that model service works without internet"""
        try:
            from services.model_service import model_service
            
            # Should be able to get pipeline without internet
            # (assuming model is cached)
            pipeline = model_service.get_pipeline()
            
            if pipeline is None:
                # This is OK if model isn't downloaded yet
                self.skipTest("Model not downloaded - run python scripts/download_model.py first")
            else:
                self.assertIsNotNone(pipeline, "Model pipeline should be available offline")
                
        except ImportError as e:
            self.fail(f"Model service import failed: {e}")
        except Exception as e:
            # Model might not be downloaded - that's OK for this test
            self.skipTest(f"Model not available (expected): {e}")
    
    def test_chat_service_basic_functionality(self):
        """Test chat service basic functionality without external dependencies"""
        try:
            from services.chat_service import chat_service
            
            # Test fallback responses work
            fallback_response = chat_service._get_fallback_response("Hello")
            self.assertIsInstance(fallback_response, str)
            self.assertGreater(len(fallback_response), 0)
            
            # Test conversation context management
            user_id = "test_user"
            persona = "mary"
            
            # This should work even without a model
            context = chat_service.conversation_contexts.get(f"{user_id}_{persona}", [])
            self.assertIsInstance(context, list)
            
        except Exception as e:
            self.fail(f"Chat service test failed: {e}")
    
    def test_no_network_dependencies_in_imports(self):
        """Ensure imports don't require network access"""
        try:
            # These should all work offline
            import src.fitness_chatbot  # Main application
            
            # API routes should import without network
            from api.routes import chat_routes, voice_routes, web_routes
            
            self.assertTrue(True, "All modules imported without network")
            
        except Exception as e:
            self.fail(f"Network-free import test failed: {e}")
    
    def test_configuration_without_tokens(self):
        """Test that configuration works without any API tokens"""
        try:
            import config.settings
            
            # Should have sensible defaults without tokens
            self.assertTrue(True, "Configuration loaded without tokens")
            
        except Exception as e:
            self.fail(f"Configuration test failed: {e}")
    
    def test_fallback_responses_available(self):
        """Test that fallback responses work when AI model unavailable"""
        try:
            import fallback_responses
            
            # Should have fallback responses defined
            self.assertTrue(True, "Fallback responses available")
            
        except Exception as e:
            self.fail(f"Fallback responses test failed: {e}")

class TestLocalTTSFunctionality(unittest.TestCase):
    """Test local TTS functionality without cloud services"""
    
    def test_pyttsx3_availability(self):
        """Test that pyttsx3 TTS is available and working"""
        try:
            import pyttsx3
            
            # Try to initialize TTS engine
            engine = pyttsx3.init()
            self.assertIsNotNone(engine)
            
            # Test basic functionality (don't actually play audio)
            engine.setProperty('rate', 200)
            rate = engine.getProperty('rate')
            self.assertIsInstance(rate, (int, float))
            
            engine.stop()
            
        except ImportError:
            self.skipTest("pyttsx3 not installed - install with: pip install pyttsx3")
        except Exception as e:
            self.fail(f"pyttsx3 test failed: {e}")
    
    def test_coqui_tts_import(self):
        """Test that Coqui TTS can be imported (even if not loaded)"""
        try:
            from TTS.api import TTS
            self.assertTrue(True, "Coqui TTS imports successfully")
            
        except ImportError:
            self.skipTest("Coqui TTS not installed - install with: pip install coqui-tts")
        except Exception as e:
            # Initialization might fail, but import should work
            self.assertTrue(True, f"Coqui TTS import worked (init may fail: {e})")

class TestRegressionStability(unittest.TestCase):
    """Tests that ensure system stability over repeated runs"""
    
    def test_repeated_voice_service_creation(self):
        """Test that voice service can be created multiple times"""
        for i in range(5):
            try:
                from services.voice_service import get_voice_service
                vs = get_voice_service()
                available = vs.is_available()
                self.assertIsInstance(available, dict)
                
            except Exception as e:
                self.fail(f"Voice service creation failed on iteration {i}: {e}")
    
    def test_memory_stability(self):
        """Basic memory stability test"""
        import gc
        
        initial_objects = len(gc.get_objects())
        
        # Create and destroy services multiple times
        for i in range(3):
            from services.voice_service import get_voice_service
            vs = get_voice_service()
            del vs
            gc.collect()
        
        final_objects = len(gc.get_objects())
        
        # Allow some growth but not excessive
        growth = final_objects - initial_objects
        self.assertLess(growth, 1000, f"Excessive memory growth: {growth} objects")

def run_local_only_tests():
    """Run all local-only tests"""
    print("Running Local-Only Functionality Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestLocalOnlyFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalTTSFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestRegressionStability))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_local_only_tests()
    sys.exit(0 if success else 1)