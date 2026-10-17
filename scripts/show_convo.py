"""Print buy-mode conversations as readable transcripts, from the server log or the METRICS_JSONL_PATH file.

    python scripts/show_convo.py app.log                 # every session in the file
    python scripts/show_convo.py app.log <session_id>    # one session
    journalctl -u <service> | python scripts/show_convo.py - <session_id>

Each turn shows what the learner said, what the bot heard it as, where the script went, and the bot's line.
"""

import json
import sys
from collections import defaultdict

MARK = "session_analytics "


def events(lines):
    for line in lines:
        text = line.split(MARK, 1)[1] if MARK in line else line
        try:
            yield json.loads(text)
        except ValueError:
            continue  # not an analytics line


def show(session_id, turns):
    print(f"\n=== session {session_id} ===")
    for e in turns:
        if e.get("user_message"):
            print(f"\n  you : {e['user_message']}")
            print(f"        heard as {e.get('heard_as', '?')}, step {e.get('step_from', '?')} -> {e.get('step_to', '?')}")
        print(f"  bot : {e.get('assistant_message', '')}")
        if e.get("saved"):
            print(f"        saved so far: {e['saved']}")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    source = sys.stdin if argv[0] == "-" else open(argv[0], encoding="utf-8")
    wanted = argv[1] if len(argv) > 1 else None
    by_session = defaultdict(list)
    for e in events(source):
        if e.get("event_type") == "conversation_turn" and (not wanted or e.get("session_id") == wanted):
            by_session[e["session_id"]].append(e)
    if not by_session:
        sys.exit("no conversation turns found")
    for sid, turns in by_session.items():
        show(sid, turns)


if __name__ == "__main__":
    main(sys.argv[1:])
