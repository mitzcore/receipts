#!/usr/bin/env python3
"""Shared memory under concurrent writers: naive vs Receipts.

Anthropic's "components of agent memory" (2026-11-06) reports several agents
writing one shared table and overwriting each other's work, leaving 41 of 57
facts. In Receipts, clerk (Claude Code) and auditor (Codex) write the same
ledger and the same team memory at the same time, so this has to hold.

Three writers, 19 facts each, 57 in total, all at once:
  naive     read the whole store, add a fact, write it back atomically
            (temp file + rename: never corrupt, but last writer wins)
  receipts  the store is append-only and every write takes an exclusive lock
            (the same `locked()` the receipts CLI uses)

    python3 eval/memory_stress.py
"""
import json
import multiprocessing as mp
import pathlib
import random
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
from receipts import locked  # noqa: E402

WRITERS, FACTS = 3, 19


def naive(path, w):
    for i in range(FACTS):
        data = json.loads(path.read_text())
        time.sleep(random.uniform(0, 0.004))  # the agent thinks between read and write
        data.append({"writer": w, "fact": i})
        tmp = path.with_name(f"store.{w}.tmp")  # atomic replace, so the file is never torn,
        tmp.write_text(json.dumps(data))         # only overwritten (the CLI's old save())
        tmp.replace(path)


def receipts(path, w):
    for i in range(FACTS):
        with locked(path):
            time.sleep(random.uniform(0, 0.004))
            with path.open("a") as f:
                f.write(json.dumps({"writer": w, "fact": i}) + "\n")


def run(fn, init):
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "store"
    p.write_text(init)
    ps = [mp.Process(target=fn, args=(p, w)) for w in range(WRITERS)]
    [x.start() for x in ps]
    [x.join() for x in ps]
    text = p.read_text()
    return len(json.loads(text)) if fn is naive else len([l for l in text.splitlines() if l.strip()])


if __name__ == "__main__":
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    n = [run(naive, "[]") for _ in range(trials)]
    r = [run(receipts, "") for _ in range(trials)]
    total = WRITERS * FACTS
    print(f"{WRITERS} concurrent writers, {total} facts, {trials} trials")
    print(f"  naive read-modify-write: kept {min(n)}-{max(n)} of {total}  (mean {sum(n)/trials:.1f})")
    print(f"  receipts locked append:  kept {min(r)}-{max(r)} of {total}")
    sys.exit(0 if min(r) == total else 1)
