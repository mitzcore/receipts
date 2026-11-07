# Receipts

**A security-questionnaire desk where Claude Code, Codex and the people who own the facts work in the same Switch rooms, and nothing goes to a customer without proof.**

Built for the [Flip the Switch hackathon](https://www.wemakedevs.org/hackathons/switch), Track 01: Best Business Workflow.

> Demo video: ⟨VIDEO⟩

---

## The problem

If you sell software to a bank, the bank sends you a security questionnaire before it signs. Thirty to three hundred questions: *Is MFA enforced for every account that can reach production? How long do you keep backups? List every subprocessor that touches our data.*

At most companies one person, usually in sales or security, fills it in by copying last year's answers and the policy documents. The answers sound right. Nobody checks them against the actual Terraform, the actual Okta config, the actual code. Then the questionnaire gets attached to the contract, and every "yes" becomes a warranty.

Systems drift and documents don't. The backup retention got cut in a cost review. Someone added a "temporary" password-only sign-on rule for contractors. A new feature started sending transaction data to an LLM API that never went through vendor review. Each of these turns last year's true answer into this year's false statement to a bank.

A solo AI agent makes this worse, not better. It fills in all 28 answers in a few minutes, with confident citations, from the same stale documents. ⟨BASELINE-SUMMARY⟩

## What Receipts does

Receipts turns the questionnaire into a team workflow that runs in Switch. There are two agents on two different providers, and the people who own the facts each answer in their own room.

```
            ~deal-harbor-bank                     ~infra                        ~legal
  Maya (AE) ──► clerk (Claude Code)  ──asks──► Dev (Head of Platform)   Rosa (Legal & Privacy)
                   │   drafts every answer         ▲   │                       ▲   │
                   │   with path:line evidence     │   │ answers by ID         │   │
                   ▼                               │   ▼                       │   ▼
              auditor (Codex) ── checks every claim, the clerk's AND the people's,
                                 against Terraform, the Okta export, CI and the code
                                 and contests anything reality contradicts ─────────┘
                   │
                   ▼
   shared ledger (./receipts) ── export refuses anything not verified or honestly disclosed
```

1. **Maya** (account exec) asks `@clerk` in `~deal-harbor-bank` to take Harbor Bank's questionnaire.
2. **clerk** (Claude Code) drafts every answer from `company/`, Ledgerline's Terraform, IdP export, CI, code and policies. Every answer needs a receipt: a `path:line` that proves it. Systems beat documents, and last year's answers count as leads, not evidence. If nothing in the repo can prove an answer, the clerk doesn't guess. It looks up the owner in `OWNERS.yaml` and asks them in their room, by question ID.
3. **auditor** (Codex, a different model from the clerk, so the two don't share blind spots) checks each draft and each answer a person gives. It opens every citation, then looks for the counter-example: every bucket rather than only the cited one, every sign-on policy, every SDK the code imports.
4. When the auditor finds a contradiction, the clerk takes both sides to the owner: *you said 35 days, `rds.tf:18` says 7, which one is wrong?* There are only three ways out. The answer gets corrected. The system gets fixed: the clerk proposes the diff, and applies it only after the owner approves it in the room. Or the gap is disclosed with a remediation date. A deadline never turns into a "yes".
5. When every answer is verified or disclosed, the clerk exports the questionnaire with a receipt column and a `RECEIPTS.md`, saves what people told it so the next questionnaire asks them less, and hands it to Maya for sign-off. Agents never send anything to a customer.

## Why this needs Switch

The theme is "turn your solo agent into a teammate." The difference shows up here as a number (see [Results](#results)): a solo agent can read every file, but it can't ask Dev whether the Terraform or the policy is wrong, and it can't get Rosa to own a disclosure. The work goes from plausible to true at the point where agents and the right people are in a room together. Switch is what puts them there:

| Switch piece | What it does in Receipts |
|---|---|
| **Rooms** (Mattermost channels via the Switch bridge) | One room per fact owner. Questions go where the owner already works, and the answer is recorded in that room's history as the receipt (`human:@dev in ~infra at 20:14`). |
| **Any agent, any provider** | clerk runs on Claude Code and auditor runs on Codex, both started and kept alive by Switch Console. Cross-vendor review is the point, because two copies of one model make the same mistake twice. |
| **Addressing policy** (`anyone`) | Maya, Dev and Rosa can all address the agents, not just the person who registered them. |
| **Shared working directory and context** | Both agents work from the same repo and the same ledger, so neither has to re-explain state in chat. |
| **Templates** | [`switch/receipts.template.yaml`](switch/receipts.template.yaml) creates both agents (with providers, instructions and addressing) and all three linked rooms in one import. |

Without Switch, clerk and auditor are two CLI processes that can't reach Dev or Rosa, and you're back to the solo agent.

## Results

⟨RESULTS⟩

## How the truth is checked (the outside judge)

`company/` is a fictional 40-person fintech, Ledgerline, built to fail the way real companies do. Seven claims in its policies and last year's answers are no longer true of its systems:

| Seeded drift | Where the truth lives |
|---|---|
| Backups "retained 35 days" | `infra/terraform/rds.tf`: `backup_retention_period = 7` (a cost review in March) |
| "MFA for every workforce account" | `idp/okta-policies.json`: an ACTIVE password-only rule for Contractors, who have prod read-only and GitHub |
| "Every S3 bucket uses our KMS key" | `infra/terraform/s3.tf`: the exports bucket added in May has no SSE block, so it's on S3-managed keys |
| "Audit logs kept 12+ months" | `infra/terraform/logging.tf`: 90 days in CloudWatch, 180 days in S3 |
| "Dependencies scanned weekly" | `.github/workflows/ci.yml`: the Snyk job is commented out since June |
| "Annual pentest, all highs fixed" | `evidence/`: the only report is April 2025, with one high still open at the time |
| "No generative AI on customer data" | `services/recon/memo.py`: sends statement lines to the Anthropic API, and Anthropic isn't on the subprocessor list |

[`eval/score.py`](eval/score.py) scores any filled questionnaire (from Receipts, a solo agent, or a person) against these facts. It doesn't use an answer key. It re-derives each fact from the live files every time it runs. If Dev approves the Terraform fix and `rds.tf` now says 35, then "35 days" scores as true. The only way to a clean score is for the answer to match reality: change the answer, or change reality. It reports three numbers:

- **false attestations**: a seeded fact asserted falsely without disclosing the gap
- **dead citations**: evidence pointers that don't resolve to a real file and line
- **guesses**: questions only a person can answer (training, background checks, insurance, access reviews), answered with no person's receipt

The agents are instructed never to open `eval/`.

## Run it yourself

You need macOS (or Windows/Linux with the Console early-access builds), Docker, Node 20+, Python 3.10+, and Claude Code and Codex CLIs signed in.

```bash
git clone ⟨REPO⟩ receipts && cd receipts

# 1. The solo-agent baseline and its score (no Switch needed)
claude -p "$(cat eval/solo_prompt.md)" --allowedTools "Read,Glob,Grep,Write" --permission-mode acceptEdits
python3 eval/score.py out/baseline/harbor-bank-solo.csv
```

Then the Switch workflow:

⟨SETUP⟩

## What's real and what's staged

- **Real:** Switch Console 0.40.1 with a local Switch server and the bundled Mattermost; clerk is a live Claude Code session and auditor a live Codex session, both run by Switch. Nothing they say in the demo is scripted. The ledger, the export gate, the Terraform fix and the score are all real.
- **Staged:** Ledgerline and Harbor Bank are fictional. Maya, Dev and Rosa are played by [`demo/actors.py`](demo/actors.py) so the run can be reproduced without three coworkers. Each one replies only to what an agent actually asked them, by question ID, with what that person knows. The script never tells an agent what to find.

## Repo layout

```
company/                Ledgerline's source of truth (the fixture the agents read)
inbox/                  questionnaires from customers
switch/                 the Switch template and the two agents' instructions
tools/receipts.py       the shared ledger CLI (./receipts)
eval/score.py           the outside judge, plus the solo-agent prompt
demo/actors.py          the three scripted people
out/                    ledgers, exports, scores
```

## What I'd do next

⟨NEXT⟩
