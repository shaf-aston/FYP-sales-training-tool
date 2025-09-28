import os
from pathlib import Path
from typing import Optional, Iterable
from paths import MODEL_CACHE_DIR

DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

def setup_model_env(model_name: Optional[str] = None, offline: bool = True) -> str:
    """Configure environment variables for local (offline) model usage.

    Args:
        model_name: Optional explicit model name. Falls back to env or default.
        offline: If True, enforce offline flags so transformers won't attempt network calls.

    Returns:
        Resolved model name.
    """
    resolved = model_name or os.environ.get("MODEL_NAME", DEFAULT_MODEL)
    os.environ["MODEL_NAME"] = resolved
    # Point all HF caches to our local cache directory
    cache_path = str(MODEL_CACHE_DIR)
    os.environ["HF_HOME"] = cache_path
    os.environ["TRANSFORMERS_CACHE"] = cache_path
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return resolved

def _candidate_snapshot_dirs(base: Path, org: str, repo: str) -> Iterable[Path]:
    """Yield possible snapshot directories for a HF cached model."""
    # New HF cache style: models--org--repo/snapshots/<hash>
    prefix = base / f"models--{org}--{repo}" / "snapshots"
    if prefix.exists():
        for child in sorted(prefix.iterdir(), reverse=True):  # prefer latest
            if child.is_dir():
                yield child

def local_model_dir(model_name: Optional[str] = None) -> Path:
    """Return an existing local directory containing model artifacts.

    Supports both a simplified flattened directory (org--repo) and
    the Hugging Face snapshot layout (models--org--repo/snapshots/<hash>).
    If multiple snapshots exist, the most recent (lexicographically last) is returned.
    """
    name = model_name or os.environ.get("MODEL_NAME", DEFAULT_MODEL)
    org, repo = name.split("/", 1)
    # 1. Flattened legacy style
    flat = MODEL_CACHE_DIR / name.replace("/", "--")
    if flat.exists():
        return flat
    # 2. Snapshot style
    for snap in _candidate_snapshot_dirs(MODEL_CACHE_DIR, org, repo):
        # Heuristic: snapshot must contain config.json
        if (snap / "config.json").exists() or any(p.suffix in {".safetensors", ".bin"} for p in snap.iterdir()):
            return snap
    # 3. Not found – return the expected flattened path (for error context)
    return flat

def assert_model_present(model_name: Optional[str] = None) -> Path:
    """Validate that a locally cached model exists with required artifacts.

    Returns the resolved directory containing model files, or raises RuntimeError
    if not found / incomplete.
    """
    resolved = model_name or os.environ.get("MODEL_NAME", DEFAULT_MODEL)
    mdir = local_model_dir(resolved)
    if not mdir.exists():
        raise RuntimeError(
            f"Model directory '{mdir}' not found (expected flattened or snapshot layout).\n"
            f"Run: python scripts/download_model.py"
        )
    # Require at least config.json AND one weight/token file
    config_ok = any(p.name == "config.json" for p in mdir.iterdir() if p.is_file())
    weight_ok = any(p.suffix in {".safetensors", ".bin"} for p in mdir.iterdir() if p.is_file())
    tokenizer_ok = any(p.name in {"tokenizer.json", "tokenizer_config.json", "vocab.json"} for p in mdir.iterdir() if p.is_file())
    if not (config_ok and (weight_ok or tokenizer_ok)):
        raise RuntimeError(
            f"Model directory '{mdir}' is incomplete (config_ok={config_ok}, weight_ok={weight_ok}, tokenizer_ok={tokenizer_ok}).\n"
            "Re-run download: python scripts/download_model.py --force"
        )
    return mdir
