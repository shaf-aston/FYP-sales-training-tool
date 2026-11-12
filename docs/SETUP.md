# Setup and workflow

## Everyday commands

| Command | What it does |
|---|---|
| `make setup` | Install Python + web dependencies |
| `make check` | Run everything CI runs |
| `make test-real` | Script tests with the real embedding model |
| `make dev` | Run the API locally |

## How a change reaches users

branch → PR (template: problem, fix, proof, risk) → **ci** green → merge to `master` → **deploy** → live check

- **ci** (`.github/workflows/ci.yml`): Python lint + tests, web check + build. Runs on every PR.
- **deploy** (`.github/workflows/deploy.yml`): runs only after ci passes on `master`.
  Updates the VM with `scripts/deploy_vm.sh`, redeploys Vercel, then checks `/api/health` reports the new commit.
  On the VM the script installs packages when `requirements.txt` changed, restarts, waits for the new commit
  on `/api/health`, and rolls back to the previous commit if it does not come up (the run then fails).
  It refuses to touch a VM checkout with local changes or one that has diverged from `master`.
  Skips itself until the setup below is done. Manual run: Actions → deploy → Run workflow.

## One-time setup

### 1. Protect `master` (GitHub → Settings → Branches → Add rule)
- Require a pull request before merging
- Require status checks: `python`, `web`
- Block force pushes

### 2. Secrets and variables (GitHub → Settings → Secrets and variables → Actions)

| Name | Kind | Value |
|---|---|---|
| `VM_HOST` | secret | `140.238.102.50` |
| `VM_USER` | secret | `ubuntu` |
| `VM_SSH_KEY` | secret | private key the VM accepts (an authorized `authorized_keys` entry for `ubuntu`) |
| `VERCEL_TOKEN` | secret | vercel.com/account/tokens → Create (scope: ShafBiz team) |
| `VM_APP_DIR` | variable | `/opt/eloquence` (git repo, runs as `eloquence.service`) |
| `VM_RESTART` | variable | `sudo systemctl restart eloquence` (`ubuntu` has passwordless sudo) |
| `SITE_URL` | variable | `https://eloquence-sales.vercel.app` |

The VM runs the API via gunicorn on `127.0.0.1:8000` under systemd unit `eloquence.service`.
Its `.env` must have `TRUST_PROXY_HEADERS=1`: the API sits behind Caddy (and Vercel for the website), so without
it every visitor looks like `127.0.0.1` and shares one rate limit. With it the visitor is Vercel's `X-Real-IP`, and
each connecting address (the last `X-Forwarded-For` entry, written by Caddy) also gets a looser limit of its own.

**Backups.** Every deploy installs `eloquence-backup.timer` (`scripts/install_backup.sh`): at 03:15 it copies the
accounts database to `data/backups/eloquence-<date>.db` and keeps the newest 7 (`limits.yaml` `backups.keep`).
`systemctl list-timers eloquence-backup.timer` shows the next run. To restore one (the API must be stopped):
`sudo systemctl stop eloquence && .venv/bin/python scripts/backup_db.py restore data/backups/eloquence-<date>.db && sudo systemctl start eloquence`.
The file it replaces is kept beside it as `eloquence.db.before`.
`vm-run.yml` (Actions → vm-run) runs any one command on the VM and prints its output.

Only the **deploy** workflow updates the VM, and only after CI passes. The VM used to also have
`eloquence-update.timer`, which pulled `master` every 10 minutes with no CI gate and no rollback.
It is disabled (the unit files are kept). Do not re-enable it; to switch it back on anyway:
`sudo systemctl enable --now eloquence-update.timer`.

### 3. Vercel
Settings → Git → Production Branch = `master`.
