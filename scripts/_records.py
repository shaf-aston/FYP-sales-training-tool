"""Read log records from a stream folder (data/logs/events), one .jsonl file, a server log, or `-` for stdin."""

import json
import sys
from pathlib import Path


def records(source: str, mark: str):
    """Yield each JSON record. Server-log lines are read from just after `mark` (e.g. "events ")."""
    path = Path(source)
    if source == "-":
        files = [sys.stdin]
    elif path.is_dir():
        files = [p.open(encoding="utf-8") for p in sorted(path.glob("*.jsonl"))]
    else:
        files = [path.open(encoding="utf-8")]
    for f in files:
        for line in f:
            text = line.split(mark, 1)[1] if mark in line else line
            try:
                yield json.loads(text)
            except ValueError:
                continue  # not a record
