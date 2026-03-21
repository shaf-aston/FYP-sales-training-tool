# Don't delete this file
# Safe cache cleanup utility for Sales Roleplay Chatbot

import os
import shutil
from pathlib import Path


def clear_python_caches():
    """
    Remove Python bytecode and build caches.

    SAFE TO DELETE (always):
    - __pycache__/: Python compiled bytecode (.pyc, .pyo)
    - .pytest_cache/: pytest temporary cache
    - .mypy_cache/: mypy type checking cache
    - *.pyc, *.pyo: Compiled Python files

    Regenerated automatically on next Python run.
    """
    project_root = Path(__file__).parent
    deleted_count = {"dirs": 0, "files": 0}

    cache_dirs = ["__pycache__", ".pytest_cache", ".mypy_cache"]
    cache_files = ["*.pyc", "*.pyo"]

    print("🧹 Cleaning Python bytecode and test caches...")
    print(f"📂 Project root: {project_root}\n")

    # Remove cache directories
    for cache_dir_name in cache_dirs:
        for cache_path in project_root.rglob(cache_dir_name):
            if cache_path.is_dir():
                try:
                    shutil.rmtree(cache_path)
                    deleted_count["dirs"] += 1
                    print(f"✓ Removed: {cache_path.relative_to(project_root)}")
                except Exception as e:
                    print(f"✗ Failed to remove {cache_path.relative_to(project_root)}: {e}")

    # Remove cache files
    for pattern in cache_files:
        for cache_file in project_root.rglob(pattern):
            if cache_file.is_file():
                try:
                    cache_file.unlink()
                    deleted_count["files"] += 1
                    print(f"✓ Removed: {cache_file.relative_to(project_root)}")
                except Exception as e:
                    print(f"✗ Failed to remove {cache_file.relative_to(project_root)}: {e}")

    return deleted_count


def clear_session_data():
    """
    Remove temporary session state files.

    SAFE TO DELETE:
    - sessions/*.json: Session state snapshots (can be recreated from analytics.jsonl)
    - *.tmp, *.temp: Temporary work files

    PRESERVED (important data):
    - analytics.jsonl: Evaluation metrics (DO NOT DELETE)
    - metrics.jsonl: Performance telemetry (DO NOT DELETE)
    """
    project_root = Path(__file__).parent
    deleted_count = {"files": 0}

    print("\n🧹 Cleaning temporary session files...")

    # Remove session state files (safe — only snapshots, not evaluation data)
    sessions_dir = project_root / "sessions"
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            try:
                session_file.unlink()
                deleted_count["files"] += 1
                print(f"✓ Removed session: {session_file.relative_to(project_root)}")
            except Exception as e:
                print(f"✗ Failed to remove {session_file.relative_to(project_root)}: {e}")

    # Remove other temporary files
    for pattern in ["*.tmp", "*.temp"]:
        for temp_file in project_root.rglob(pattern):
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                    deleted_count["files"] += 1
                    print(f"✓ Removed: {temp_file.relative_to(project_root)}")
                except Exception as e:
                    print(f"✗ Failed to remove {temp_file.relative_to(project_root)}: {e}")

    return deleted_count


def preserve_important_data():
    """
    Report on critical files that should NEVER be deleted.
    """
    project_root = Path(__file__).parent
    critical_files = [
        ("analytics.jsonl", "Evaluation metrics (session analytics, stage transitions, intent distribution)"),
        ("metrics.jsonl", "Performance telemetry (latency, provider stats)"),
        ("src/config/", "Configuration files (signals, analysis, products)"),
        ("Documentation/", "Project documentation and architecture"),
    ]

    print("\n⚠️  CRITICAL FILES — NEVER DELETE:")
    for filepath, description in critical_files:
        full_path = project_root / filepath
        exists = "✓" if full_path.exists() else "✗"
        print(f"  {exists} {filepath}: {description}")


def clear_all_caches():
    """
    Remove all safe-to-delete caches and temporary files.
    Preserves all important data (analytics, metrics, config, documentation).
    """
    print("=" * 80)
    print("SALES CHATBOT CACHE CLEANUP UTILITY")
    print("=" * 80)

    # Clear Python bytecode caches (always safe)
    python_count = clear_python_caches()

    # Clear session snapshots (safe — not evaluation data)
    session_count = clear_session_data()

    # Report on preserved critical files
    preserve_important_data()

    # Summary
    total_dirs = python_count["dirs"]
    total_files = python_count["files"] + session_count["files"]

    print(f"\n✨ Done! Removed {total_dirs} directories and {total_files} files")

    if total_dirs == 0 and total_files == 0:
        print("ℹ️  No cache files found (project already clean)")

    print("\n📊 Preserved:")
    print("  • analytics.jsonl — FYP evaluation metrics (DO NOT DELETE)")
    print("  • metrics.jsonl — Performance telemetry (DO NOT DELETE)")
    print("  • src/config/ — All configuration files")
    print("  • Documentation/ — All architecture and project documentation")
    print("=" * 80)


if __name__ == "__main__":
    clear_all_caches()
    input("\nPress Enter to exit...")