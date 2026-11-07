#!/usr/bin/env python3
"""The three people in the demo: Maya (account exec), Dev (platform), Rosa (legal).

The agents in the demo are live: clerk is a Claude Code session and auditor a
Codex session, both started by Switch, and nothing they say is scripted. The
people are scripted, so anyone can rerun the demo without three coworkers. Each
person watches their Mattermost channel and replies only to what an agent
actually asked them, by question ID, with what that person knows. A reply never
depends on the agent having said the right thing.

    python3 demo/actors.py            # reads demo/.env (see demo/env.example)

Stdlib only.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
for line in (HERE / ".env").read_text().splitlines() if (HERE / ".env").exists() else []:
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

MM = os.environ.get("MM_URL", "http://localhost:8065").rstrip("/")
TEAM = os.environ.get("MM_TEAM", "")
DEAL, INFRA, LEGAL = (os.environ.get(k, d) for k, d in [("CH_DEAL", "deal-harbor-bank"), ("CH_INFRA", "infra"), ("CH_LEGAL", "legal")])
PACE = float(os.environ.get("ACTOR_PACE", "6"))  # seconds a person "takes" to type a reply
IDS = re.compile(r"\b((?:HB|CW)-\d\d)\b")
MODE = os.environ.get("DEMO", "harbor")  # harbor | clearwater (run 2, after scripts/drift.sh)

# ── What each person knows ─────────────────────────────────────────────────────
DEV_KNOWS = {
    "HB-02": "yes. Everything goes through Okta, there's no local login on anything in prod.",
    "HB-05": "yes, quarterly, done in Okta. Last review was 2026-10-06 (SEC-88). Next one is January.",
    "HB-12": "RPO 1h / RTO 4h is right. The September restore test took 1h52m end to end.",
    "HB-16": "nothing since Bramble in April 2025, we skipped it this year on budget. Bramble is booked for 2026-12-01. BR-02 was fixed 2025-09-03 (PR #1182).",
    "HB-18": "yes. Three AWS accounts, prod / staging / dev, and an SCP stops prod snapshots being shared out.",
    "HB-28": "yes, three AZs, RDS is Multi-AZ.",
}
DEV_DECIDES = {  # what Dev says when the auditor shows him a contradiction
    "HB-01": "the 2026 review slipped, that's on me. Disclose it: v3.2 was approved 2025-09-15, the 2026 review and re-approval is scheduled for 2026-11-20, approver is the CEO.",
    "HB-03": "ugh. That contractor rule was meant to die in May. I'm not changing Okta from a chat thread, so disclose it: 6 contractor accounts are password-only today, Okta Verify gets enforced for them by 2026-11-14.",
    "HB-06": "that's a real miss, the exports bucket never got the KMS block. Fix the Terraform: same SSE config as the statements bucket, pointed at aws_kms_key.data. Show me the diff first.",
    "HB-11": "the policy is right and the Terraform is wrong. 7 days came out of the March cost review and nobody told legal. Put it back to 35. Diff first.",
    "HB-13": "we keep 180 days, not 12 months. Disclose it. We're moving audit logs to 400 days in S3 by 2026-12-31.",
    "HB-15": "true, nothing has scanned since Snyk lapsed in June. Disclose it. Dependabot goes on this week, by 2026-11-13.",
    "HB-16": "right, it's stale. Disclose it: last test April 2025, Bramble booked for 2026-12-01, BR-02 fixed 2025-09-03.",
}
# When the auditor contests an answer for missing evidence, the owner points at the record.
DEV_CORROBORATES = {
    "HB-05": "SEC-88 is the Q3 Okta access certification. Run 2026-10-06, reviewer me, scope every prod AWS and GitHub assignment, 2 stale contractor accounts removed. The earlier ones were SEC-61 (July), SEC-40 (April) and SEC-17 (January). Yes, add the record file.",
    "HB-16": "BR-02 was fixed in PR #1182, merged 2025-09-03, but Bramble never retested it. Update line 9 with the PR and say it isn't verified by the tester until the Dec 1 retest.",
    "HB-28": "the app tier lives in the platform repo, not here: ECS on Fargate across us-east-1a/b/c, 3 tasks minimum. Narrow the answer to what this repo shows, and say the app tier spans three AZs on my word.",
}
ROSA_KNOWS = {
    "HB-20": "for bank customers the MSA says 36 hours from confirmation, not 72. And if an incident disrupts the service for 4+ hours we tell them as soon as possible, that's the bank service provider rule.",
    "HB-21": "AWS, Sentry, Postmark, and Anthropic. See HB-22.",
    "HB-22": "yes, and it never went through vendor review, which is on me. Disclose it: Anthropic drafts exception memos for unmatched transactions; it receives the statement line (counterparty, amount, value date, remittance text). Their commercial API terms exclude training on our data. DPA signed by 2026-11-21, and it goes on the subprocessor list today.",
    "HB-23": "United States only. AWS us-east-1, and Anthropic processes our API traffic in the US.",
    "HB-24": "live data within 30 days of termination; backups age out after that within the backup retention window.",
    "HB-25": "yes. KnowBe4, annual and mandatory for employees and contractors. 100% completion at the October 2026 deadline.",
    "HB-26": "yes. Checkr at hire for every US employee. Contractors are checked by their agency, and our contract with the agency requires it.",
    "HB-27": "yes. Coalition, $5M aggregate limit, renews 2027-03-01.",
}
ROSA_FOLLOWUP = {  # what Rosa says when the clerk comes back with a diff or a narrower question
    "HB-21": "yes, apply the subprocessor diff. And the DPA isn't signed yet: it's due 2026-11-21, so say exactly that.",
    "HB-24": "our order form with Anthropic says memo inputs are deleted within 30 days, and they don't train on them. Sentry keeps 30 days, Postmark 45. Nothing passes 65.",
    "HB-26": "one contractor in Portugal; she's in the Contractors group, so yes, she can reach prod read-only. Say that. Her agency ran the check like everyone else's.",
    "HB-20": "yes, apply the version without \"likely to\". The plan is the stale one; the MSA wins.",
    "HB-23": "the order form commits Anthropic to US processing for our account, yes. You're right that the code doesn't pin it, so cite me, not the code.",
    "HB-27": "nothing to add.",
    "HB-11": "good catch on the history. I'll handle the customers we told \"35 days\" since March. Leave Harbor's answer as you wrote it.",
}
ROSA_DECIDES = {"HB-21": ROSA_KNOWS["HB-22"], "HB-22": ROSA_KNOWS["HB-22"], "HB-20": ROSA_KNOWS["HB-20"]}

# Clearwater (run 2) asks overlapping questions in different words.
CW_SAME = {"CW-05": "HB-16", "CW-06": "HB-21", "CW-07": "HB-22", "CW-08": "HB-25", "CW-09": "HB-26",
           "CW-10": "HB-27", "CW-11": "HB-20", "CW-12": "HB-05", "CW-02": "HB-06", "CW-04": "HB-13"}
for cw, hb in CW_SAME.items():
    for book in (DEV_KNOWS, ROSA_KNOWS, DEV_DECIDES, ROSA_DECIDES):
        if hb in book:
            book[cw] = book[hb]
DEV_KNOWS["CW-01"] = DEV_DECIDES["CW-01"] = "yes, as of 2026-11-12. Contractors are on the Workforce MFA policy now and the temporary password-only rule is deleted."
DEV_KNOWS["CW-03"] = DEV_DECIDES["CW-03"] = "finance cut it to 14 days in last week's cost review, I lost that one. Disclose 14 days. I'm taking it back to 35 at the December review."
ROSA_KNOWS["CW-11"] = ROSA_DECIDES["CW-11"] = "same MSA language as for banks: 36 hours from confirmation."

if MODE == "clearwater":  # after scripts/drift.sh: what changed since Harbor Bank
    POST_DRIFT_BACKUPS = "yeah, finance cut it to 14 days in this week's cost review (PLAT-511). I lost that one. Disclose 14 days; I'm taking it back to 35 at the December review. Don't revert it."
    POST_DRIFT_MFA = "that's real: contractors moved onto the Workforce MFA policy today and the temporary password-only rule is deleted. MFA is enforced for every workforce account now."
    for k in ("HB-11", "HB-24", "CW-03"):
        DEV_KNOWS[k] = DEV_DECIDES[k] = POST_DRIFT_BACKUPS
    for k in ("HB-03", "CW-01"):
        DEV_KNOWS[k] = DEV_DECIDES[k] = POST_DRIFT_MFA

KICKOFF = ("@clerk Harbor Bank sent their vendor security questionnaire: `inbox/harbor-bank-vendor-security-questionnaire.csv`, "
           "28 questions. Procurement wants it back Monday or the pilot slips to Q1. Can you take it?")
KICKOFF_CW = ("@clerk one more: Clearwater Credit Union sent a 12-question security review, "
              "`inbox/clearwater-cu-security-review.csv`. Same drill, please.")
SIGNOFF_CW = "Thanks. That was fast. Signing off and sending it to Clearwater."
SIGNOFF = ("Read it, thanks. Signing off. I'd rather tell Harbor about the contractor MFA gap now than have their auditor "
           "find it in March. Sending it today.")


# ── Mattermost ────────────────────────────────────────────────────────────────
def api(token, method, path, body=None):
    req = urllib.request.Request(MM + "/api/v4" + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


class Person:
    def __init__(self, name, token):
        self.name, self.token = name, token
        self.me = api(token, "GET", "/users/me")
        self.channels = {}

    def channel(self, name):
        if name not in self.channels:
            teams = api(self.token, "GET", "/users/me/teams")
            for t in teams:
                if TEAM and t["name"] != TEAM:
                    continue
                for c in api(self.token, "GET", f"/users/me/teams/{t['id']}/channels"):
                    if c["name"] == name or c["display_name"].lstrip("~#") == name:
                        self.channels[name] = c["id"]
            if name not in self.channels:
                sys.exit(f"{self.name} can't see a channel called {name}")
        return self.channels[name]

    def say(self, ch, text, root_id=""):
        time.sleep(PACE)
        api(self.token, "POST", "/posts", {"channel_id": self.channel(ch), "message": text, "root_id": root_id})
        print(f"[{self.name} → ~{ch}] {text[:100]}")

    def since(self, ch, t_ms):
        r = api(self.token, "GET", f"/channels/{self.channel(ch)}/posts?since={t_ms}")
        posts = sorted(r["posts"].values(), key=lambda p: p["create_at"])
        return [p for p in posts if p["create_at"] > t_ms and not p.get("type")]


def humans_ids(people):
    return {p.me["id"] for p in people}


def main():
    maya, dev, rosa = (Person(n, os.environ[f"MM_TOKEN_{n.upper()}"]) for n in ("maya", "dev", "rosa"))
    people = humans_ids([maya, dev, rosa])
    answered = {"dev": set(), "rosa": set(), "dev_decided": set(), "rosa_decided": set(), "dev_corroborated": set(), "rosa_followup": set()}
    approved_diffs, signed, nudged, last_activity = set(), False, False, time.time()
    t0 = int(time.time() * 1000) - int(os.environ.get("LOOKBACK_S", "0")) * 1000
    if not os.environ.get("SKIP_KICKOFF"):
        maya.say(DEAL, KICKOFF if MODE == "harbor" else KICKOFF_CW)
    cursor = {DEAL: t0, INFRA: t0, LEGAL: t0}
    deadline = time.time() + float(os.environ.get("DEMO_TIMEOUT", "2400"))
    while time.time() < deadline and not signed:
        time.sleep(3)
        for ch, person, key in [(INFRA, dev, "dev"), (LEGAL, rosa, "rosa"), (DEAL, maya, "maya")]:
            for p in person.since(ch, cursor[ch]):
                cursor[ch] = max(cursor[ch], p["create_at"])
                last_activity = time.time()
                if p["user_id"] in people:
                    continue
                msg, root = p["message"], p.get("root_id") or p["id"]
                if key == "maya":
                    if re.search(r"sign[- ]?off|ready for (your|maya)|ready to send", msg, re.I) and re.search(r"RECEIPTS\.md|answers\.csv", msg):
                        maya.say(DEAL, SIGNOFF if MODE == "harbor" else SIGNOFF_CW, root)
                        signed = True
                    continue
                if f"@{person.me['username']}" not in msg:
                    continue
                ids = list(dict.fromkeys(IDS.findall(msg)))
                knows = DEV_KNOWS if key == "dev" else ROSA_KNOWS
                decides = DEV_DECIDES if key == "dev" else ROSA_DECIDES
                is_diff = "```diff" in msg or re.search(r"^[+-]\s+\w", msg, re.M)
                if is_diff and key == "dev" and re.search(r"apply|approve|ok to|go ahead|confirm", msg, re.I):
                    extra = [i for i in ids if i in DEV_DECIDES and i not in answered["dev_decided"] and not re.search(rf"{i}\*?\*?:? diff", msg)]
                    if p["id"] not in approved_diffs:
                        approved_diffs.add(p["id"])
                        answered["dev_decided"].update(extra)
                        person.say(ch, "Diffs look right. Approved, apply them." + "".join(f"\n**{i}**: {DEV_DECIDES[i]}" for i in extra), root)
                    continue
                if key == "rosa" and (is_diff or "?" in msg):
                    todo = [i for i in ids if i in ROSA_FOLLOWUP and (i in answered["rosa"] or i == "HB-11") and i not in answered["rosa_followup"]]
                    if todo:
                        answered["rosa_followup"].update(todo)
                        person.say(ch, "\n".join(f"**{i}**: {ROSA_FOLLOWUP[i]}" for i in todo), root)
                        continue
                contest = re.search(r"contest|contradict|disagree|conflict|mismatch|doesn.t match|reality|which (one )?is (wrong|right|true)|one of (these|them) is wrong|policy says|terraform says", msg, re.I)
                lines = []
                if key == "dev" and contest and re.search(r"missing|no (review )?record|substantiat|corroborat|provide", msg, re.I):
                    for i in ids:
                        if i in DEV_CORROBORATES and i not in answered["dev_corroborated"]:
                            answered["dev_corroborated"].add(i)
                            lines.append(f"**{i}**: {DEV_CORROBORATES[i]}")
                    if lines:
                        person.say(ch, "\n".join(lines), root)
                        continue
                for i in ids:
                    if (contest or i not in knows) and i in decides and i not in answered[f"{key}_decided"]:
                        answered[f"{key}_decided"].add(i); answered[key].add(i)
                        lines.append(f"**{i}**: {decides[i]}")
                    elif i not in answered[key] and i in knows:
                        answered[key].add(i)
                        lines.append(f"**{i}**: {knows[i]}")
                    elif i not in answered[key] and i not in decides:
                        answered[key].add(i)
                        lines.append(f"**{i}**: not mine to answer from memory. Go with what the systems show, and flag me if they disagree with the policy.")
                if lines:
                    person.say(ch, "\n".join(lines), root)
        # Agents only act when addressed. If the ledger is done and nobody has handed it back, Maya asks.
        if not nudged and MODE and time.time() - last_activity > 90:
            led = pathlib.Path(__file__).resolve().parent.parent / "out" / ("harbor-bank" if MODE == "harbor" else "clearwater-cu") / "ledger.json"
            if led.exists():
                qs = json.loads(led.read_text())["questions"]
                if qs and all(q["status"] in ("verified", "exception") for q in qs):
                    nudged = True
                    maya.say(DEAL, "@clerk looks like the auditor has signed off on everything. Can you wrap it up and give me the summary?")
    print("done" if signed else "timed out before sign-off")


if __name__ == "__main__":
    main()
