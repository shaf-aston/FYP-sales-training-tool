#!/usr/bin/env bash
# Stop hook: Claude may only stop when the work is verified.
#   1. no uncommitted changes   2. every commit pushed   3. the full test suite passed on this exact commit
# The suite (~7 min) runs once per commit; a pass is remembered by commit id.
# Safety valve: after 5 blocks in a row Claude may stop anyway (it may be waiting on the user), and says why.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 0
state=.claude/hooks/.state; mkdir -p "$state"
input=$(cat)

block() {
  n=$(( $(cat "$state/blocks" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$state/blocks"
  if [ "$n" -gt 5 ]; then
    rm -f "$state/blocks"
    printf '{"systemMessage": "Stop check still failing after 5 tries (%s). Stopping so you can decide."}\n' "$1"
    exit 0
  fi
  printf '{"decision": "block", "reason": "Not finished: %s. Fix it, verify, then stop. (If you are truly blocked on the user, say exactly what you need.)"}\n' "$1"
  exit 0
}

[ -z "$(git status --porcelain)" ] || block "uncommitted changes ($(git status --porcelain | wc -l) files) - commit and push them"

branch=$(git rev-parse --abbrev-ref HEAD)
git fetch -q origin "$branch" 2>/dev/null
ahead=$(git rev-list --count "origin/$branch..HEAD" 2>/dev/null || echo 1)
[ "$ahead" = 0 ] || block "$ahead commit(s) not pushed to origin/$branch - push them"

head=$(git rev-parse HEAD)
if [ "$(cat "$state/passed" 2>/dev/null)" != "$head" ]; then
  if timeout 560 python -m pytest -q -x -p no:cacheprovider > "$state/pytest.log" 2>&1; then
    echo "$head" > "$state/passed"
  else
    block "tests fail on $head: $(tail -1 "$state/pytest.log" | tr '"' "'") - see .claude/hooks/.state/pytest.log"
  fi
fi

rm -f "$state/blocks"
echo '{"systemMessage": "Verified: tree clean, pushed, full test suite passed on this commit."}'
