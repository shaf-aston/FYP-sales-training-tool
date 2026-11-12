#!/usr/bin/env bash
# Install (or refresh) the nightly database backup as a systemd timer: eloquence-backup.timer runs
# scripts/backup_db.py at 03:15 as the app's user. Safe to run again; deploy_vm.sh runs it on every deploy.
# Run from the app folder on the VM:  bash scripts/install_backup.sh
set -euo pipefail

APP_DIR=$(pwd)
PY=${VENV:-$APP_DIR/.venv}/bin/python
RUN_AS=${RUN_AS:-$(stat -c %U "$APP_DIR")}
UNITS=${UNITS:-/etc/systemd/system}
SUDO=${SUDO-sudo -n}

service="[Unit]
Description=Back up the Eloquence accounts database

[Service]
Type=oneshot
User=$RUN_AS
WorkingDirectory=$APP_DIR
ExecStart=$PY $APP_DIR/scripts/backup_db.py
"
timer="[Unit]
Description=Nightly Eloquence database backup

[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"

changed=0
write() {   # write a unit file only when it differs, so a deploy with no change reloads nothing
  if [ "$(cat "$UNITS/$1" 2>/dev/null)" != "$(printf '%s' "$2")" ]; then
    printf '%s' "$2" | $SUDO tee "$UNITS/$1" > /dev/null
    changed=1
  fi
}
write eloquence-backup.service "$service"
write eloquence-backup.timer "$timer"
if [ "$changed" = 1 ]; then
  $SUDO systemctl daemon-reload
  echo "backup: timer units written"
fi
$SUDO systemctl enable --now -q eloquence-backup.timer
echo "backup: $(systemctl show -p NextElapseUSecRealtime --value eloquence-backup.timer 2>/dev/null || echo scheduled)"
