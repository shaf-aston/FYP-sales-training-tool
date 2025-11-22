"""
File Management Utilities
Handles file operations, validation, and organization
"""
import logging
import os
import json
import shutil
import tempfile
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class FileManager:
    """File management utilities"""
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize file manager
        
        Args:
            base_path: Base directory for file operations
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.temp_files = []  # Track temp files for cleanup
    
    def ensure_directory(self, path: Union[str, Path]) -> Path:
        """
        Ensure directory exists, create if needed
        
        Args:
            path: Directory path
            
        Returns:
            Path object for the directory
        """
        path = Path(path)
        if not path.is_absolute():
            path = self.base_path / path
        
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory: {path}")
            return path
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise
    
    def safe_write_json(self, data: Dict[str, Any], file_path: Union[str, Path],
                       backup: bool = True, indent: int = 2) -> bool:
        """
        Safely write JSON data with optional backup
        
        Args:
            data: Data to write
            file_path: Target file path
            backup: Whether to create backup
            indent: JSON formatting indent
            
        Returns:
            Success status
        """
        file_path = Path(file_path)
        if not file_path.is_absolute():
            file_path = self.base_path / file_path
        
        # Ensure parent directory exists
        self.ensure_directory(file_path.parent)
        
        try:
            # Create backup if file exists and backup requested
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                shutil.copy2(file_path, backup_path)
                logger.debug(f"Created backup: {backup_path}")
            
            # Write to temporary file first
            temp_path = file_path.with_suffix(f".tmp_{os.getpid()}")
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            # Atomic move to final location
            shutil.move(str(temp_path), str(file_path))
            
            logger.debug(f"Successfully wrote JSON to {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to write JSON to {file_path}: {e}")
            # Cleanup temp file if it exists
            temp_path = file_path.with_suffix(f".tmp_{os.getpid()}")
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    def safe_read_json(self, file_path: Union[str, Path], 
                      default: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Safely read JSON data with fallback
        
        Args:
            file_path: Source file path
            default: Default value if file doesn't exist or is invalid
            
        Returns:
            Loaded JSON data or default
        """
        file_path = Path(file_path)
        if not file_path.is_absolute():
            file_path = self.base_path / file_path
        
        if not file_path.exists():
            logger.warning(f"JSON file not found: {file_path}")
            return default or {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Successfully read JSON from {file_path}")
            return data
        
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            
            # Try to find backup
            backup_files = list(file_path.parent.glob(f"{file_path.stem}.backup_*.json"))
            if backup_files:
                latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
                logger.info(f"Attempting to restore from backup: {latest_backup}")
                try:
                    with open(latest_backup, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as backup_e:
                    logger.error(f"Backup restore failed: {backup_e}")
            
            return default or {}
        
        except Exception as e:
            logger.error(f"Failed to read JSON from {file_path}: {e}")
            return default or {}
    
    def create_temp_file(self, suffix: str = ".tmp", prefix: str = "temp_",
                        content: Optional[str] = None) -> Path:
        """
        Create temporary file
        
        Args:
            suffix: File suffix
            prefix: File prefix
            content: Initial content
            
        Returns:
            Path to temporary file
        """
        try:
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            temp_path = Path(temp_path)
            
            # Write initial content if provided
            if content is not None:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                os.close(fd)
            
            # Track for cleanup
            self.temp_files.append(temp_path)
            
            logger.debug(f"Created temp file: {temp_path}")
            return temp_path
        
        except Exception as e:
            logger.error(f"Failed to create temp file: {e}")
            raise
    
    def cleanup_temp_files(self):
        """Clean up all tracked temporary files"""
        cleaned = 0
        for temp_file in self.temp_files[:]:  # Copy list to avoid modification during iteration
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    cleaned += 1
                self.temp_files.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} temporary files")
    
    def get_file_hash(self, file_path: Union[str, Path], 
                     algorithm: str = "md5") -> str:
        """
        Calculate file hash
        
        Args:
            file_path: File to hash
            algorithm: Hash algorithm (md5, sha1, sha256)
            
        Returns:
            Hex digest of file hash
        """
        file_path = Path(file_path)
        
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            raise
    
    def organize_files_by_date(self, source_dir: Union[str, Path],
                              target_dir: Union[str, Path],
                              file_pattern: str = "*.*") -> Dict[str, int]:
        """
        Organize files by creation date
        
        Args:
            source_dir: Source directory
            target_dir: Target directory
            file_pattern: File pattern to match
            
        Returns:
            Dictionary with organization statistics
        """
        source_dir = Path(source_dir)
        target_dir = Path(target_dir)
        
        stats = {"moved": 0, "errors": 0, "skipped": 0}
        
        try:
            for file_path in source_dir.glob(file_pattern):
                if not file_path.is_file():
                    continue
                
                try:
                    # Get creation date
                    creation_time = datetime.fromtimestamp(file_path.stat().st_ctime)
                    date_folder = target_dir / creation_time.strftime("%Y-%m-%d")
                    
                    # Ensure target directory exists
                    self.ensure_directory(date_folder)
                    
                    # Move file
                    target_path = date_folder / file_path.name
                    
                    # Handle name conflicts
                    counter = 1
                    while target_path.exists():
                        name_parts = file_path.stem, counter, file_path.suffix
                        target_path = date_folder / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                        counter += 1
                    
                    shutil.move(str(file_path), str(target_path))
                    stats["moved"] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to move {file_path}: {e}")
                    stats["errors"] += 1
            
            logger.info(f"File organization complete: {stats}")
            return stats
        
        except Exception as e:
            logger.error(f"File organization failed: {e}")
            stats["errors"] += 1
            return stats
    
    def clean_old_files(self, directory: Union[str, Path],
                       max_age_days: int, file_pattern: str = "*.*",
                       dry_run: bool = False) -> Dict[str, int]:
        """
        Clean old files from directory
        
        Args:
            directory: Directory to clean
            max_age_days: Maximum file age in days
            file_pattern: File pattern to match
            dry_run: Only simulate, don't actually delete
            
        Returns:
            Dictionary with cleaning statistics
        """
        directory = Path(directory)
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        
        stats = {"deleted": 0, "size_freed": 0, "errors": 0}
        
        try:
            for file_path in directory.glob(file_pattern):
                if not file_path.is_file():
                    continue
                
                try:
                    file_stat = file_path.stat()
                    
                    if file_stat.st_mtime < cutoff_time:
                        file_size = file_stat.st_size
                        
                        if not dry_run:
                            file_path.unlink()
                        
                        stats["deleted"] += 1
                        stats["size_freed"] += file_size
                        
                        logger.debug(f"{'Would delete' if dry_run else 'Deleted'}: {file_path}")
                
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    stats["errors"] += 1
            
            logger.info(f"File cleanup {'simulation' if dry_run else 'complete'}: {stats}")
            return stats
        
        except Exception as e:
            logger.error(f"File cleanup failed: {e}")
            stats["errors"] += 1
            return stats
    
    def get_directory_size(self, directory: Union[str, Path]) -> Dict[str, Any]:
        """
        Calculate directory size and file count
        
        Args:
            directory: Directory to analyze
            
        Returns:
            Dictionary with size statistics
        """
        directory = Path(directory)
        
        stats = {
            "total_size": 0,
            "file_count": 0,
            "dir_count": 0,
            "largest_file": {"path": None, "size": 0},
            "extensions": {}
        }
        
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    file_size = item.stat().st_size
                    stats["total_size"] += file_size
                    stats["file_count"] += 1
                    
                    # Track largest file
                    if file_size > stats["largest_file"]["size"]:
                        stats["largest_file"] = {
                            "path": str(item),
                            "size": file_size
                        }
                    
                    # Track extensions
                    ext = item.suffix.lower() or "no_extension"
                    if ext not in stats["extensions"]:
                        stats["extensions"][ext] = {"count": 0, "size": 0}
                    stats["extensions"][ext]["count"] += 1
                    stats["extensions"][ext]["size"] += file_size
                
                elif item.is_dir():
                    stats["dir_count"] += 1
            
            return stats
        
        except Exception as e:
            logger.error(f"Failed to analyze directory {directory}: {e}")
            return {"error": str(e)}
    
    def __del__(self):
        """Cleanup on destruction"""
        self.cleanup_temp_files()