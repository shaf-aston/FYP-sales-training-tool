"""Load YAML configuration from config/: each file is parsed once, and every caller gets its own copy."""

import copy
import json
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=None)
def _load_yaml_cached(filename):
    """Load and cache YAML from CONFIG_DIR. Raises FileNotFoundError if missing."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(filename):
    """A deep copy of the cached parse, so a caller's in-place change cannot leak into another module."""
    return copy.deepcopy(_load_yaml_cached(filename))


def load_buyer_products():
    """buyer_products.yaml: what the AI buyer knows about each product it can shop for."""
    return load_yaml("buyer_products.yaml")


def load_buyer_config():
    """buyer.yaml: the AI buyer's personas and behaviour, and sell-mode scoring."""
    return load_yaml("buyer.yaml")


@lru_cache(maxsize=1)
def load_real_objections():
    """Real-call objection pool, or [] when disabled or not built yet. Read-only: callers sample it."""
    cfg = load_buyer_config().get("real_objections", {})
    path = CONFIG_DIR / cfg.get("file", "")
    if not cfg.get("enabled") or not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
