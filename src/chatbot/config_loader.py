"""YAML configuration loader utilities.

Centralizes configuration loading from YAML files for signals, analysis parameters, and product configs.
"""

import yaml
from pathlib import Path
from functools import lru_cache


# Get config directory path (src/config - adjacent to chatbot package)
# Config is now in src/config, one level up from current module
CONFIG_DIR = Path(__file__).parent.parent / "config"

# Required top-level keys in signals.yaml — guards against silent YAML typos
_REQUIRED_SIGNAL_KEYS = {
    "commitment", "objection", "walking", "impatience",
    "low_intent", "high_intent", "guarded", "demand_directness",
    "direct_info_requests", "soft_positive", "validation_phrases",
}


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
        
    Raises:
        ValueError: If any required signal keys are missing
    """
    signals = load_yaml("signals.yaml")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing required keys: {sorted(missing)}")
    return signals


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

    Supports alias resolution: if product_type is not a direct key,
    checks each product's 'aliases' list for a match.

    Args:
        product_type: Product identifier string (canonical key or alias)

    Returns:
        dict: {"strategy": str, "context": str, ...}
    """
    config = load_product_config()
    products = config["products"]

    # Direct match (O(1) dict lookup)
    if product_type in products:
        return products[product_type]

    # Alias resolution: check each product's aliases list
    for _key, settings in products.items():
        if product_type in settings.get("aliases", []):
            return settings

    return config["default"]
