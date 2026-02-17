"""Product-based flow configuration.

Loads FSM configuration from YAML files for easy modification.
"""

import os
from .config_loader import get_product_settings


def get_product_config(product_key):
    """Get flow configuration for product type.
    
    Args:
        product_key: Product type identifier
        
    Returns:
        dict: {"strategy": str, "context": str}
    """
    return get_product_settings(product_key)


def get_groq_model():
    """Fetch the Groq model name from environment variables."""
    return os.environ.get("GROQ_MODEL", "default-model")

