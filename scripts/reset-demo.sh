#!/usr/bin/env bash
# Put Ledgerline back the way it was before a demo run: the clerk may have
# applied Terraform fixes the owner approved, and `remember` appends to the
# answer library. Removes the Harbor Bank ledger so the run starts clean.
set -euo pipefail
cd "$(dirname "$0")/.."
git checkout -- company/
rm -rf out/harbor-bank out/clearwater-cu
echo "fixture reset; out/harbor-bank removed"
