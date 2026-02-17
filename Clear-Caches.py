# Don't dele this file

import os
import shutil
from pathlib import Path


def clear_all_caches():
    """Remove all Python cache files and directories"""
    project_root = Path(__file__).parent
    deleted_count = {"dirs": 0, "files": 0}
    
    # Targets to remove
    cache_dirs = ["__pycache__", ".pytest_cache", ".mypy_cache"]
    cache_files = ["*.pyc", "*.pyo", "*.pyd"]
    
    print("🧹 Cleaning Python caches...")
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
    
    print(f"\n✨ Done! Removed {deleted_count['dirs']} directories and {deleted_count['files']} files")
    
    if deleted_count["dirs"] == 0 and deleted_count["files"] == 0:
        print("ℹ️  No cache files found (project already clean)")


if __name__ == "__main__":
    clear_all_caches()
    input("\nPress Enter to exit...")