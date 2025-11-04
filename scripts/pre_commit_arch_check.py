#!/usr/bin/env python3
"""
Pre-commit hook for architecture quality checks
Prevents commits that violate architectural standards
"""

import sys
import subprocess
from pathlib import Path

def run_architecture_check():
    """Run architecture monitoring as a pre-commit check"""
    
    # Run the architecture monitor
    script_path = Path(__file__).parent / "monitor_architecture.py"
    
    try:
        result = subprocess.run([
            sys.executable, str(script_path)
        ], capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        # Check if quality gates passed
        if result.returncode != 0:
            print("\n🚨 COMMIT BLOCKED: Architecture quality gates failed!")
            print("Please address the issues above before committing.")
            print("Run 'python scripts/monitor_architecture.py' for details.")
            return False
        
        print("\n✅ Architecture quality checks passed!")
        return True
        
    except Exception as e:
        print(f"❌ Architecture check failed: {e}")
        return False

if __name__ == "__main__":
    passed = run_architecture_check()
    sys.exit(0 if passed else 1)