# Backup and Recovery Policy

Version 2.0 · Owner: Head of Platform · Approved 2025-09-15

- The production ledger database is backed up automatically every night.
- Point-in-time recovery is enabled.
- Backups are retained for **35 days**.
- Backups are encrypted with the same KMS key as the source data.
- Recovery objectives: **RPO 1 hour, RTO 4 hours** for the ledger database.
- A restore test runs every quarter; results go in `evidence/`.
