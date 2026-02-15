"""YAML configuration loader utilities.

Centralizes configuration loading from YAML files for signals, analysis parameters, and product configs.
"""

import yaml
from pathlib import Path
from functools import lru_cache


# Get config directory path (project root / config)
# Find project root by looking for requirements.txt
def _find_project_root():
    """Find project root directory by looking for requirements.txt."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "requirements.txt").exists():
            return current
        current = current.parent
    # Fallback: assume we're in src/chatbot and go up 2 levels
    return Path(__file__).parent.parent.parent


CONFIG_DIR = _find_project_root() / "config"


@lru_cache(maxsize=None)
def load_yaml(filename):
    """Load and cache YAML configuration file.
    
    Args:
        filename: Name of YAML file in config directory
        
    Returns:
        dict: Parsed YAML content
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    filepath = CONFIG_DIR / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def load_signals():
    """Load behavioral signal keywords from signals.yaml.
    
    Returns:
        dict: Signal keyword mappings
    """
    return load_yaml("signals.yaml")


@lru_cache(maxsize=None)
def load_analysis_config():
    """Load analysis configuration from analysis_config.yaml.
    
    Returns:
        dict: Analysis thresholds and parameters
    """
    return load_yaml("analysis_config.yaml")


@lru_cache(maxsize=None)
def load_product_config():
    """Load product configuration from product_config.yaml.
    
    Returns:
        dict: Product type to strategy/context mappings
    """
    return load_yaml("product_config.yaml")


def get_product_settings(product_type):
    """Get configuration for a specific product type.
    
    Args:
        product_type: Product identifier string
        
    Returns:
        dict: {"strategy": str, "context": str}
    """
    config = load_product_config()
    return config["products"].get(product_type, config["default"])


def reload_configs():
    """Clear all cached configurations to force reload.
    
    Useful for development/testing when YAML files are modified.
    """
    load_yaml.cache_clear()
    load_signals.cache_clear()
    load_analysis_config.cache_clear()
    load_product_config.cache_clear()
