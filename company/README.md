# Ledgerline (fixture)

Ledgerline is a fictional 40-person B2B SaaS company. It sells payment
reconciliation software to banks and credit unions. This folder is its
"source of truth": the infrastructure code, the identity-provider export, CI,
written policies, evidence files, and the answers it gave customers last year.

It is deliberately imperfect, the way real companies are. Some of what the
policies and last year's answers say is no longer true of the systems. The
ground truth lives in `../eval/ground_truth.yaml`. The agents never read that
file. They read only this folder.
