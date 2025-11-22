#!/usr/bin/env python3
"""
Convenience script to run the comprehensive test suite from the project root.
This is a simple wrapper around tests/run_all_tests.py
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Run the test runner from the tests directory"""
    project_root = Path(__file__).parent
    test_runner = project_root / "tests" / "run_all_tests.py"
    
    if not test_runner.exists():
        print(f"❌ Test runner not found at: {test_runner}")
        return 1
    
    # Pass all arguments to the actual test runner
    cmd = [sys.executable, str(test_runner)] + sys.argv[1:]
    
    try:
        result = subprocess.run(cmd, cwd=project_root)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())