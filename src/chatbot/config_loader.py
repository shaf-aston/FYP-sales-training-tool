"""YAML configuration loader utilities.

Centralizes configuration loading from YAML files for signals, analysis parameters, and product configs.
"""

import yaml
from pathlib import Path
from functools import lru_cache


CONFIG_DIR = Path(__file__).parent.parent / "config"

# Required top-level keys in signals.yaml — guards against silent YAML typos
_REQUIRED_SIGNAL_KEYS = {
    "commitment", "objection", "walking", "impatience",
    "low_intent", "high_intent", "guarded", "demand_directness",
    "direct_info_requests", "soft_positive", "validation_phrases",
}


@lru_cache(maxsize=None)
def load_yaml(filename):
    """Load and cache a YAML file from CONFIG_DIR. Raises on missing file or parse error."""
    filepath = CONFIG_DIR / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def load_signals():
    """Load signals.yaml and validate required keys are present."""
    signals = load_yaml("signals.yaml")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing required keys: {sorted(missing)}")
    return signals


@lru_cache(maxsize=None)
def load_analysis_config():
    return load_yaml("analysis_config.yaml")


@lru_cache(maxsize=None)
def load_product_config():
    return load_yaml("product_config.yaml")


@lru_cache(maxsize=1)
def _build_alias_map():
    """Pre-compute alias→settings map for O(1) alias lookup."""
    config = load_product_config()
    alias_map = {}
    for settings in config["products"].values():
        for alias in settings.get("aliases", []):
            alias_map[alias] = settings
    return alias_map


def get_product_settings(product_type):
    """Return product config for the given type or alias. Falls back to default."""
    config = load_product_config()
    products = config["products"]
    
    # Direct match in products
    if product_type in products:
        return products[product_type]
    
    # Try alias lookup
    aliased = _build_alias_map().get(product_type)
    if aliased:
        return aliased
    
    # Fallback to default (inside products dict)
    if "default" in products:
        return products["default"]
    
    # If no default exists, raise error
    raise ValueError(f"Product type '{product_type}' not found and no default config available")

