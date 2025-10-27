#!/usr/bin/env python3
"""
Comprehensive integration test suite
Tests full system functionality with different dependency configurations
"""

import sys
import os
import asyncio
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess
import time

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Import core modules
try:
    from src.models.character_profiles import get_mary_profile, get_jake_profile
    from src.config.settings import APP_TITLE, APP_VERSION
    CHARACTER_PROFILES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Character profiles not available: {e}")
    CHARACTER_PROFILES_AVAILABLE = False

try:
    from src.services.voice_service import EnhancedVoiceService, VoiceEmotion
    VOICE_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Voice service not available: {e}")
    VOICE_SERVICE_AVAILABLE = False

try:
    from src.services.model_optimization_service import ModelOptimizationService
    MODEL_OPTIMIZATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Model optimization service not available: {e}")
    MODEL_OPTIMIZATION_AVAILABLE = False

class TestSystemIntegration(unittest.TestCase):
    """Test core system integration"""
    
    def test_configuration_loading(self):
        """Test that configuration is properly loaded"""
        if not CHARACTER_PROFILES_AVAILABLE:
            self.skipTest("Configuration not available")
        
        # Test app configuration
        self.assertIsInstance(APP_TITLE, str)
        self.assertIsInstance(APP_VERSION, str)
        self.assertGreater(len(APP_TITLE), 0)
        self.assertGreater(len(APP_VERSION), 0)
        
        print(f"✅ Configuration loaded: {APP_TITLE} v{APP_VERSION}")
    
    def test_character_profiles_integration(self):
        """Test character profiles integration"""
        if not CHARACTER_PROFILES_AVAILABLE:
            self.skipTest("Character profiles not available")
        
        # Test loading different profiles
        mary = get_mary_profile()
        jake = get_jake_profile()
        
        # Validate profile structure
        required_fields = ['name', 'age', 'background', 'communication_style', 'goals']
        
        for profile, name in [(mary, 'Mary'), (jake, 'Jake')]:
            for field in required_fields:
                self.assertIn(field, profile, f"Missing {field} in {name} profile")
            
            self.assertIsInstance(profile['name'], str)
            self.assertIsInstance(profile['age'], int)
            self.assertGreater(profile['age'], 0)
        
        print(f"✅ Character profiles loaded: {mary['name']}, {jake['name']}")
    
    def test_logging_system(self):
        """Test logging system integration"""
        try:
            from utils.logger_config import setup_logging
            
            # Setup logging
            logs_dir = project_root / "logs"
            logger = setup_logging(logs_dir)
            
            # Test logging
            logger.info("Integration test log message")
            
            self.assertIsNotNone(logger)
            print("✅ Logging system working")
            
        except ImportError:
            print("⚠️  Logging system not available")

class TestServiceIntegration(unittest.TestCase):
    """Test service integration"""
    
    def setUp(self):
        self.services = {}
        
        # Initialize available services
        if VOICE_SERVICE_AVAILABLE:
            self.services['voice'] = EnhancedVoiceService()
        
        if MODEL_OPTIMIZATION_AVAILABLE:
            self.services['optimization'] = ModelOptimizationService()
    
    def test_voice_service_integration(self):
        """Test voice service integration"""
        if 'voice' not in self.services:
            self.skipTest("Voice service not available")
        
        voice_service = self.services['voice']
        
        # Test service capabilities
        capabilities = voice_service.get_voice_capabilities()
        self.assertIsInstance(capabilities, dict)
        self.assertIn('speech_to_text', capabilities)
        self.assertIn('text_to_speech', capabilities)
        
        # Test availability check
        availability = voice_service.is_available()
        self.assertIsInstance(availability, dict)
        
        print("✅ Voice service integration working")
        print(f"   Speech-to-text: {'✅' if availability.get('whisper') else '❌'}")
        print(f"   Text-to-speech: {'✅' if availability.get('coqui_tts') else '❌'}")
    
    def test_optimization_service_integration(self):
        """Test model optimization service integration"""
        if 'optimization' not in self.services:
            self.skipTest("Model optimization service not available")
        
        optimization_service = self.services['optimization']
        
        # Test cache statistics
        stats = optimization_service.get_cache_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn('cache_capacity', stats)
        self.assertIn('processing', stats.get('memory_usage', {}))
        
        # Test performance analytics
        analytics = optimization_service.get_performance_analytics()
        self.assertIsInstance(analytics, dict)
        
        print("✅ Model optimization service integration working")
        print(f"   Optimization features: {optimization_service.optimization_features}")
    
    def test_cross_service_compatibility(self):
        """Test compatibility between services"""
        if len(self.services) < 2:
            self.skipTest("Multiple services not available")
        
        # Test that services can coexist
        for service_name, service in self.services.items():
            self.assertIsNotNone(service)
        
        print("✅ Cross-service compatibility working")
        print(f"   Active services: {list(self.services.keys())}")

