"""Archive sessions older than configured retention days.

Creates `archive/sessions_YYYYMMDD.zip` and removes archived files from `sessions/`.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import zipfile


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_retention(root: Path) -> int:
    cfg = root / "src" / "config" / "session_config.yaml"
    if cfg.exists():
        try:
            import yaml
            data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "retention_days" in data:
                return int(data["retention_days"])
        except Exception:
            pass
    return 90


def main() -> None:
    root = repo_root()
    sessions = root / "sessions"
    if not sessions.exists():
        print("No sessions/ folder found; nothing to archive.")
        return

    retention = load_retention(root)
    cutoff = datetime.utcnow() - timedelta(days=retention)
    to_archive = []
    for p in sessions.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            created = data.get("created_at")
            if isinstance(created, str):
                try:
                    created_dt = datetime.fromisoformat(created)
                except Exception:
                    created_dt = datetime.utcfromtimestamp(p.stat().st_mtime)
            else:
                created_dt = datetime.utcfromtimestamp(p.stat().st_mtime)
        except Exception:
            created_dt = datetime.utcfromtimestamp(p.stat().st_mtime)

        if created_dt < cutoff:
            to_archive.append(p)

    if not to_archive:
        print("No sessions to archive.")
        return

    archive_dir = root / "archive"
    archive_dir.mkdir(exist_ok=True)
    fname = archive_dir / f"sessions_archive_{datetime.utcnow().strftime('%Y%m%d')}.zip"
    with zipfile.ZipFile(fname, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in to_archive:
            zf.write(p, arcname=p.name)
            p.unlink()

    print(f"Archived {len(to_archive)} sessions to {fname}")


if __name__ == "__main__":
    main()
