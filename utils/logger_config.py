# Centralized logging setup for the AI Sales Training Chatbot

import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging(logs_dir: Path, logger_name: str = "fitness_chatbot"):
  """Setup centralized logging configuration"""
  
  # Fix Windows console encoding for emojis
  if sys.platform == "win32":
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

  # Ensure logs directory exists
  try:
    logs_dir.mkdir(parents=True, exist_ok=True)
  except Exception:
    pass

  # Configure logging handlers
  file_handler = RotatingFileHandler(
    logs_dir / "chatbot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
  )
  log_handlers = [file_handler]

  # Add console handler if UTF-8 is supported
  try:
    if sys.platform == "win32":
      sys.stdout.reconfigure(encoding='utf-8')
      sys.stderr.reconfigure(encoding='utf-8')
    log_handlers.append(logging.StreamHandler())
  except:
    pass

  # Setup logging configuration
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
  )
  
  return logging.getLogger(logger_name)