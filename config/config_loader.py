import json
from pathlib import Path

class Config:
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):
        config_path = Path(__file__).parent / "../model_config.json"
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
            if config_path.exists():
                loaded = json.load(open(config_path))
                # Deep merge for nested dicts
                def deep_merge(d1, d2):
                    for k, v in d2.items():
                        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                            deep_merge(d1[k], v)
                        else:
                            d1[k] = v
                    return d1
                cls._config = deep_merge(default_config.copy(), loaded)
            else:
                cls._config = default_config
        except Exception:
            cls._config = default_config

    @classmethod
    def get(cls, key_path, default=None):
        if cls._config is None:
            cls._load_config()

        value = cls._config
        for key in key_path.split('.'):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    @classmethod
    def reload(cls):
        cls._load_config()

config = Config()
