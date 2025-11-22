"""
Test script to validate the modular architecture works correctly
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "utils"))


def test_config():
    """Test configuration loading"""
    try:
        from src.config.settings import APP_TITLE, APP_VERSION
        print(f"Config: {APP_TITLE} v{APP_VERSION}")
        return True
    except Exception as e:
        print(f"Config failed: {e}")
        return False

def test_character_profiles():
    """Test character profiles"""
    try:
        from src.data_access.character_profiles import get_mary_profile
        mary = get_mary_profile()
        print(f"Character: {mary['name']}, age {mary['age']}")
        return True
    except Exception as e:
        print(f"Character profiles failed: {e}")
        return False

def test_logger_config():
    """Test logger configuration"""
    try:
        from config.logger_config import setup_logging
        logger = setup_logging(project_root / "logs")
        logger.info("Test log message")
        print("Logger: Configuration loaded and working")
        return True
    except Exception as e:
        print(f"Logger failed: {e}")
        return False

def test_enhanced_responses():
    """Test enhanced responses"""
    try:
        from src.fallback_responses import generate_ai_response
        print("Enhanced responses: Module loaded successfully")
        return True
    except Exception as e:
        print(f"Enhanced responses failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Modular Architecture Components")
    print("=" * 50)
    
    tests = [
        test_config,
        test_character_profiles,
        test_logger_config,
        test_enhanced_responses
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print("=" * 50)
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("All modular components working correctly!")
        print("The modular architecture is ready for use!")
    else:
        print("Some components need attention")
    
    return passed == len(tests)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)