"""Load and cache YAML configuration files"""

import copy
import json
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

@lru_cache(maxsize=16)
def _load_yaml_cached(filename):
    """Load and cache YAML from CONFIG_DIR. Raises FileNotFoundError if missing."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(filename):
    """Return a cached YAML snapshot as a deep copy.

    The underlying parse result stays cached, but callers receive their own copy so
    accidental in-place mutations cannot leak across modules.
    """
    return copy.deepcopy(_load_yaml_cached(filename))


@lru_cache(maxsize=1)
def load_product_config():
    """Load product_config.yaml."""
    return load_yaml("product_config.yaml")


@lru_cache(maxsize=1)
def load_prospect_config():
    """Load prospect_config.yaml."""
    return load_yaml("prospect_config.yaml")


@lru_cache(maxsize=1)
def load_real_objections():
    """Real-call objection pool, or [] when disabled or not built yet."""
    cfg = load_prospect_config().get("real_objections", {})
    path = CONFIG_DIR / cfg.get("file", "")
    if not cfg.get("enabled") or not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
