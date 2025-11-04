#!/usr/bin/env python3
"""
Automated Architecture Monitoring Tool
Tracks code metrics, file sizes, and architectural health over time
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
import subprocess

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

@dataclass
class FileMetrics:
    """Metrics for a single file"""
    path: str
    lines: int
    size_bytes: int
    last_modified: str
    complexity_score: float = 0.0

@dataclass
class ArchitecturalMetrics:
    """Overall architectural health metrics"""
    timestamp: str
    total_files: int
    total_lines: int
    largest_file: FileMetrics
    files_over_500_lines: int
    files_over_1000_lines: int
    average_file_size: float
    duplicate_files: List[str]
    architectural_score: float
    recommendations: List[str]

class ArchitectureMonitor:
    """Monitor and track architectural health metrics"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.metrics_file = project_root / "architecture_metrics.json"
        self.thresholds = {
            'max_file_lines': 500,
            'critical_file_lines': 1000,
            'max_duplicates': 0,
            'target_avg_size': 300
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def calculate_complexity_score(self, file_path: Path) -> float:
        """Calculate a simple complexity score for a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple heuristics for complexity
            complexity = 0
            complexity += content.count('class ') * 3  # Classes
            complexity += content.count('def ') * 2    # Functions
            complexity += content.count('if ') * 1     # Conditionals
            complexity += content.count('for ') * 1    # Loops
            complexity += content.count('while ') * 1  # Loops
            complexity += content.count('try:') * 2    # Error handling
            complexity += content.count('except') * 2  # Error handling
            
            # Normalize by lines of code
            lines = len(content.split('\n'))
            return complexity / max(lines, 1) * 100
            
        except Exception:
            return 0.0
    
    def scan_python_files(self) -> List[FileMetrics]:
        """Scan all Python files and collect metrics"""
        files_metrics = []
        
        for py_file in self.src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                stat = py_file.stat()
                
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = len(f.readlines())
                
                complexity = self.calculate_complexity_score(py_file)
                
                metrics = FileMetrics(
                    path=str(py_file.relative_to(self.project_root)),
                    lines=lines,
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    complexity_score=complexity
                )
                
                files_metrics.append(metrics)
                
            except Exception as e:
                self.logger.warning(f"Failed to process {py_file}: {e}")
        
        return files_metrics
    
    def find_duplicate_files(self, files: List[FileMetrics]) -> List[str]:
        """Find potential duplicate files based on name similarity"""
        duplicates = []
        file_names = {}
        
        for file_metric in files:
            name = Path(file_metric.path).name
            if name in file_names:
                duplicates.append(f"{name}: {file_names[name]} & {file_metric.path}")
            else:
                file_names[name] = file_metric.path
        
        return duplicates
    
    def calculate_architectural_score(self, files: List[FileMetrics], duplicates: List[str]) -> Tuple[float, List[str]]:
        """Calculate overall architectural health score (0-100)"""
        score = 100.0
        recommendations = []
        
        # File size penalties
        large_files = [f for f in files if f.lines > self.thresholds['max_file_lines']]
        critical_files = [f for f in files if f.lines > self.thresholds['critical_file_lines']]
        
        if critical_files:
            penalty = len(critical_files) * 15
            score -= penalty
            recommendations.append(f"Refactor {len(critical_files)} files over {self.thresholds['critical_file_lines']} lines")
        
        if large_files:
            penalty = len(large_files) * 5
            score -= penalty
            recommendations.append(f"Consider refactoring {len(large_files)} files over {self.thresholds['max_file_lines']} lines")
        
        # Duplicate file penalties
        if duplicates:
            penalty = len(duplicates) * 10
            score -= penalty
            recommendations.append(f"Remove {len(duplicates)} duplicate files")
        
        # Complexity penalties
        high_complexity_files = [f for f in files if f.complexity_score > 50]
        if high_complexity_files:
            penalty = len(high_complexity_files) * 3
            score -= penalty
            recommendations.append(f"Simplify {len(high_complexity_files)} high-complexity files")
        
        # Average file size assessment
        avg_lines = sum(f.lines for f in files) / len(files) if files else 0
        if avg_lines > self.thresholds['target_avg_size'] * 2:
            score -= 10
            recommendations.append(f"Average file size ({avg_lines:.0f} lines) exceeds target")
        
        return max(score, 0.0), recommendations
    
    def generate_metrics_report(self) -> ArchitecturalMetrics:
        """Generate comprehensive architectural metrics"""
        self.logger.info("Scanning Python files...")
        files = self.scan_python_files()
        
        if not files:
            raise ValueError("No Python files found in src/ directory")
        
        # Sort files by line count (descending)
        files.sort(key=lambda x: x.lines, reverse=True)
        largest_file = files[0]
        
        # Find duplicates
        duplicates = self.find_duplicate_files(files)
        
        # Calculate scores
        arch_score, recommendations = self.calculate_architectural_score(files, duplicates)
        
        # Generate metrics
        metrics = ArchitecturalMetrics(
            timestamp=datetime.now().isoformat(),
            total_files=len(files),
            total_lines=sum(f.lines for f in files),
            largest_file=largest_file,
            files_over_500_lines=len([f for f in files if f.lines > 500]),
            files_over_1000_lines=len([f for f in files if f.lines > 1000]),
            average_file_size=sum(f.lines for f in files) / len(files),
            duplicate_files=duplicates,
            architectural_score=arch_score,
            recommendations=recommendations
        )
        
        return metrics
    
    def save_metrics(self, metrics: ArchitecturalMetrics):
        """Save metrics to JSON file for tracking over time"""
        # Load existing history
        history = []
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    history = data.get('history', [])
            except Exception as e:
                self.logger.warning(f"Failed to load existing metrics: {e}")
        
        # Add current metrics
        history.append(asdict(metrics))
        
        # Keep only last 50 entries
        history = history[-50:]
        
        # Save updated history
        output = {
            'current': asdict(metrics),
            'history': history,
            'generated_at': datetime.now().isoformat()
        }
        
        with open(self.metrics_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        self.logger.info(f"Metrics saved to {self.metrics_file}")
    
    def print_report(self, metrics: ArchitecturalMetrics):
        """Print formatted metrics report"""
        print("\n" + "="*80)
        print("🏗️  ARCHITECTURAL HEALTH REPORT")
        print("="*80)
        print(f"📅 Generated: {metrics.timestamp}")
        print(f"🎯 Architecture Score: {metrics.architectural_score:.1f}/100")
        
        # Health indicator
        if metrics.architectural_score >= 90:
            health = "🟢 EXCELLENT"
        elif metrics.architectural_score >= 75:
            health = "🟡 GOOD"
        elif metrics.architectural_score >= 60:
            health = "🟠 NEEDS ATTENTION"
        else:
            health = "🔴 CRITICAL"
        
        print(f"🏥 Health Status: {health}")
        print()
        
        # File statistics
        print("📊 FILE STATISTICS:")
        print(f"   Total Python files: {metrics.total_files}")
        print(f"   Total lines of code: {metrics.total_lines:,}")
        print(f"   Average file size: {metrics.average_file_size:.0f} lines")
        print(f"   Files > 500 lines: {metrics.files_over_500_lines}")
        print(f"   Files > 1000 lines: {metrics.files_over_1000_lines}")
        print()
        
        # Largest file
        print("📏 LARGEST FILE:")
        print(f"   {metrics.largest_file.path}")
        print(f"   Lines: {metrics.largest_file.lines:,}")
        print(f"   Complexity: {metrics.largest_file.complexity_score:.1f}")
        print()
        
        # Duplicates
        if metrics.duplicate_files:
            print("🔄 DUPLICATE FILES:")
            for dup in metrics.duplicate_files[:5]:  # Show first 5
                print(f"   {dup}")
            if len(metrics.duplicate_files) > 5:
                print(f"   ... and {len(metrics.duplicate_files) - 5} more")
            print()
        
        # Recommendations
        if metrics.recommendations:
            print("💡 RECOMMENDATIONS:")
            for i, rec in enumerate(metrics.recommendations, 1):
                print(f"   {i}. {rec}")
            print()
        
        print("="*80)
    
    def check_ci_thresholds(self, metrics: ArchitecturalMetrics) -> bool:
        """Check if metrics meet CI/CD quality gates"""
        failing_checks = []
        
        # Critical thresholds for CI/CD
        if metrics.largest_file.lines > 1500:
            failing_checks.append(f"Largest file exceeds 1500 lines ({metrics.largest_file.lines})")
        
        if metrics.files_over_1000_lines > 5:
            failing_checks.append(f"Too many large files: {metrics.files_over_1000_lines} > 5")
        
        if metrics.architectural_score < 60:
            failing_checks.append(f"Architecture score too low: {metrics.architectural_score:.1f} < 60")
        
        if len(metrics.duplicate_files) > 2:
            failing_checks.append(f"Too many duplicates: {len(metrics.duplicate_files)} > 2")
        
        if failing_checks:
            print("\n🚨 CI/CD QUALITY GATE FAILURES:")
            for check in failing_checks:
                print(f"   ❌ {check}")
            return False
        
        print("\n✅ All CI/CD quality gates passed!")
        return True

def main():
    """Main function to run architecture monitoring"""
    try:
        monitor = ArchitectureMonitor(PROJECT_ROOT)
        
        # Generate metrics
        metrics = monitor.generate_metrics_report()
        
        # Print report
        monitor.print_report(metrics)
        
        # Save metrics
        monitor.save_metrics(metrics)
        
        # Check CI thresholds
        ci_passed = monitor.check_ci_thresholds(metrics)
        
        # Exit with appropriate code for CI/CD
        sys.exit(0 if ci_passed else 1)
        
    except Exception as e:
        logging.error(f"Architecture monitoring failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()