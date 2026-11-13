#!/usr/bin/env bash
# Update the VM to origin/master, restart the API, and roll back if it does not come up.
# Run from the app folder on the VM:  bash scripts/deploy_vm.sh "<restart command>"
# The deploy workflow runs it over SSH. Env overrides (for tests): HEALTH_URL, VENV.
set -uo pipefail

RESTART=${1:?usage: deploy_vm.sh "<restart command>"}
HEALTH_URL=${HEALTH_URL:-http://127.0.0.1:8000/api/health}
PY=${VENV:-.venv}/bin/python
TRIES=${TRIES:-30}

say() { echo "deploy: $*"; }
fail() { echo "::error title=VM deploy::$*"; exit 1; }

# Install packages only when requirements.txt differs between two commits.
deps() {
  if git diff --quiet "$1" "$2" -- requirements.txt; then return 0; fi
  say "requirements.txt changed, installing"
  "$PY" -m pip install -q -r requirements.txt
}

# Wait until /api/health reports the given commit.
live_on() {
  local v=""
  for _ in $(seq 1 "$TRIES"); do
    v=$("$PY" -c 'import json,sys,urllib.request as u; print(json.load(u.urlopen(sys.argv[1], timeout=3))["version"])' "$HEALTH_URL" 2>/dev/null || true)
    [ "$v" = "$1" ] && return 0
    sleep 2
  done
  say "API reports '${v:-nothing}', expected $1"
  return 1
}

[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "VM checkout has local changes; not touching it"

old=$(git rev-parse HEAD)
git fetch -q origin master || fail "git fetch failed"
git checkout -q master || fail "git checkout master failed"
git merge -q --ff-only origin/master || fail "VM master has diverged from origin/master"
new=$(git rev-parse HEAD)
say "${old:0:7} -> ${new:0:7}"

if deps "$old" "$new" && bash -c "$RESTART" && live_on "$new"; then
  say "API live on ${new:0:7}"
  # the nightly database backup; a problem here is reported but never undoes a good deploy
  [ -n "${SKIP_BACKUP_TIMER:-}" ] || bash scripts/install_backup.sh \
    || echo "::warning title=Backup timer::could not install the nightly backup timer"
  # ffmpeg splits recordings past 25 MB; without it they are refused as too big, so a failure here is only a warning
  [ -n "${SKIP_FFMPEG_INSTALL:-}" ] || bash scripts/install_ffmpeg.sh \
    || echo "::warning title=ffmpeg::could not install ffmpeg; recordings over 25 MB will be refused"
  # the voice and dictation models (120 MB + 660 MB, once); without them Groq or the browser does it instead
  [ -n "${SKIP_VOICE_FETCH:-}" ] || "$PY" -c "from core.infra.providers.speech import fetch_files as a; from core.infra.providers.dictation import fetch_files as b; a(); b()" \
    || echo "::warning title=Voice::could not fetch the voice models; speech falls back to Groq or the browser"
  # make the fixed lines ahead of time, detached and at the lowest priority (a live call always comes first); one at
  # a time, and a no-op once they are all made
  [ -n "${SKIP_VOICE_PREWARM:-}" ] || setsid nohup flock -n .cache/speech-prewarm.lock nice -n 19 \
    "$PY" -m scripts.speech_prewarm > .cache/speech-prewarm.log 2>&1 < /dev/null &
  exit 0
fi

[ "$old" = "$new" ] && fail "API is not healthy on ${new:0:7} (nothing to roll back to)"
say "rolling back to ${old:0:7}"
git reset -q --hard "$old"
if deps "$new" "$old" && bash -c "$RESTART" && live_on "$old"; then
  fail "new commit ${new:0:7} did not come up; rolled back, API is on ${old:0:7}"
fi
fail "new commit ${new:0:7} did not come up and the rollback to ${old:0:7} failed too"
