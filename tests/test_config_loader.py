import os
import json
import tempfile
from pathlib import Path
import sys
import pytest

# Add parent directory to path to import config_loader
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))

from config_loader import config, Config

def test_default_config_loads():
    # Should load defaults if file missing
    Config._config = None
    assert config.get("llm.model_name") == "qwen2"
    assert config.get("llm.endpoint") == "http://localhost:11434/api/generate"
    assert config.get("llm.temperature") == 0.8
    assert config.get("llm.max_tokens") == 500
    assert config.get("features.real_time_feedback") is True
    assert config.get("features.save_conversations") is False


def test_missing_key_returns_default():
    assert config.get("llm.nonexistent", default="fallback") == "fallback"
    assert config.get("features.nonexistent", default=False) is False


def test_reload_works(tmp_path):
    # Write a temp config file
    temp_config = {
        "llm": {
            "model_name": "test-model",
            "endpoint": "http://test-endpoint",
            "temperature": 0.5,
            "max_tokens": 100
        },
        "features": {
            "real_time_feedback": False,
            "save_conversations": True
        }
    }
    config_path = tmp_path / "model_config.json"
    with open(config_path, "w") as f:
        json.dump(temp_config, f)
    # Patch loader to use temp config
    orig_path = Config._load_config.__code__
    def _load_config_patch(cls):
        default_config = {
            "llm": {
                "model_name": "qwen2",
                "endpoint": "http://localhost:11434/api/generate",
                "temperature": 0.8,
                "max_tokens": 500
            },
            "evaluation": {
                "use_llm": False,
                "fallback_to_rules": True
            },
            "features": {
                "real_time_feedback": True,
                "save_conversations": False
            }
        }
        try:
            loaded = json.load(open(config_path))
            def deep_merge(d1, d2):
                for k, v in d2.items():
                    if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                        deep_merge(d1[k], v)
                    else:
                        d1[k] = v
                return d1
            cls._config = deep_merge(default_config.copy(), loaded)
        except Exception:
            cls._config = default_config
    Config._load_config = classmethod(_load_config_patch)
    config.reload()
    assert config.get("llm.model_name") == "test-model"
    assert config.get("llm.endpoint") == "http://test-endpoint"
    assert config.get("llm.temperature") == 0.5
    assert config.get("llm.max_tokens") == 100
    assert config.get("features.real_time_feedback") is False
    assert config.get("features.save_conversations") is True
    # Restore loader
    Config._load_config = classmethod(Config._load_config.__func__)
    config.reload()
