"""
Main test runner with pytest integration and reporting
"""
import os
import sys
import pytest
import argparse
from pathlib import Path
from datetime import datetime

def run_tests(args):
    """Run tests with pytest"""
    pytest_args = []
    
    if args.suite:
        if args.suite == "deps":
            pytest_args.append("test_dependencies.py")
        elif args.suite == "voice":
            pytest_args.append("test_voice_service.py")
        elif args.suite == "optimization":
            pytest_args.append("test_model_optimization.py")
        elif args.suite == "integration":
            pytest_args.append("test_integration.py")
            
    pytest_args.extend(["-v"])
    
    if not args.no_report:
        report_path = Path("tests/output/test-results.xml")
        report_path.parent.mkdir(exist_ok=True)
        pytest_args.extend(["--junitxml", str(report_path)])
    
    if args.coverage:
        pytest_args.extend([
            "--cov=src",
            "--cov-report=html:tests/output/coverage",
            "--cov-report=term-missing"
        ])
    
    return pytest.main(pytest_args)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Sales Roleplay Chatbot Test Runner")
    parser.add_argument("--suite", 
                       choices=["deps", "voice", "optimization", "integration"],
                       help="Run specific test suite")
    parser.add_argument("--no-report", action="store_true",
                       help="Skip generating test report")
    parser.add_argument("--coverage", action="store_true",
                       help="Generate test coverage report")
    
    args = parser.parse_args()
    
    try:
        result = run_tests(args)
        sys.exit(result)
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()