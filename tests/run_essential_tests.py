"""
Simple test runner for the refactored codebase
Runs essential tests only
"""
import sys
import subprocess
from pathlib import Path

def run_essential_tests():
    """Run only the essential tests"""
    test_files = [
        "test_essentials_only.py",
        "test_integration_complete.py"
    ]
    
    for test_file in test_files:
        print(f"\n{'='*60}")
        print(f"Running {test_file}")
        print(f"{'='*60}")
        
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_file, "-v", "--tb=short"
        ], cwd=Path(__file__).parent)
        
        if result.returncode != 0:
            print(f"❌ {test_file} failed")
            return False
        else:
            print(f"✅ {test_file} passed")
    
    return True

if __name__ == "__main__":
    print("Running essential tests for refactored codebase...")
    success = run_essential_tests()
    
    if success:
        print("\n🎉 All essential tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)