"""Helpers for loading provider modules with non-standard filenames."""

from __future__ import annotations

from functools import lru_cache
from importlib import util
from pathlib import Path
from types import ModuleType


@lru_cache(maxsize=None)
def load_module_from_path(module_name: str, file_path: str) -> ModuleType:
    path = Path(file_path)
    spec = util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")

    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
