#!/usr/bin/env python

import os
import sys
import shutil
import argparse
from pathlib import Path
import logging
import time

# Setup directory paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ROOT_DIR)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "cleanup.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("model_cleanup")

def find_model_cache_directories():
    """Find Hugging Face cache directories"""
    # Default cache locations
    cache_locations = []
    
    # Our project cache directory
    project_cache = Path(PROJECT_ROOT) / "model_cache"
    if project_cache.exists():
        cache_locations.append(project_cache)
    
    # Common locations for Hugging Face cache
    home = Path.home()
    cache_dirs = [
        home / ".cache" / "huggingface",
        home / ".huggingface",
        Path(os.environ.get("HF_HOME", "")) if os.environ.get("HF_HOME") else None,
        Path(os.environ.get("TRANSFORMERS_CACHE", "")) if os.environ.get("TRANSFORMERS_CACHE") else None,
    ]
    
    for directory in cache_dirs:
        if directory and directory.exists():
            cache_locations.append(directory)
    
    return cache_locations

def get_cache_size(directory):
    """Calculate the size of a directory in MB"""
    try:
        total_size = 0
        for path in directory.glob('**/*'):
            if path.is_file():
                total_size += path.stat().st_size
        return total_size / (1024 * 1024)  # Convert to MB
    except Exception as e:
        logger.error(f"Error calculating size of {directory}: {e}")
        return 0

def cleanup_model_cache(dry_run=False, keep_models=None):
    """Clean up model cache directories"""
    if keep_models is None:
        keep_models = ["Qwen/Qwen-0_5B-Chat"]  # Default to keep our model
    
    start_time = time.time()
    cache_dirs = find_model_cache_directories()
    
    if not cache_dirs:
        logger.info("No Hugging Face cache directories found.")
        return
    
    logger.info(f"Found {len(cache_dirs)} cache directories:")
    
    total_saved = 0
    total_size = 0
    total_kept = 0
    models_deleted = 0
    models_kept = 0
    
    for cache_dir in cache_dirs:
        logger.info(f"Examining {cache_dir}")
        
        # First check if this is our project cache
        if "model_cache" in str(cache_dir) and str(PROJECT_ROOT) in str(cache_dir):
            # For project cache, directly check subdirectories
            model_dirs = list(cache_dir.glob("*--*"))  # Match the Hugging Face format with -- instead of /
            
            if not model_dirs:
                model_dirs = list(cache_dir.glob("*"))  # Fallback to any directory
        else:
            # For Hugging Face cache, check the models directory
            models_dir = cache_dir / "models"
            if not models_dir.exists():
                logger.info(f"No models directory found in {cache_dir}")
                continue
            
            # Get all model directories
            model_dirs = list(models_dir.glob("*/*"))
        
        if not model_dirs:
            logger.info(f"No model directories found in {cache_dir}")
            continue
        
        logger.info(f"Found {len(model_dirs)} model directories")
        
        # Process each model directory
        for model_dir in model_dirs:
            # Get model name depending on format
            if "--" in model_dir.name:
                model_name = model_dir.name.replace("--", "/")
            else:
                model_name = f"{model_dir.parent.name}/{model_dir.name}" if "models" in str(model_dir.parent) else model_dir.name
            
            # Get size
            size_mb = get_cache_size(model_dir)
            total_size += size_mb
            
            # Skip models we want to keep
            should_keep = any(keep_model in model_name for keep_model in keep_models)
            
            if should_keep:
                logger.info(f"Keeping model: {model_name} ({size_mb:.2f} MB)")
                models_kept += 1
                total_kept += size_mb
                continue
            
            if dry_run:
                logger.info(f"Would delete: {model_name} ({size_mb:.2f} MB)")
                models_deleted += 1
                total_saved += size_mb
            else:
                try:
                    logger.info(f"Deleting: {model_name} ({size_mb:.2f} MB)")
                    shutil.rmtree(model_dir)
                    models_deleted += 1
                    total_saved += size_mb
                    logger.info(f"Successfully deleted {model_name}")
                except Exception as e:
                    logger.error(f"Error deleting {model_name}: {e}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info("=" * 60)
    if dry_run:
        logger.info(f"Dry run completed in {duration:.2f} seconds")
        logger.info(f"Would delete {models_deleted} models, saving {total_saved:.2f} MB")
        logger.info(f"Would keep {models_kept} models, using {total_kept:.2f} MB")
    else:
        logger.info(f"Cleanup completed in {duration:.2f} seconds")
        logger.info(f"Deleted {models_deleted} models, saved {total_saved:.2f} MB")
        logger.info(f"Kept {models_kept} models, using {total_kept:.2f} MB")
    logger.info(f"Total cache size: {total_size:.2f} MB")
    logger.info("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Clean up Hugging Face model cache")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--keep", nargs="+", default=["Qwen/Qwen-0_5B-Chat"], help="Models to keep (partial name matching)")
    parser.add_argument("--check", action="store_true", help="Just check cache size without listing all models")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Hugging Face Model Cache Cleanup Utility")
    print("=" * 60)
    print(f"Mode: {'Dry Run (nothing will be deleted)' if args.dry_run else 'Actual Deletion'}")
    print(f"Models to keep: {', '.join(args.keep)}")
    print("=" * 60)
    
    if args.check:
        # Just check total cache size
        cache_dirs = find_model_cache_directories()
        total_size = 0
        
        for cache_dir in cache_dirs:
            size_mb = get_cache_size(cache_dir)
            print(f"{cache_dir}: {size_mb:.2f} MB")
            total_size += size_mb
        
        print(f"Total cache size: {total_size:.2f} MB")
    else:
        cleanup_model_cache(dry_run=args.dry_run, keep_models=args.keep)
    
    print("=" * 60)
    print("Cleanup process completed")
    print("=" * 60)

if __name__ == "__main__":
    main()
