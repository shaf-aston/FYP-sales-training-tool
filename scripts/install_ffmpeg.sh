#!/usr/bin/env bash
# Install ffmpeg, which cuts call recordings past the speech engine's 25 MB limit into parts (core/calls/audio_parts.py).
# Safe to run again: it does nothing when ffmpeg is already there. deploy_vm.sh runs it on every deploy.
# Run from the app folder on the VM:  bash scripts/install_ffmpeg.sh
set -euo pipefail

FFMPEG=${FFMPEG:-ffmpeg}   # the command to look for (tests point it elsewhere)
SUDO=${SUDO-sudo -n}

if command -v "$FFMPEG" > /dev/null; then
  echo "ffmpeg: already installed"
  exit 0
fi
# wait for unattended upgrades rather than fail on the package lock
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 update -q
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 install -y -q ffmpeg
echo "ffmpeg: installed"
