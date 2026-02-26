"""Centralized logging setup."""

import logging
import os
from pathlib import Path

def setup_logger(name: str, log_dir: str = "logs", level=logging.INFO) -> logging.Logger:
    """Set up logger with console and file output."""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_format)
    
    log_file = log_path / f"{name.replace('.', '_')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s")
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get or create logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger

