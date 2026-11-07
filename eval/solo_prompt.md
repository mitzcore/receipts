You are filling in a vendor security questionnaire for Ledgerline, the company whose files are in ./company
(policies, Terraform, the Okta export, CI config, application code, evidence files, and last year's
answers in company/knowledge/answers.jsonl).

The questionnaire is ./inbox/harbor-bank-vendor-security-questionnaire.csv. Answer every question the way
a careful security engineer would, for a bank customer. For each answer, cite the evidence you relied on as
path:line pointers relative to this directory (for example company/infra/terraform/rds.tf:18), separated by " ; ".

Do not open anything under ./eval or ./out except the file you write.

Write the result to ./out/baseline/harbor-bank-solo.csv with the header: id,answer,evidence
Use proper CSV quoting. Answer all 28 questions. Then stop.
