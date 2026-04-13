"""Thread-safe JSONL writer with line-count rotation."""

import json
import logging
import os
from threading import Lock

logger = logging.getLogger(__name__)


class JSONLWriter:
    """Append-only JSONL writer with line-count rotation."""

    def __init__(self, filepath: str, max_lines: int, keep_after_rotation: int):
        self.filepath = filepath
        self.max_lines = max_lines
        self.keep = keep_after_rotation
        self.file_lock = Lock()
        self.line_count: int = -1  # -1 = not yet counted

    def get_line_count(self) -> int:
        if self.line_count < 0:
            try:
                if os.path.exists(self.filepath):
                    with open(self.filepath, "r") as f:
                        self.line_count = sum(1 for _ in f)
                else:
                    self.line_count = 0
            except Exception:
                self.line_count = 0
        return self.line_count

    def append(self, record: dict) -> None:
        """Append a JSON record, rotating if file exceeds max_lines."""
        with self.file_lock:
            try:
                if self.get_line_count() >= self.max_lines and os.path.exists(self.filepath):
                    with open(self.filepath, "r") as f:
                        lines = f.readlines()
                    tail = lines[-self.keep :]
                    with open(self.filepath, "w") as f:
                        f.writelines(tail)
                    self.line_count = len(tail)

                with open(self.filepath, "a") as f:
                    f.write(json.dumps(record) + "\n")
                if self.line_count >= 0:
                    self.line_count += 1
            except Exception as e:
                logger.warning("Failed to write JSONL record to %s: %s", self.filepath, e)

    def read_all(self) -> list[dict]:
        """Read and parse all records."""
        records = []
        with self.file_lock:
            try:
                with open(self.filepath, "r") as f:
                    for line in f:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
        return records

    def read_filtered(self, key: str, value: str) -> list[dict]:
        return [r for r in self.read_all() if r.get(key) == value]
