import os
import sys
import logging
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler

class JsonFormatter(logging.Formatter):
    """Formats logs as a JSON string."""
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "funcName": record.funcName,
            "lineNo": record.lineno
        }
        return json.dumps(log_record)

def setup_logging(logs_dir: Path, log_level: str = "WARNING", use_json: bool = False):
    """Setup centralized and structured logging configuration."""

    level = os.environ.get("LOG_LEVEL", log_level).upper()
    
    logger = logging.getLogger()
    logger.setLevel(level)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    # Configure console handler with UTF-8 encoding for Windows
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Force UTF-8 encoding on Windows to handle emoji and special characters
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass  # Fallback silently if reconfigure fails

    if use_json or os.environ.get("LOG_JSON_FORMAT", "false").lower() == "true":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized with level {level} and {'JSON' if use_json else 'text'} format.")
    return logger

