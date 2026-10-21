"""How long things take in real use, from the timings stream.

    python scripts/timings_report.py data/logs/timings                # every step: count, median, p95, slowest
    python scripts/timings_report.py data/logs/timings <session_id>   # that chat, request by request, as a tree

On the server: ssh in, then run it from /opt/eloquence.
"""

import sys
from collections import defaultdict
from datetime import datetime

from _records import records


def pct(values, p):
    """The value p% of the way up the sorted list (nearest rank)."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def summary(spans):
    by_name = defaultdict(list)
    for s in spans:
        by_name[(s.get("depth", 0), s["name"])].append(s)
    print(f"{'step':<58}{'count':>7}{'median':>9}{'p95':>9}{'slowest':>9}{'failed':>8}   (ms)")
    for (depth, name), group in sorted(by_name.items()):
        ms = [s["ms"] for s in group]
        failed = sum(1 for s in group if not s.get("ok", True))
        label = ("  " * depth + name)[:57]
        print(f"{label:<58}{len(ms):>7}{pct(ms, 50):>9.0f}{pct(ms, 95):>9.0f}{max(ms):>9.0f}{failed:>8}")


def started(s):
    return datetime.fromisoformat(s["started"])


def tree(spans):
    by_request = defaultdict(list)
    for s in spans:
        by_request[s.get("request_id", "-")].append(s)
    for group in sorted(by_request.values(), key=lambda g: min(map(started, g))):
        print()
        for s in sorted(group, key=lambda s: (started(s), s.get("depth", 0))):
            extra = "" if s.get("ok", True) else "  FAILED"
            detail = " ".join(f"{k}={s[k]}" for k in ("route", "status", "provider", "model", "answered") if k in s)
            print(f"{'  ' * s.get('depth', 0)}{s['ms']:>8.0f} ms  {s['name']}  {detail}{extra}")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    spans = [s for s in records(argv[0], "timings ") if {"name", "ms", "started"} <= s.keys()]
    if len(argv) > 1:
        spans = [s for s in spans if s.get("session_id") == argv[1]]
    if not spans:
        sys.exit("no timings found")
    (tree if len(argv) > 1 else summary)(spans)


if __name__ == "__main__":
    main(sys.argv[1:])
