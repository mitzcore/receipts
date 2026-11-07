#!/usr/bin/env bash
# What happens to Ledgerline between two questionnaires. Run it after the
# Harbor Bank run and before Clearwater, to test whether team memory notices.
#   1. a regression: a later cost review cuts backup retention to 14 days
#   2. an improvement: Okta Verify is now enforced for contractors, and the
#      temporary password-only rule is gone
set -euo pipefail
cd "$(dirname "$0")/../company"
python3 - <<'PY'
import json, pathlib, re
rds = pathlib.Path("infra/terraform/rds.tf")
rds.write_text(re.sub(r"backup_retention_period = \d+[^\n]*", "backup_retention_period = 14 # 2026-11 cost review again (PLAT-511)", rds.read_text()))
okta_p = pathlib.Path("idp/okta-policies.json")
okta = json.loads(okta_p.read_text())
okta["sign_on_policies"] = [p for p in okta["sign_on_policies"] if p["name"] != "Contractor onboarding (temporary)"]
okta["sign_on_policies"][0]["conditions"]["people"]["groups"]["include"] = ["Employees", "Contractors"]
okta["exported_at"] = "2026-11-12T09:00:00Z"
okta_p.write_text(json.dumps(okta, indent=2) + "\n")
print("drift applied: backups -> 14 days; contractors now on Workforce MFA")
PY
