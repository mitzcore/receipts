#!/usr/bin/env python3
"""receipts: the shared answer ledger the clerk, the auditor and the humans work from.

Every answer to a questionnaire lives in out/<deal>/ledger.json with its
status, its evidence and its history. The agents call this CLI rather than
editing JSON by hand, so the state is the same whichever agent (or person)
touched it last, and `export` can refuse to ship anything without a receipt.

Statuses
  open         nobody has looked at it yet
  drafted      the clerk answered it and cited evidence; waiting for the auditor
  needs_owner  the evidence can't prove it; routed to a person
  contested    the auditor found evidence that contradicts the answer
  verified     the auditor checked the evidence and it supports the answer
  exception    the true answer is "no" or "not yet"; disclosed with remediation
Only verified and exception answers can be exported.

Stdlib only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
COMPANY = ROOT / "company"
FINAL = {"verified", "exception"}
STATUSES = ["open", "drafted", "needs_owner", "contested", "verified", "exception"]
ICON = {"open": "·", "drafted": "✎", "needs_owner": "?", "contested": "✗", "verified": "✓", "exception": "!"}


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ledger_path(deal: str) -> pathlib.Path:
    return OUT / deal / "ledger.json"


def load(deal: str) -> dict:
    p = ledger_path(deal)
    if not p.exists():
        sys.exit(f"no ledger for '{deal}'. Run: receipts start <questionnaire.csv> --deal {deal}")
    return json.loads(p.read_text())


def save(deal: str, led: dict) -> None:
    p = ledger_path(deal)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(led, indent=2, ensure_ascii=False))
    tmp.replace(p)


def find(led: dict, qid: str) -> dict:
    for q in led["questions"]:
        if q["id"].lower() == qid.lower():
            return q
    sys.exit(f"no question {qid}")


def check_pointer(ptr: str) -> str | None:
    """Return an error string if an evidence pointer doesn't resolve, else None.

    Pointers look like `company/infra/terraform/rds.tf:18`, `company/idp/okta-policies.json`,
    or `human:@dev in ~infra at 2026-11-07T20:14` for something a person said.
    """
    if ptr.startswith("human:"):
        return None
    path, _, line = ptr.partition(":")
    f = (ROOT / path).resolve()
    if not str(f).startswith(str(ROOT)) or not f.is_file():
        return f"file not found: {path}"
    if line:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", line)
        if not m:
            return f"bad line spec: {ptr}"
        n = sum(1 for _ in f.open(errors="replace"))
        hi = int(m.group(2) or m.group(1))
        if hi > n:
            return f"{path} has {n} lines, pointer says {line}"
    return None


def cmd_start(a):
    rows = list(csv.DictReader(open(a.csv, newline="")))
    d = OUT / a.deal
    d.mkdir(parents=True, exist_ok=True)
    if ledger_path(a.deal).exists() and not a.force:
        sys.exit(f"ledger for {a.deal} exists; pass --force to restart it")
    led = {
        "deal": a.deal,
        "customer": a.customer or a.deal,
        "source": str(pathlib.Path(a.csv).resolve().relative_to(ROOT)) if str(pathlib.Path(a.csv).resolve()).startswith(str(ROOT)) else a.csv,
        "started": now(),
        "questions": [
            {"id": r["id"], "section": r.get("section", ""), "question": r["question"], "status": "open",
             "answer": "", "evidence": [], "owner": None, "history": []}
            for r in rows
        ],
    }
    save(a.deal, led)
    print(f"ledger started: {len(rows)} questions → {ledger_path(a.deal).relative_to(ROOT)}")


def cmd_set(a):
    led = load(a.deal)
    q = find(led, a.qid)
    bad = [e for e in (check_pointer(p) for p in a.evidence) if e]
    if bad:
        sys.exit("refused, evidence doesn't resolve:\n  " + "\n  ".join(bad))
    if a.status in FINAL and not (a.evidence or q["evidence"]):
        sys.exit(f"refused: {a.status} needs at least one evidence pointer (a file:line or human:...)")
    before = q["status"]
    if a.answer is not None:
        q["answer"] = a.answer
    if a.replace_evidence:
        q["evidence"] = []
    for p in a.evidence:
        if p not in q["evidence"]:
            q["evidence"].append(p)
    if a.owner:
        q["owner"] = a.owner.lstrip("@")
    q["status"] = a.status
    q["history"].append({"at": now(), "by": a.by, "from": before, "to": a.status, "note": a.note or ""})
    save(a.deal, led)
    print(f"{q['id']}: {before} → {a.status}" + (f" (owner @{q['owner']})" if q["owner"] else ""))


def cmd_show(a):
    led = load(a.deal)
    qs = led["questions"] if not a.qid else [find(led, x) for x in a.qid]
    for q in qs:
        if a.status and q["status"] not in a.status:
            continue
        print(f"[{q['id']}] {q['status']}" + (f"  owner @{q['owner']}" if q["owner"] else ""))
        print(f"  Q: {q['question']}")
        if q["answer"]:
            print(f"  A: {q['answer']}")
        for e in q["evidence"]:
            print(f"  ↳ {e}")
        if a.history:
            for h in q["history"]:
                print(f"    {h['at']} {h['by']}: {h['from']}→{h['to']} {h['note']}")


def cmd_board(a):
    led = load(a.deal)
    qs = led["questions"]
    counts = {s: sum(q["status"] == s for q in qs) for s in STATUSES}
    done = counts["verified"] + counts["exception"]
    lines = [f"**{led['customer']}**: {done}/{len(qs)} ready to send · "
             + " · ".join(f"{ICON[s]} {s.replace('_', ' ')} {n}" for s, n in counts.items() if n)]
    if not a.short:
        lines += ["", "| | id | question | owner | status |", "|---|---|---|---|---|"]
        for q in qs:
            if a.only and q["status"] not in a.only:
                continue
            short = q["question"] if len(q["question"]) < 70 else q["question"][:67] + "…"
            lines.append(f"| {ICON[q['status']]} | {q['id']} | {short} | {('@' + q['owner']) if q['owner'] else ''} | {q['status'].replace('_', ' ')} |")
    print("\n".join(lines))


def cmd_lint(a):
    """Every evidence pointer must resolve. Run before export; the auditor runs it too."""
    led = load(a.deal)
    errors = 0
    for q in led["questions"]:
        for p in q["evidence"]:
            e = check_pointer(p)
            if e:
                errors += 1
                print(f"{q['id']}: {e}")
        if q["status"] in FINAL and not q["evidence"]:
            errors += 1
            print(f"{q['id']}: {q['status']} with no evidence")
    print("evidence ok" if not errors else f"{errors} problem(s)")
    sys.exit(1 if errors else 0)


def cmd_export(a):
    led = load(a.deal)
    pending = [q["id"] for q in led["questions"] if q["status"] not in FINAL]
    if pending and not a.draft:
        sys.exit(f"refused: {len(pending)} answer(s) aren't verified or disclosed yet: {', '.join(pending)}")
    d = OUT / a.deal
    csv_path = d / f"{a.deal}-answers.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "section", "question", "answer", "status", "evidence", "last_changed_by"])
        for q in led["questions"]:
            w.writerow([q["id"], q["section"], q["question"], q["answer"], q["status"],
                        " ; ".join(q["evidence"]), q["history"][-1]["by"] if q["history"] else ""])
    exc = [q for q in led["questions"] if q["status"] == "exception"]
    changed = [q for q in led["questions"] if any(h["to"] == "contested" for h in q["history"])]
    md = [f"# Receipts: {led['customer']}", "",
          f"Questionnaire `{led['source']}` · exported {now()}", "",
          f"- {len(led['questions'])} answers, every one with a receipt",
          f"- {len(changed)} answers were contested by the auditor before they went out",
          f"- {len(exc)} disclosed exceptions", ""]
    if exc:
        md += ["## Disclosed exceptions", ""]
        md += [f"- **{q['id']}**: {q['answer']}" for q in exc] + [""]
    md += ["## Answers", ""]
    for q in led["questions"]:
        md += [f"### {q['id']} · {q['section']}", f"> {q['question']}", "", q["answer"] or "_(no answer)_", ""]
        md += [f"- receipt: `{e}`" for e in q["evidence"]]
        if any(h["to"] == "contested" for h in q["history"]):
            md += [f"- history: " + " → ".join(f"{h['to']} ({h['by']})" for h in q["history"])]
        md.append("")
    (d / "RECEIPTS.md").write_text("\n".join(md))
    print(f"wrote {csv_path.relative_to(ROOT)} and {(d / 'RECEIPTS.md').relative_to(ROOT)}")


def cmd_remember(a):
    """Save what people told us, so the next questionnaire doesn't have to ask them again."""
    led = load(a.deal)
    lib = COMPANY / "knowledge" / "answers.jsonl"
    added = 0
    with lib.open("a") as f:
        for q in led["questions"]:
            humans = [e for e in q["evidence"] if e.startswith("human:")]
            if q["status"] in FINAL and humans:
                f.write(json.dumps({"topic": q["section"].lower(), "question": q["question"], "answer": q["answer"],
                                    "source": f"{led['customer']} questionnaire {q['id']}",
                                    "as_of": dt.date.today().isoformat(),
                                    "answered_by": q["owner"] or "", "receipts": q["evidence"]}, ensure_ascii=False) + "\n")
                added += 1
    print(f"remembered {added} human-confirmed answer(s) in {lib.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(prog="receipts", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("csv"); s.add_argument("--deal", required=True); s.add_argument("--customer"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_start)
    s = sub.add_parser("set"); s.add_argument("deal"); s.add_argument("qid"); s.add_argument("--status", required=True, choices=STATUSES)
    s.add_argument("--answer"); s.add_argument("--evidence", action="append", default=[]); s.add_argument("--replace-evidence", action="store_true")
    s.add_argument("--owner"); s.add_argument("--by", required=True); s.add_argument("--note"); s.set_defaults(fn=cmd_set)
    s = sub.add_parser("show"); s.add_argument("deal"); s.add_argument("qid", nargs="*"); s.add_argument("--status", nargs="*"); s.add_argument("--history", action="store_true"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("board"); s.add_argument("deal"); s.add_argument("--short", action="store_true"); s.add_argument("--only", nargs="*"); s.set_defaults(fn=cmd_board)
    s = sub.add_parser("lint"); s.add_argument("deal"); s.set_defaults(fn=cmd_lint)
    s = sub.add_parser("export"); s.add_argument("deal"); s.add_argument("--draft", action="store_true"); s.set_defaults(fn=cmd_export)
    s = sub.add_parser("remember"); s.add_argument("deal"); s.set_defaults(fn=cmd_remember)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
