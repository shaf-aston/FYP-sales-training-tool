"""Real buyer objections, taken from recorded sales calls (Fathom).

Pure logic only: turning the call vault's extracted data into a clean objection
pool, and picking a session's objections from that pool. File reading lives in
scripts/build_real_calls.py (writing) and core/loader.py (reading).
"""

import random
import re

# Lines told about a buyer ("She only got approved...", "when prospects say...")
# rather than said by one.
_REPORTED_SPEECH = re.compile(r"^(he|she|they|objection)\b|\bprospects?\b", re.IGNORECASE)
# Editor notes like "(role-play prospect)".
_EDITOR_NOTE = re.compile(r"\s*\([^)]*\)")


def extract_objections(extracted: dict, index_rows: list[dict], type_map: dict) -> list[dict]:
    """Return unique, buyer-voiced objections from calls marked included=yes.

    Objection types not in `type_map` are dropped, so "other" never reaches the buyer.
    """
    allowed = {row["file"] for row in index_rows if row.get("included") == "yes"}
    pool, seen = [], set()
    for item in extracted.get("obj", []):
        kind = type_map.get(item.get("type"))
        text = _EDITOR_NOTE.sub("", str(item.get("objection", ""))).strip()
        key = text.lower().rstrip(".!? ")
        if (
            item.get("file") not in allowed
            or not kind
            or not text
            or _REPORTED_SPEECH.match(text)
            or key in seen
        ):
            continue
        seen.add(key)
        pool.append({"type": kind, "text": text, "source": item["file"]})
    return pool


def pick_bank(pool: list[dict], session_id: str, size: int) -> list[dict]:
    """Pick `size` objections for one session, the same ones every time for that id."""
    return random.Random(session_id).sample(pool, min(size, len(pool)))
