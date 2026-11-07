#!/usr/bin/env bash
# What happens to Ledgerline between two questionnaires. Run it after the
# Harbor Bank run and before Clearwater, to test whether team memory notices.
#   1. a regression: a later cost review cuts backup retention to 14 days
#   2. an improvement: Okta Verify is now enforced for contractors, and the
#      temporary password-only rule is deleted
# Edits are minimal, the way a real PR would make them.
set -euo pipefail
cd "$(dirname "$0")/../company"
python3 - <<'PY'
import pathlib, re
rds = pathlib.Path("infra/terraform/rds.tf")
rds.write_text(re.sub(r"backup_retention_period = \d+[^\n]*", "backup_retention_period = 14 # 2026-11 cost review again (PLAT-511)", rds.read_text()))
okta = pathlib.Path("idp/okta-policies.json")
t = okta.read_text()
t = t.replace('"exported_at": "2026-11-02T14:10:00Z"', '"exported_at": "2026-11-07T14:55:00Z"')
t = t.replace('"conditions": {"people": {"groups": {"include": ["Employees"]}}},', '"conditions": {"people": {"groups": {"include": ["Employees", "Contractors"]}}},', 1)
t = re.sub(r',\n    \{\n      "name": "Contractor onboarding \(temporary\)".*?\n    \}(?=\n  \])', "", t, flags=re.S)
okta.write_text(t)
print("drift applied: backups -> 14 days; contractors now on Workforce MFA")
PY
