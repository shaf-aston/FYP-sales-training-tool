# Centralized logging setup for the AI Sales Training Chatbot

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

def setup_logging(logs_dir: Path, log_level: str = "INFO", use_json: bool = False):
    """Setup centralized and structured logging configuration."""

    # Get log level from environment or use default
    level = os.environ.get("LOG_LEVEL", log_level).upper()
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Clear existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Ensure logs directory exists
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create file handler
    file_handler = RotatingFileHandler(
        logs_dir / "chatbot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)

    # Set formatter
    if use_json or os.environ.get("LOG_JSON_FORMAT", "false").lower() == "true":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized with level {level} and {'JSON' if use_json else 'text'} format.")
    return logger