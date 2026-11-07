#!/usr/bin/env bash
# Run the Harbor Bank demo end to end against a running Switch + Mattermost:
# resets the fixture, starts the scripted people, waits for Maya's sign-off,
# then scores the export with the outside judge.
#   demo/.env must hold MM_URL, MM_TEAM and the three people's tokens (see demo/env.example).
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/reset-demo.sh
python3 demo/actors.py
python3 eval/score.py out/harbor-bank/harbor-bank-answers.csv || true
git --no-pager diff --stat -- company/
