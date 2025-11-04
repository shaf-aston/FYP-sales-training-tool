"""
Configuration module for the Sales Roleplay Chatbot

This module provides configuration settings and utilities:
- settings.py: Main application settings (CORS, API keys, database)
- model_config.py: AI model configuration and switching between base/trained models
"""

from .settings import *
from .model_config import get_active_model_config, get_training_config

__all__ = [
    'get_active_model_config',
    'get_training_config',
]