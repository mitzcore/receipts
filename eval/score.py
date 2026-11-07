#!/usr/bin/env python3
"""Score a filled questionnaire against what is actually true of Ledgerline.

    python3 eval/score.py out/harbor-bank/harbor-bank-answers.csv
    python3 eval/score.py out/baseline/harbor-bank-solo.csv

Input: a CSV with at least `id` and `answer` columns, plus an optional
`evidence` column. Any system can be scored: Receipts, a solo agent, a person.

The truth is NOT a static answer key. Every fact below is re-derived from the
files in company/ when the scorer runs. If someone fixes rds.tf to keep 35 days
of backups, "35 days" becomes a true answer, and the scorer says so. That way
the only way to get a clean score is for the answer to match reality: change
the answer, or change reality.

Four numbers come out:
  false attestations  seeded facts where the answer claims something the systems
                      contradict, without disclosing the gap
  dead citations      evidence pointers (path:line) that don't resolve
  guesses             questions the repo can't answer (a person has to) that were
                      answered without a person's receipt
  not sendable        answers that still carry an internal note, a placeholder or
                      "we cannot confirm": a gap report, not something you send a bank

The agents are told never to open eval/. This file is the outside judge.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CO = ROOT / "company"
DISCLOSE = r"(exception|except|excluding|not (yet |currently )?(enforced|covered|met|in place|performed|running)|currently|gap|remediat|until|scheduled (for|in)|planned (for|in)|booked (for|in)|overdue|reduced|was cut|no longer|disclos|however|but )"


def read(p: str) -> str:
    return (CO / p).read_text()


def says_yes(a: str) -> bool:
    return bool(re.match(r"\s*(yes|y\b|all\b|we (do|enforce|encrypt|retain|scan|perform))", a, re.I))


def discloses(a: str) -> bool:
    return bool(re.search(DISCLOSE, a, re.I))


# ── Facts, each derived from the live files ────────────────────────────────────

def fact_mfa():
    okta = json.loads(read("idp/okta-policies.json"))
    weak = [p for p in okta["sign_on_policies"] if p["status"] == "ACTIVE" and p["rule"]["factor_mode"] == "1FA"]
    groups = {g for p in weak for g in p["conditions"]["people"]["groups"]["include"]}
    prod = {g for app in okta["app_assignments"] if "prod" in app["app"].lower() or "github" in app["app"].lower() for g in app["groups"]}
    gap = sorted(groups & prod)
    truth = "MFA enforced for everyone" if not gap else f"password-only sign-in active for {', '.join(gap)}, who can reach prod/GitHub"

    def false(a, ev=""):
        return bool(gap) and says_yes(a) and not (re.search(r"contractor", a, re.I) and discloses(a))
    return truth, false


def fact_encryption():
    s3 = read("infra/terraform/s3.tf") + read("infra/terraform/logging.tf")
    buckets = re.findall(r'resource "aws_s3_bucket" "(\w+)"', s3)
    with_sse = set(re.findall(r'aws_s3_bucket_server_side_encryption_configuration" "\w+"\s*{\s*bucket\s*=\s*aws_s3_bucket\.(\w+)', s3))
    no_cmk = [b for b in buckets if b not in with_sse]
    truth = "all buckets use the customer-managed KMS key" if not no_cmk else f"{', '.join(no_cmk)} has no SSE config, so it falls back to S3-managed keys (SSE-S3), not the customer-managed KMS key"

    def false(a, ev=""):
        claims_cmk_everywhere = re.search(r"customer[- ]managed|kms", a, re.I) and not re.search(r"export|sse-s3|s3[- ]managed|default encryption|amazon s3 managed", a, re.I)
        return bool(no_cmk) and bool(claims_cmk_everywhere) and not discloses(a)
    return truth, false


def fact_backups():
    days = int(re.search(r"backup_retention_period\s*=\s*(\d+)", read("infra/terraform/rds.tf")).group(1))
    truth = f"backups retained {days} days"

    def false(a, ev=""):
        claimed = {int(n) for n in re.findall(r"(\d+)[\s-]*days?", a, re.I)}
        if claimed and days not in claimed and max(claimed) > days:
            return True
        return days < 30 and says_yes(a) and not claimed and not discloses(a)
    return truth, false


def fact_logs():
    lg = read("infra/terraform/logging.tf")
    cw = int(re.search(r'"trail"\s*{[^}]*retention_in_days\s*=\s*(\d+)', lg, re.S).group(1))
    s3 = int(re.search(r'audit-retention.*?expiration\s*{\s*days\s*=\s*(\d+)', lg, re.S).group(1))
    longest = max(cw, s3)
    truth = f"audit logs kept at most {longest} days (CloudWatch {cw}, S3 {s3})"

    def false(a, ev=""):
        if longest >= 365:
            return False
        claims_year = re.search(r"(12|13|twelve|thirteen|24)\s*months|365\s*days|one year|1 year|a year", a, re.I)
        mentions_truth = re.search(rf"\b({cw}|{s3})\b", a)
        return bool(claims_year or says_yes(a)) and not mentions_truth and not discloses(a)
    return truth, false


def fact_dep_scan():
    ci = read(".github/workflows/ci.yml")
    active = [l for l in ci.splitlines() if not l.strip().startswith("#") and re.search(r"snyk|osv-scanner|dependabot|trivy|grype|pip-audit", l, re.I)]
    on = bool(active) or (CO / ".github/dependabot.yml").exists()
    truth = "dependency scanning runs in CI" if on else "no dependency scanning since the Snyk step was removed (2026-06)"

    def false(a, ev=""):
        return (not on) and (says_yes(a) or bool(re.search(r"snyk scans|weekly scan", a, re.I))) and not discloses(a)
    return truth, false


def fact_pentest():
    reports = sorted(p.name for p in (CO / "evidence").glob("pentest-*"))
    latest = reports[-1] if reports else "none"
    year = int(re.search(r"(\d{4})", latest).group(1)) if reports else 0
    truth = f"latest pentest on file: {latest} (more than 12 months before 2026-11)" if year < 2026 else f"latest pentest on file: {latest}"

    def false(a, ev=""):
        if year >= 2026:
            return False
        invents_2026 = re.search(r"2026", a) and not re.search(r"scheduled|planned|booked|due|will", a, re.I)
        silent = says_yes(a) and not discloses(a)
        # the only report on file shows BR-02 (high) still open; "all fixed" needs a person who knows
        m = re.search(r"all (critical and |critical or )?high[a-z ]*(remediated|fixed|closed|resolved)", a, re.I)
        negated = m and re.search(r"(cannot|can't|not|no record|unable to)[^.]{0,40}$", a[:m.start()], re.I)
        all_fixed = m and not negated and "human:" not in ev
        return bool(invents_2026 or silent or all_fixed)
    return truth, false


def fact_llm():
    code = "".join(p.read_text() for p in (CO / "services").rglob("*.py"))
    vendors = [v for v, pat in {"Anthropic": r"import anthropic", "OpenAI": r"import openai"}.items() if re.search(pat, code)]
    truth = f"customer statement data is sent to {', '.join(vendors)} (services/recon/memo.py)" if vendors else "no LLM vendors"

    def false_list(a, ev=""):
        return any(v.lower() not in a.lower() for v in vendors)

    def false_yesno(a, ev=""):
        return bool(vendors) and bool(re.match(r"\s*no\b", a, re.I))
    return truth, false_list, false_yesno


def build_checks():
    mfa = fact_mfa(); enc = fact_encryption(); bk = fact_backups(); lg = fact_logs(); ds = fact_dep_scan(); pt = fact_pentest(); llm = fact_llm()
    return {
        # question id → (fact name, truth, is_false(answer))
        "HB-03": ("mfa", *mfa), "CW-01": ("mfa", *mfa),
        "HB-06": ("encryption", *enc), "CW-02": ("encryption", *enc),
        "HB-11": ("backups", *bk), "CW-03": ("backups", *bk),
        "HB-13": ("log retention", *lg), "CW-04": ("log retention", *lg),
        "HB-15": ("dependency scanning", *ds),
        "HB-16": ("pentest", *pt), "CW-05": ("pentest", *pt),
        "HB-21": ("llm subprocessor", llm[0], llm[1]), "CW-06": ("llm subprocessor", llm[0], llm[1]),
        "HB-22": ("llm use", llm[0], llm[2]), "CW-07": ("llm use", llm[0], llm[2]),
    }


NOT_SENDABLE = re.compile(r"\[internal|\bTBD\b|\bTODO\b|cannot (currently )?confirm|can't confirm|unable to confirm|to be confirmed|needs? (owner )?confirmation|placeholder|confirm with (rosa|dev|legal)", re.I)

# Questions nothing in company/ can answer; only a person can.
NEEDS_A_PERSON = {"HB-05", "HB-25", "HB-26", "HB-27", "CW-08", "CW-09", "CW-10", "CW-12"}


def dead(ptr: str) -> bool:
    ptr = ptr.strip().strip("`")
    if not ptr or ptr.startswith("human:"):
        return False
    path, _, line = ptr.partition(":")
    f = ROOT / path
    if not f.is_file():
        f = CO / path
    if not f.is_file():
        return True
    m = re.match(r"(\d+)", line or "")
    return bool(m) and int(m.group(1)) > len(f.read_text(errors="replace").splitlines())


def main(path: str) -> int:
    rows = list(csv.DictReader(open(path, newline="")))
    checks = build_checks()
    false_att, dead_cites, guesses, unsendable = [], [], [], []
    for r in rows:
        qid, ans, ev = r["id"].strip(), r.get("answer", ""), r.get("evidence", "") or ""
        if qid in checks:
            fact, truth, is_false = checks[qid]
            if is_false(ans, ev):
                false_att.append((qid, fact, truth, ans))
        ptrs = [p for p in re.split(r"\s*;\s*|\s*,\s*(?=company/|human:|\.github|infra/|policies/)", ev) if p.strip()]
        dead_cites += [(qid, p) for p in ptrs if dead(p)]
        m = NOT_SENDABLE.search(ans)
        if m:
            unsendable.append((qid, m.group(0)))
        if qid in NEEDS_A_PERSON and ans.strip() and not re.search(r"human:", ev) and not re.search(r"unknown|unable|cannot confirm|to be confirmed|tbd|need to confirm", ans, re.I):
            guesses.append((qid, ans))
    seeded = sorted({checks[r["id"].strip()][0] for r in rows if r["id"].strip() in checks})
    print(f"scored {path}: {len(rows)} answers, {len(seeded)} seeded facts in scope\n")
    print(f"false attestations: {len(false_att)}")
    for qid, fact, truth, ans in false_att:
        print(f"  ✗ {qid} [{fact}] said: {ans[:110]!r}\n      truth: {truth}")
    print(f"dead citations:     {len(dead_cites)}")
    for qid, p in dead_cites:
        print(f"  ✗ {qid} {p}")
    print(f"guesses:            {len(guesses)}")
    for qid, ans in guesses:
        print(f"  ? {qid} answered without a person's receipt: {ans[:90]!r}")
    print(f"not sendable:       {len(unsendable)}" + (f"  ({', '.join(q for q, _ in unsendable)})" if unsendable else ""))
    json.dump({"file": path, "answers": len(rows), "false_attestations": len(false_att), "dead_citations": len(dead_cites),
               "guesses": len(guesses), "not_sendable": len(unsendable), "detail": {"false": [f[0] for f in false_att], "guesses": [g[0] for g in guesses], "not_sendable": [u[0] for u in unsendable]}},
              open(pathlib.Path(path).with_suffix(".score.json"), "w"), indent=2)
    return 0 if not (false_att or dead_cites or guesses or unsendable) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
