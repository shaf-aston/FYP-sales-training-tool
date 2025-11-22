import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(log_level=logging.INFO, log_file="app.log", max_bytes=5*1024*1024, backup_count=5):
    """Configures centralized logging for the application."""

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Create console handler and set level to debug
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Create file handler
    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Add formatter to handlers
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Prevent duplicate logs from propagating to the root logger
    logger.propagate = False

    logging.info("Centralized logging configured.")

# Example usage (can be called from main application entry point)
if __name__ == "__main__":
    # Ensure the log directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_level=logging.DEBUG, log_file=os.path.join(log_dir, "debug.log"))
    logging.debug("This is a debug message.")
    logging.info("This is an info message.")
    logging.warning("This is a warning message.")
    logging.error("This is an error message.")
    logging.critical("This is a critical message.")