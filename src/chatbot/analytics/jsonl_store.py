"""Thread-safe JSONL file writer with automatic rotation.

Shared by performance.py and session_analytics.py to eliminate duplication.
"""

import json
import logging
import os
from threading import Lock

logger = logging.getLogger(__name__)


class JSONLWriter:
    """Append-only JSONL writer with line-count-based rotation.

    Tracks line count in memory (avoids re-reading file on every write).
    When max_lines is reached, keeps only the newest keep_after_rotation lines.
    """

    def __init__(self, filepath: str, max_lines: int, keep_after_rotation: int):
        self._filepath = filepath
        self._max_lines = max_lines
        self._keep = keep_after_rotation
        self._lock = Lock()
        self._line_count: int = -1  # -1 = uninitialized

    def _get_line_count(self) -> int:
        if self._line_count < 0:
            try:
                if os.path.exists(self._filepath):
                    with open(self._filepath, 'r') as f:
                        self._line_count = sum(1 for _ in f)
                else:
                    self._line_count = 0
            except Exception:
                self._line_count = 0
        return self._line_count

    def append(self, record: dict) -> None:
        """Append a JSON record, rotating if the file exceeds max_lines."""
        with self._lock:
            try:
                if self._get_line_count() >= self._max_lines and os.path.exists(self._filepath):
                    with open(self._filepath, 'r') as f:
                        lines = f.readlines()
                    keep = lines[-self._keep:]
                    with open(self._filepath, 'w') as f:
                        f.writelines(keep)
                    self._line_count = len(keep)

                with open(self._filepath, 'a') as f:
                    f.write(json.dumps(record) + '\n')
                if self._line_count >= 0:
                    self._line_count += 1
            except Exception as e:
                logger.warning("Failed to write JSONL record to %s: %s", self._filepath, e)

    def read_all(self) -> list[dict]:
        """Read and parse all records from the file."""
        records = []
        with self._lock:
            try:
                with open(self._filepath, 'r') as f:
                    for line in f:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
        return records

    def read_filtered(self, key: str, value: str) -> list[dict]:
        """Read records matching key==value."""
        return [r for r in self.read_all() if r.get(key) == value]