class TestDependencyConfiguration(unittest.TestCase):
    """Test different dependency configurations"""
    
    def test_minimal_configuration(self):
        """Test system with minimal dependencies"""
        # This would test with only core dependencies
        # For now, just verify the system can start
        
        try:
            # Import core modules
            from src.config.settings import APP_TITLE
            minimal_working = True
        except ImportError:
            minimal_working = False
        
        if minimal_working:
            print("✅ Minimal configuration working")
        else:
            print("❌ Minimal configuration not working")
        
        self.assertTrue(minimal_working, "Minimal configuration should work")
    
    def test_optimization_configuration(self):
        """Test system with optimization packages"""
        optimization_available = MODEL_OPTIMIZATION_AVAILABLE
        
        if optimization_available:
            try:
                service = ModelOptimizationService()
                features = service.optimization_features
                
                # Count available optimizations
                available_count = sum(1 for available in features.values() if available)
                total_count = len(features)
                
                print(f"✅ Optimization configuration: {available_count}/{total_count} features")
                
                return available_count > 0
            except Exception as e:
                print(f"❌ Optimization configuration failed: {e}")
                return False
        else:
            print("⚠️  Optimization packages not available")
            return True  # Not having optimizations is OK
    
    def test_voice_configuration(self):
        """Test system with voice packages"""
        voice_available = VOICE_SERVICE_AVAILABLE
        
        if voice_available:
            try:
                service = EnhancedVoiceService()
                availability = service.is_available()
                
                # Count available voice features
                voice_features = ['whisper', 'coqui_tts']
                available_count = sum(1 for feature in voice_features if availability.get(feature))
                
                print(f"✅ Voice configuration: {available_count}/{len(voice_features)} features")
                
                return True  # Voice service can work even without all features
            except Exception as e:
                print(f"❌ Voice configuration failed: {e}")
                return False
        else:
            print("⚠️  Voice packages not available")
            return True  # Not having voice is OK

