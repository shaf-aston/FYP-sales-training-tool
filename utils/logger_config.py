# Centralized logging setup for the AI Sales Training Chatbot

import os
import sys
import logging
from pathlib import Path

def setup_logging(logs_dir: Path, logger_name: str = "fitness_chatbot"):
  """Setup centralized logging configuration"""
  
  # Fix Windows console encoding for emojis
  if sys.platform == "win32":
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

  # Configure logging handlers
  log_handlers = [
    logging.FileHandler(logs_dir / "chatbot.log", encoding='utf-8'),
  ]

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