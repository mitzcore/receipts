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
import contextlib
import csv
import datetime as dt
import fcntl
import hashlib
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
COMPANY = ROOT / "company"
FINAL = {"verified", "exception"}
STATUSES = ["open", "drafted", "needs_owner", "contested", "verified", "exception"]
ICON = {"open": "·", "drafted": "✎", "needs_owner": "?", "contested": "✗", "verified": "✓", "exception": "!"}


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


MEMORY = COMPANY / "knowledge" / "memory.jsonl"
LEGACY = COMPANY / "knowledge" / "answers.jsonl"
HUMAN_TTL_DAYS = 180


@contextlib.contextmanager
def locked(path: pathlib.Path):
    """Exclusive advisory lock. clerk and auditor run at the same time, on different
    providers, and both write through this CLI: no read-modify-write may interleave."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


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
    with locked(ledger_path(a.deal)):
        _set(a)


def _set(a):
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


# ── Team memory with receipts ──────────────────────────────────────────────────
# A memory is a claim plus HOW it was known. File receipts store the cited text
# and its hash; person receipts store who said it, where, and when. Recall
# re-checks every receipt against the world as it is now, so a memory whose
# evidence changed can never be silently reused. Checking costs a file read and
# a hash per receipt, not a model call: only stale memories need a model or a person.

def _lines(ptr: str):
    path, _, spec = ptr.partition(":")
    f = ROOT / path
    if not f.is_file():
        return None, None
    text = f.read_text(errors="replace").splitlines()
    if not spec:
        return "\n".join(text), f
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", spec)
    lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
    return "\n".join(l.strip() for l in text[lo - 1:hi]), f


def _sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()[:16]


def receipt_for(ptr: str) -> dict:
    if ptr.startswith("human:"):
        return {"ptr": ptr}
    cited, _ = _lines(ptr)
    return {"ptr": ptr, "sha": _sha(cited or ""), "text": (cited or "")[:400]}


def check_receipt(r: dict, today: dt.date) -> tuple[str, str]:
    ptr = r["ptr"]
    if ptr.startswith("human:"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", ptr) or re.search(r"(\d{4}-\d{2}-\d{2})", r.get("as_of", ""))
        when = dt.date.fromisoformat(m.group(1)) if m else None
        if when and (today - when).days > HUMAN_TTL_DAYS:
            return "expired", f"said {when}, older than {HUMAN_TTL_DAYS} days: ask the owner again"
        return "fresh", "a person confirmed it" + (f" on {when}" if when else "")
    cited, f = _lines(ptr)
    if cited is None:
        return "stale", f"{ptr.split(':')[0]} no longer exists"
    if _sha(cited) == r["sha"]:
        return "fresh", "evidence unchanged"
    old = [l for l in r.get("text", "").splitlines() if l.strip()]
    body = [l.strip() for l in f.read_text(errors="replace").splitlines()]
    if old and all(l in body for l in old):
        n = body.index(old[0]) + 1
        return "fresh", f"evidence unchanged, moved to line {n}"
    now = cited.splitlines()[0][:120] if cited else ""
    return "stale", f"evidence changed. was: {r.get('text', '')[:120]!r} now: {now!r}"


def cmd_remember(a):
    """Save every final answer with its receipts, so the next questionnaire can reuse what's still true."""
    led = load(a.deal)
    added = 0
    with locked(MEMORY):
        with MEMORY.open("a") as f:
            for q in led["questions"]:
                if q["status"] not in FINAL or not q["evidence"]:
                    continue
                entry = {"id": f"{a.deal}/{q['id']}", "question": q["question"], "answer": q["answer"], "status": q["status"],
                         "owner": q["owner"] or "", "as_of": dt.date.today().isoformat(), "source": led["customer"],
                         "receipts": [receipt_for(p) for p in q["evidence"]]}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                added += 1
    print(f"remembered {added} answers with receipts in {MEMORY.relative_to(ROOT)}")


def _memories():
    if not MEMORY.exists():
        return []
    latest = {}
    for line in MEMORY.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            latest[e["id"]] = e  # append-only; the newest entry for an id wins
    return list(latest.values())


WORD = re.compile(r"[a-z0-9]{3,}")
STOP = set("the and are for you your with that this all any what how does have from our used will been when which least".split())


def _score(query: str, text: str) -> float:
    q = {w for w in WORD.findall(query.lower()) if w not in STOP}
    t = {w for w in WORD.findall(text.lower()) if w not in STOP}
    return len(q & t) / (len(q) or 1)


def cmd_recall(a):
    today = dt.date.today()
    hits = sorted(((_score(a.query, e["question"] + " " + e["answer"]), e) for e in _memories()), key=lambda x: -x[0])
    hits = [(s, e) for s, e in hits if s >= 0.25][: a.k]
    if not hits:
        print("no memory with receipts for this. Draft it from the systems, or ask the owner.")
    for s, e in hits:
        verdicts = [(r["ptr"], *check_receipt(r, today)) for r in e["receipts"]]
        overall = "STALE" if any(v[1] == "stale" for v in verdicts) else "EXPIRED" if any(v[1] == "expired" for v in verdicts) else "FRESH"
        print(f"[{overall}] {e['id']} ({e['as_of']}, {e['status']}) match {s:.0%}")
        print(f"  Q: {e['question']}")
        print(f"  A: {e['answer']}")
        for ptr, v, why in verdicts:
            print(f"  {'✓' if v == 'fresh' else '✗'} {ptr}: {why}")
    leads = sorted(((_score(a.query, j["question"] + " " + j["answer"]), j) for j in map(json.loads, LEGACY.read_text().splitlines()) if True), key=lambda x: -x[0]) if LEGACY.exists() else []
    for s, j in leads[:1]:
        if s >= 0.25:
            print(f"[LEAD, no receipts] last year ({j['as_of']}): {j['answer']}  ← not evidence; re-prove it")
    print("rule: FRESH may be reused with its receipts (the auditor still checks). STALE or EXPIRED: re-derive or re-ask.")


def cmd_memcheck(a):
    t0 = time.perf_counter()
    today = dt.date.today()
    mems = _memories()
    counts = {"fresh": 0, "stale": 0, "expired": 0}
    stale = []
    n_receipts = 0
    for e in mems:
        vs = [check_receipt(r, today)[0] for r in e["receipts"]]
        n_receipts += len(vs)
        k = "stale" if "stale" in vs else "expired" if "expired" in vs else "fresh"
        counts[k] += 1
        if k != "fresh":
            stale.append(e["id"])
    ms = (time.perf_counter() - t0) * 1000
    print(f"{len(mems)} memories, {n_receipts} receipts checked in {ms:.1f} ms: "
          f"{counts['fresh']} fresh, {counts['stale']} stale, {counts['expired']} expired")
    for i in stale:
        print(f"  ✗ {i}")


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
    s = sub.add_parser("recall", help="what the team already knows about a question, with each receipt re-checked now"); s.add_argument("query"); s.add_argument("-k", type=int, default=3); s.set_defaults(fn=cmd_recall)
    s = sub.add_parser("memcheck", help="re-check every receipt in team memory"); s.set_defaults(fn=cmd_memcheck)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
