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
  Updates the VM, redeploys Vercel, then checks `/api/health` reports the new commit.
  Skips itself until the setup below is done. Manual run: Actions → deploy → Run workflow.

## One-time setup

### 1. Protect `master` (GitHub → Settings → Branches → Add rule)
- Require a pull request before merging
- Require status checks: `python`, `web`
- Block force pushes

### 2. Secrets and variables (GitHub → Settings → Secrets and variables → Actions)

| Name | Kind | Value |
|---|---|---|
| `VM_HOST` | secret | VM address |
| `VM_USER` | secret | SSH user |
| `VM_SSH_KEY` | secret | private key the VM accepts |
| `VERCEL_TOKEN` | secret | vercel.com/account/tokens → Create (scope: ShafBiz team) |
| `VM_APP_DIR` | variable | repo folder on the VM |
| `VM_RESTART` | variable | restart command, e.g. `sudo systemctl restart sales-bot` |
| `SITE_URL` | variable | e.g. `https://your-app.vercel.app` |

### 3. Vercel
Settings → Git → Production Branch = `master`.

### 4. Netlify (not used)
`netlify.toml` tells the linked Netlify site to skip every build, so it no longer fails PR checks.
To remove it completely: Netlify → fyp-sales → Site configuration → Build & deploy → Unlink repository
(or delete the site), then delete `netlify.toml`.
