"""Consolidated model configuration and helper utilities.

This module centralizes model identifiers, generation/training presets and
helper functions to locate/validate locally cached models.
"""
import os
from pathlib import Path
from typing import Optional, Iterable
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
DEFAULT_MODEL = BASE_MODEL
USE_TRAINED_MODEL = os.environ.get("USE_TRAINED_MODEL", "0") == "1"
TRAINING_ENABLED = True
TRAINED_MODEL_PATH = PROJECT_ROOT / "training" / "models" / "sales_roleplay_model"

GENERATION_CONFIG = {
    "base_model": {
        "max_new_tokens": 200,
        "do_sample": True,
        "num_beams": 1,
        "temperature": 0.85,
        "repetition_penalty": 1.15,
        "pad_token_id": 151643,
        "eos_token_id": 151645,
    },
    "trained_model": {
        "max_new_tokens": 250,
        "do_sample": True,
        "num_beams": 1,
        "temperature": 0.9,
        "repetition_penalty": 1.2,
        "pad_token_id": 151643,
        "eos_token_id": 151645,
    },
}

CONTEXT_CONFIG = {
    "max_history_turns": 15,
    "context_window": 2048,
    "memory_retention": True,
    "persona_consistency": True,
    "creative_gaps": False,
    "user_prompt_weight": 0.9,
}

LANGCHAIN_CONFIG = {
    "max_new_tokens": 200,
    "temperature": 0.85,
    "repetition_penalty": 1.15,
    "memory_window": 10,
    "fallback_message": "I'm sorry, I'm having trouble responding right now. Could you try asking again?",
}


def get_active_model_config():
    """Return active model configuration dict.

    Uses trained model if `USE_TRAINED_MODEL` is set and the trained path exists.
    Otherwise returns config for the base model referring to the remote repo id.
    """
    if USE_TRAINED_MODEL and TRAINED_MODEL_PATH.exists():
        return {
            "model_path": str(TRAINED_MODEL_PATH),
            "model_type": "trained",
            "generation_config": GENERATION_CONFIG["trained_model"],
            "description": "Sales Roleplay Trained Model",
        }
    else:
        return {
            "model_path": BASE_MODEL,
            "model_type": "base",
            "generation_config": GENERATION_CONFIG["base_model"],
            "description": "Base Qwen Model (Optimized for Speed)",
        }


def get_training_config():
    """Return a dict describing the training pipeline configuration."""
    return {
        "enabled": TRAINING_ENABLED,
        "base_model": BASE_MODEL,
        "output_dir": str(PROJECT_ROOT / "training" / "models"),
        "training_data_dir": str(PROJECT_ROOT / "training" / "data"),
        "checkpoint_dir": str(PROJECT_ROOT / "training" / "checkpoints"),
        "logs_dir": str(PROJECT_ROOT / "training" / "logs"),
        "training_scripts": [
            str(PROJECT_ROOT / "training" / "core_pipeline" / "model_training.py"),
            str(PROJECT_ROOT / "training" / "core_pipeline" / "roleplay_training.py"),
            str(PROJECT_ROOT / "training" / "enhanced_training_coordinator.py"),
        ],
    }


try:
    from config.paths import MODEL_CACHE_DIR
except Exception:
    MODEL_CACHE_DIR = PROJECT_ROOT / "model_cache"


def _candidate_snapshot_dirs(base: Path, org: str, repo: str) -> Iterable[Path]:
    prefix = base / f"models--{org}--{repo}" / "snapshots"
    if prefix.exists():
        for child in sorted(prefix.iterdir(), reverse=True):
            if child.is_dir():
                yield child


def local_model_dir(model_name: Optional[str] = None) -> Path:
    """Return an existing local directory containing model artifacts."""
    name = model_name or os.environ.get("MODEL_NAME", BASE_MODEL)
    org, repo = name.split("/", 1)
    flat = MODEL_CACHE_DIR / name.replace("/", "--")
    if flat.exists():
        return flat
    for snap in _candidate_snapshot_dirs(MODEL_CACHE_DIR, org, repo):
        if (snap / "config.json").exists() or any(p.suffix in {".safetensors", ".bin"} for p in snap.iterdir()):
            return snap
    return flat


def assert_model_present(model_name: Optional[str] = None) -> Path:
    """Validate that a locally cached model exists with required artifacts.

    Raises RuntimeError with an actionable message if the model is missing or incomplete.
    Returns the resolved Path when successful.
    """
    resolved = model_name or os.environ.get("MODEL_NAME", BASE_MODEL)
    mdir = local_model_dir(resolved)
    if not mdir.exists():
        if os.getenv("HF_HUB_OFFLINE") == "1":
            raise RuntimeError(
                f"Model directory '{mdir}' not found (expected flattened or snapshot layout).\n"
                f"Run: python scripts/download_model.py"
            )
        else:
            logger.info("Model not found locally. Attempting to download...")
            try:
                from transformers import AutoModelForCausalLM

                AutoModelForCausalLM.from_pretrained(resolved, cache_dir=MODEL_CACHE_DIR)
                logger.info("Model downloaded successfully.")
            except Exception as e:
                raise RuntimeError(f"Failed to download model '{resolved}': {e}")
    files = [p for p in mdir.iterdir()] if mdir.exists() else []
    config_ok = any(p.name == "config.json" for p in files if p.is_file())
    weight_ok = any(p.suffix in {".safetensors", ".bin"} for p in files if p.is_file())
    tokenizer_ok = any(p.name in {"tokenizer.json", "tokenizer_config.json", "vocab.json"} for p in files if p.is_file())
    if not (config_ok and (weight_ok or tokenizer_ok)):
        raise RuntimeError(
            f"Model directory '{mdir}' is incomplete (config_ok={config_ok}, weight_ok={weight_ok}, tokenizer_ok={tokenizer_ok}).\n"
            "Re-run download: python scripts/download_model.py --force"
        )
    return mdir


if __name__ == "__main__":
    active_config = get_active_model_config()
    print("=" * 60)
    print("MODEL CONFIGURATION")
    print("=" * 60)
    print(f"\nActive Model: {active_config['model_type'].upper()}")
    print(f"   Path: {active_config['model_path']}")
    print(f"   Description: {active_config['description']}")
    print(f"\nGeneration Settings:")
    for key, value in active_config["generation_config"].items():
        print(f"   {key}: {value}")
