#!/usr/bin/env python3
"""
Comprehensive Regression Test Suite for Sales Roleplay Chatbot
=============================================================

This script runs all regression tests and provides detailed reporting.
Designed to be run repeatedly for continuous integration and regression testing.

Usage:
    python tests/regression_test_suite.py              # Run all tests
    python tests/regression_test_suite.py --fast       # Run only fast tests  
    python tests/regression_test_suite.py --voice      # Include voice tests
    python tests/regression_test_suite.py --report     # Generate detailed report
"""

import sys
import os
import time
import json
import unittest
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

class RegressionTestRunner:
    """Comprehensive test runner for regression testing"""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
        self.test_log = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        self.test_log.append(log_entry)
        
    def run_test_module(self, module_name: str, description: str) -> Dict:
        """Run a specific test module and return results"""
        self.log(f"Running {description}...")
        
        try:
            # Import and run the test module
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(f"tests.{module_name}")
            
            # Run tests with detailed results
            stream = unittest.TextTestRunner._makeResult(
                unittest.TextTestRunner(), unittest.TextTestRunner._makeResult, 2
            )
            
            test_start = time.time()
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            test_duration = time.time() - test_start
            
            return {
                "module": module_name,
                "description": description,
                "tests_run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "success": result.wasSuccessful(),
                "duration": test_duration,
                "failure_details": [str(f[1]) for f in result.failures],
                "error_details": [str(e[1]) for e in result.errors]
            }
            
        except Exception as e:
            self.log(f"Failed to run {module_name}: {e}", "ERROR")
            return {
                "module": module_name,
                "description": description,
                "tests_run": 0,
                "failures": 0,
                "errors": 1,
                "success": False,
                "duration": 0,
                "failure_details": [],
                "error_details": [str(e)]
            }
    
    def run_core_tests(self) -> List[Dict]:
        """Run core functionality tests (always run these)"""
        core_tests = [
            ("test_dependencies", "Dependency Validation"),
            ("test_imports", "Import Validation"),
            ("test_modular", "Modular Architecture"),
        ]
        
        results = []
        for module, description in core_tests:
            result = self.run_test_module(module, description)
            results.append(result)
            
        return results
    
    def run_service_tests(self) -> List[Dict]:
        """Run service-level tests"""
        service_tests = [
            ("test_model_optimization", "Model Optimization Service"),
            ("test_ai_improvement", "AI Response Quality"),
            ("test_enhanced_responses", "Enhanced Response System"),
        ]
        
        results = []
        for module, description in service_tests:
            result = self.run_test_module(module, description)
            results.append(result)
            
        return results
    
    def run_voice_tests(self) -> List[Dict]:
        """Run voice processing tests (optional)"""
        voice_tests = [
            ("test_voice_service", "Voice Processing Service"),
        ]
        
        results = []
        for module, description in voice_tests:
            result = self.run_test_module(module, description)
            results.append(result)
            
        return results
    
    def run_integration_tests(self) -> List[Dict]:
        """Run integration tests"""
        integration_tests = [
            ("test_integration", "Full System Integration"),
        ]
        
        results = []
        for module, description in integration_tests:
            result = self.run_test_module(module, description)
            results.append(result)
            
        return results
    
    def generate_report(self, all_results: List[Dict]) -> str:
        """Generate a comprehensive test report"""
        total_duration = time.time() - self.start_time
        
        # Summary statistics
        total_tests = sum(r["tests_run"] for r in all_results)
        total_failures = sum(r["failures"] for r in all_results)
        total_errors = sum(r["errors"] for r in all_results)
        success_rate = (total_tests - total_failures - total_errors) / max(total_tests, 1) * 100
        
        report = []
        report.append("=" * 80)
        report.append("SALES ROLEPLAY CHATBOT - REGRESSION TEST REPORT")
        report.append("=" * 80)
        report.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Duration: {total_duration:.2f} seconds")
        report.append("")
        
        # Summary
        report.append("SUMMARY:")
        report.append(f"  Total Tests: {total_tests}")
        report.append(f"  Passed: {total_tests - total_failures - total_errors}")
        report.append(f"  Failed: {total_failures}")
        report.append(f"  Errors: {total_errors}")
        report.append(f"  Success Rate: {success_rate:.1f}%")
        report.append("")
        
        # Per-module results
        report.append("DETAILED RESULTS:")
        for result in all_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            report.append(f"  {status} {result['description']}")
            report.append(f"    Module: {result['module']}")
            report.append(f"    Tests: {result['tests_run']}, Duration: {result['duration']:.2f}s")
            
            if result["failures"]:
                report.append(f"    Failures: {result['failures']}")
                for failure in result["failure_details"][:2]:  # Limit output
                    report.append(f"      - {failure.split('\\n')[0]}")
                    
            if result["errors"]:
                report.append(f"    Errors: {result['errors']}")
                for error in result["error_details"][:2]:  # Limit output
                    report.append(f"      - {error.split('\\n')[0]}")
                    
            report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS:")
        if total_failures + total_errors == 0:
            report.append("  🎉 All tests passed! System is stable.")
        else:
            report.append("  🔧 Issues found - review failed tests above")
            
        if success_rate >= 90:
            report.append("  ✅ System ready for deployment")
        elif success_rate >= 75:
            report.append("  ⚠️  System needs attention before deployment")
        else:
            report.append("  🚨 System requires significant fixes")
            
        report.append("")
        report.append("=" * 80)
        
        return "\\n".join(report)
    
    def save_results(self, all_results: List[Dict], report: str):
        """Save test results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON results
        results_file = PROJECT_ROOT / "tests" / f"regression_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "duration": time.time() - self.start_time,
                "results": all_results,
                "log": self.test_log
            }, f, indent=2)
        
        # Save text report  
        report_file = PROJECT_ROOT / "tests" / f"regression_report_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
            
        self.log(f"Results saved to {results_file}")
        self.log(f"Report saved to {report_file}")

def main():
    """Main function to run regression tests"""
    parser = argparse.ArgumentParser(description="Sales Roleplay Chatbot Regression Tests")
    parser.add_argument("--fast", action="store_true", help="Run only fast core tests")
    parser.add_argument("--voice", action="store_true", help="Include voice tests")
    parser.add_argument("--report", action="store_true", help="Generate detailed report files")
    parser.add_argument("--no-integration", action="store_true", help="Skip integration tests")
    
    args = parser.parse_args()
    
    runner = RegressionTestRunner()
    runner.log("Starting Sales Roleplay Chatbot Regression Tests")
    
    all_results = []
    
    # Always run core tests
    runner.log("Phase 1: Core Tests")
    all_results.extend(runner.run_core_tests())
    
    if not args.fast:
        # Run service tests
        runner.log("Phase 2: Service Tests")  
        all_results.extend(runner.run_service_tests())
        
        # Run voice tests if requested
        if args.voice:
            runner.log("Phase 3: Voice Tests")
            all_results.extend(runner.run_voice_tests())
            
        # Run integration tests unless skipped
        if not args.no_integration:
            runner.log("Phase 4: Integration Tests")
            all_results.extend(runner.run_integration_tests())
    
    # Generate and display report
    report = runner.generate_report(all_results)
    print("\\n" + report)
    
    # Save results if requested
    if args.report:
        runner.save_results(all_results, report)
    
    # Exit with appropriate code
    total_failures = sum(r["failures"] + r["errors"] for r in all_results)
    sys.exit(0 if total_failures == 0 else 1)

if __name__ == "__main__":
    main()