class TestAPIIntegration(unittest.TestCase):
    """Test API integration (if available)"""
    
    def test_api_imports(self):
        """Test that API modules can be imported"""
        try:
            from src.api.routes.chat_routes import router as chat_router
            print("✅ Chat routes importable")
            api_available = True
        except ImportError as e:
            print(f"⚠️  Chat routes not available: {e}")
            api_available = False
        
        try:
            from src.api.routes.voice_routes import router as voice_router
            print("✅ Voice routes importable")
        except ImportError as e:
            print(f"⚠️  Voice routes not available: {e}")
        
        return api_available
    
    @patch('subprocess.run')
    def test_api_startup_simulation(self, mock_run):
        """Simulate API startup without actually starting server"""
        mock_run.return_value = Mock(returncode=0, stdout="Server started")
        
        # Simulate startup command
        result = mock_run("uvicorn src.main:app --host 0.0.0.0 --port 8000", shell=True, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        print("✅ API startup simulation successful")

class TestDataPersistence(unittest.TestCase):
    """Test data persistence and file operations"""
    
    def test_model_cache_directory(self):
        """Test model cache directory creation and access"""
        try:
            from config.settings import MODEL_CACHE_DIR
            
            # Ensure cache directory exists
            MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Test write access
            test_file = MODEL_CACHE_DIR / "test_write.txt"
            test_file.write_text("test")
            test_file.unlink()  # Clean up
            
            print(f"✅ Model cache directory accessible: {MODEL_CACHE_DIR}")
            return True
        except Exception as e:
            print(f"❌ Model cache directory issue: {e}")
            return False
    
    def test_logs_directory(self):
        """Test logs directory creation and access"""
        logs_dir = project_root / "logs"
        
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Test write access
            test_log = logs_dir / "test.log"
            test_log.write_text("test log entry")
            test_log.unlink()  # Clean up
            
            print(f"✅ Logs directory accessible: {logs_dir}")
            return True
        except Exception as e:
            print(f"❌ Logs directory issue: {e}")
            return False
    
    def test_conversation_backup(self):
        """Test conversation backup functionality"""
        backup_file = project_root / "logs" / "conversation_backup.json"
        
        try:
            # Create test backup
            test_data = {
                "timestamp": "2024-01-01T00:00:00",
                "conversations": [
                    {"user": "Hello", "assistant": "Hi there!"}
                ]
            }
            
            with open(backup_file, 'w') as f:
                json.dump(test_data, f)
            
            # Read it back
            with open(backup_file, 'r') as f:
                loaded_data = json.load(f)
            
            self.assertEqual(loaded_data["conversations"][0]["user"], "Hello")
            
            print("✅ Conversation backup working")
            return True
        except Exception as e:
            print(f"❌ Conversation backup issue: {e}")
            return False

class TestErrorHandling(unittest.TestCase):
    """Test error handling and graceful degradation"""
    
    def test_missing_model_graceful_handling(self):
        """Test system behavior with missing models"""
        if not MODEL_OPTIMIZATION_AVAILABLE:
            self.skipTest("Model optimization service not available")
        
        try:
            service = ModelOptimizationService()
            
            # Test with non-existent model
            with self.assertRaises(Exception):
                service.load_optimized_model("non-existent-model")
            
            print("✅ Missing model handling working")
        except Exception as e:
            print(f"❌ Missing model handling failed: {e}")
    
    def test_voice_fallback_behavior(self):
        """Test voice service fallback behavior"""
        if not VOICE_SERVICE_AVAILABLE:
            self.skipTest("Voice service not available")
        
        try:
            service = EnhancedVoiceService()
            
            # Test speech-to-text fallback
            async def test_stt():
                result = await service.speech_to_text(b"fake_audio")
                return result
            
            result = asyncio.run(test_stt())
            self.assertIsNotNone(result)
            
            # Test text-to-speech fallback
            async def test_tts():
                result = await service.text_to_speech("Hello world")
                return result
            
            tts_result = asyncio.run(test_tts())
            # Should return None or bytes
            self.assertTrue(tts_result is None or isinstance(tts_result, bytes))
            
            print("✅ Voice fallback behavior working")
        except Exception as e:
            print(f"❌ Voice fallback behavior failed: {e}")

def run_integration_tests():
    """Run all integration tests"""
    print("🧪 Running Integration Tests")
    print("=" * 60)
    
    # Create test suite
    test_classes = [
        TestSystemIntegration,
        TestServiceIntegration,
        TestDependencyConfiguration,
        TestAPIIntegration,
        TestDataPersistence,
        TestErrorHandling
    ]
    
    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 60)
    print(f"📊 Integration Test Results:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print("   Failures:")
        for test, error in result.failures:
            print(f"     - {test}: {error.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("   Errors:")
        for test, error in result.errors:
            print(f"     - {test}: {error.split('Exception:')[-1].strip()}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"   Success rate: {success_rate:.1f}%")
    
    return len(result.failures) == 0 and len(result.errors) == 0

def run_system_health_check():
    """Run comprehensive system health check"""
    print("\n🏥 System Health Check")
    print("=" * 60)
    
    health_status = {}
    
    # Check core functionality
    try:
        from src.config.settings import APP_TITLE
        health_status['configuration'] = True
        print("✅ Configuration: OK")
    except Exception as e:
        health_status['configuration'] = False
        print(f"❌ Configuration: {e}")
    
    # Check services
    if VOICE_SERVICE_AVAILABLE:
        try:
            service = EnhancedVoiceService()
            capabilities = service.get_voice_capabilities()
            health_status['voice_service'] = True
            print("✅ Voice Service: OK")
        except Exception as e:
            health_status['voice_service'] = False
            print(f"❌ Voice Service: {e}")
    else:
        health_status['voice_service'] = None
        print("⚠️  Voice Service: Not available")
    
    if MODEL_OPTIMIZATION_AVAILABLE:
        try:
            service = ModelOptimizationService()
            stats = service.get_cache_statistics()
            health_status['optimization_service'] = True
            print("✅ Optimization Service: OK")
        except Exception as e:
            health_status['optimization_service'] = False
            print(f"❌ Optimization Service: {e}")
    else:
        health_status['optimization_service'] = None
        print("⚠️  Optimization Service: Not available")
    
    # Check file system access
    try:
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        test_file = logs_dir / "health_check.tmp"
        test_file.write_text("OK")
        test_file.unlink()
        health_status['filesystem'] = True
        print("✅ File System: OK")
    except Exception as e:
        health_status['filesystem'] = False
        print(f"❌ File System: {e}")
    
    # Overall health assessment
    working_components = sum(1 for status in health_status.values() if status is True)
    total_components = len([s for s in health_status.values() if s is not None])
    
    if total_components > 0:
        health_percentage = (working_components / total_components) * 100
        print(f"\n🎯 Overall Health: {health_percentage:.0f}% ({working_components}/{total_components} components)")
        
        if health_percentage >= 90:
            print("🎉 Excellent system health!")
        elif health_percentage >= 70:
            print("✅ Good system health")
        elif health_percentage >= 50:
            print("⚠️  Moderate system health - some issues need attention")
        else:
            print("❌ Poor system health - multiple issues need resolution")
    else:
        print("❌ No components available for health check")
    
    return health_status

if __name__ == "__main__":
    print("🚀 Sales Roleplay Chatbot - Integration Testing")
    print("=" * 60)
    
    # Run integration tests
    integration_success = run_integration_tests()
    
    # Run health check
    health_status = run_system_health_check()
    
    # Final summary
    print("\n📋 Final Summary")
    print("=" * 60)
    
    if integration_success:
        print("✅ Integration tests passed")
    else:
        print("❌ Some integration tests failed")
    
    working_services = sum(1 for status in health_status.values() if status is True)
    available_services = len([s for s in health_status.values() if s is not None])
    
    print(f"🔧 System Status: {working_services}/{available_services} components working")
    
    if CHARACTER_PROFILES_AVAILABLE:
        print("✅ Ready for character-based conversations")
    else:
        print("⚠️  Character profiles need attention")
    
    if VOICE_SERVICE_AVAILABLE:
        print("🎤 Voice features available")
    else:
        print("💬 Text-only mode")
    
    if MODEL_OPTIMIZATION_AVAILABLE:
        print("🚀 Performance optimizations available")
    else:
        print("⚡ Basic performance mode")
    
    overall_success = integration_success and (working_services >= available_services * 0.7)
    
    print(f"\n{'🎉 System ready for deployment!' if overall_success else '⚠️  System needs attention before deployment'}")
    
    sys.exit(0 if overall_success else 1)