"""Copy the accounts database to BACKUP_DIR, keeping the newest few (config/limits.yaml backups.keep).

    python scripts/backup_db.py                         # tonight's copy (the systemd timer runs this)
    python scripts/backup_db.py restore <copy.db>       # put a copy back; stop the server first

On the server: run it from /opt/eloquence with the app's Python (.venv/bin/python).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.accounts.backup import backup, restore  # noqa: E402
from core.accounts.db import backup_dir, db_path  # noqa: E402
from core.infra.constants import BACKUPS_KEEP  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        out = backup(db_path(), backup_dir(), BACKUPS_KEEP)
        print(f"backup: {out.name} ({out.stat().st_size} bytes), keeping {BACKUPS_KEEP}")
        return 0
    if argv[0] == "restore" and len(argv) == 2:
        restore(Path(argv[1]), db_path())
        print(f"restored {argv[1]} to {db_path()}; the old file is beside it as .before")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
