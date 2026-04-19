"""Normalize existing JSON session files into the canonical session schema.

Usage: run from the repository root with Python. This script is conservative and
moves invalid files into `sessions/invalid/` for inspection.
"""

import json
from pathlib import Path
import shutil
import sys


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = repo_root()
    sessions = root / "sessions"
    if not sessions.exists():
        print("No sessions/ folder found; nothing to migrate.")
        return 0

    invalid = sessions / "invalid"
    invalid.mkdir(exist_ok=True)

    for p in sessions.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            print(f"Invalid JSON {p.name}: {exc}; moving to invalid/")
            shutil.move(str(p), str(invalid / p.name))
            continue

        # Basic normalization: ensure required keys
        changed = False
        if "session_id" not in data:
            data["session_id"] = p.stem
            changed = True
        if "created_at" not in data:
            data["created_at"] = p.stat().st_mtime
            changed = True
        if "turns" not in data or not isinstance(data.get("turns"), list):
            data["turns"] = []
            changed = True
        if "finalised" not in data:
            data["finalised"] = False
            changed = True

        if changed:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            print(f"Normalized {p.name}")

    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
