"""Rebuild config/real_objections.json from the Fathom call vault.

Reads the vault only, never writes to it. Run again after new calls land:
    python scripts/build_real_calls.py
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.loader import CONFIG_DIR, load_buyer_config  # noqa: E402
from core.real_calls import extract_objections  # noqa: E402


def main() -> None:
    cfg = load_buyer_config()["real_objections"]
    vault = (ROOT / cfg["vault_dir"]).resolve()
    with open(vault / "grwth" / "extracted.json", encoding="utf-8") as f:
        extracted = json.load(f)
    with open(vault / "call-index.csv", encoding="utf-8", newline="") as f:
        index_rows = list(csv.DictReader(f))

    pool = extract_objections(extracted, index_rows, cfg["type_map"])
    if not pool:
        sys.exit("No usable objections found in the vault - nothing written.")
    out = CONFIG_DIR / cfg["file"]
    out.write_text(json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(pool)} real objections to {out}")


if __name__ == "__main__":
    main()
