# Receipts: Clearwater Credit Union

Questionnaire `inbox/clearwater-cu-security-review.csv` · exported 2026-11-07T10:05:17-05:00

- 12 answers, every one with a receipt
- 0 answers were contested by the auditor before they went out
- 0 disclosed exceptions

## Answers

### CW-01 · Identity
> Is MFA required for every person with access to systems that hold member data, including third-party contractors?

Yes. Every workforce account, employees and contractors alike, signs in through Okta with MFA enforced (Okta Verify push or WebAuthn). This includes the six third-party contractor accounts, which have read-only access to production AWS and access to GitHub. Contractor accounts were moved onto the MFA policy on 2026-11-07; before that date they signed in with a password only, under a temporary onboarding rule.

- receipt: `company/idp/okta-policies.json:17-23`
- receipt: `company/idp/okta-policies.json:5-12`
- receipt: `human:@dev in ~infra at 2026-11-07T10:00`
- receipt: `human:@dev in ~infra at 2026-11-07T09:32`

### CW-02 · Data protection
> Describe encryption at rest for member data, including key ownership.

Member data at rest is encrypted with AES-256. The production PostgreSQL database (Amazon RDS) and the S3 buckets holding statement files and reconciliation exports are encrypted with a single AWS KMS customer-managed key (alias/ledgerline-data). Ledgerline owns and manages this key in its own AWS account; the key material is held in AWS KMS, rotates automatically every year, and is not supplied or held by customers. The same key protects all customers' data. Reconciliation export files created before 2026-11-07 remain encrypted with AES-256 under S3-managed keys until they expire, no later than 2026-12-07.

- receipt: `company/infra/terraform/rds.tf:7-8`
- receipt: `company/infra/terraform/s3.tf:6-13`
- receipt: `company/infra/terraform/s3.tf:30-38`
- receipt: `company/infra/terraform/s3.tf:53`
- receipt: `company/infra/terraform/kms.tf:1-10`
- receipt: `human:@dev in ~infra at 2026-11-07T09:35`

### CW-03 · Continuity
> How long are database backups kept?

Production database backups (Amazon RDS automated snapshots, taken nightly, with point-in-time recovery across the retention window) are currently kept for 14 days. Retention was 7 days from March 2026 until 2026-11-07, so the full 14-day history is available from 2026-11-14. Our backup policy sets 35 days, and we plan to restore 35-day retention at our December 2026 review.

- receipt: `company/infra/terraform/rds.tf:14-17`
- receipt: `company/policies/backup-and-recovery.md:7`
- receipt: `human:@dev in ~infra at 2026-11-07T09:35`
- receipt: `human:@dev in ~infra at 2026-11-07T10:00`

### CW-04 · Monitoring
> What is the retention period for security and audit logs?

AWS CloudTrail audit logs (all regions, with log file validation) are retained for 90 days in CloudWatch Logs and for 180 days in an S3 archive encrypted with our AWS KMS key. Application API logs are retained for 30 days. We are extending S3 retention of audit logs to 400 days by 2026-12-31.

- receipt: `company/infra/terraform/logging.tf:1-14`
- receipt: `company/infra/terraform/logging.tf:16-19`
- receipt: `company/infra/terraform/logging.tf:25-33`
- receipt: `company/infra/terraform/logging.tf:44`
- receipt: `human:@dev in ~infra at 2026-11-07T09:32`

### CW-05 · Testing
> Provide the date of your last third-party penetration test.

Our most recent third-party penetration test was performed by Bramble Security (CREST-accredited) from 2025-04-07 to 2025-04-18, covering the public API, web app, admin console and AWS configuration. No penetration test has been performed since. Our next test with Bramble Security is booked for 2026-12-01.

- receipt: `company/evidence/pentest-2025-04-summary.md:3-4`
- receipt: `company/evidence/pentest-2025-04-summary.md:9`
- receipt: `human:@dev in ~infra at 2026-11-07T09:32`

### CW-06 · Vendors
> Please list your subprocessors.

Amazon Web Services (hosting and storage, US, us-east-1); Sentry (error monitoring, PII scrubbed, US); Postmark (transactional email, US); Anthropic (LLM API that drafts exception memos for unmatched transactions). Anthropic was added in our August 2026 release without first completing our vendor security review. The DPA with Anthropic is not yet signed; it is due to be signed by 2026-11-21.

- receipt: `company/policies/vendor-management.md:12-15`
- receipt: `company/services/recon/memo.py:9-11`
- receipt: `company/services/recon/memo.py:21-27`
- receipt: `human:@rosa in ~legal at 2026-11-07T09:32`
- receipt: `human:@rosa in ~legal at 2026-11-07T09:38`

### CW-07 · AI
> Is member data shared with any AI model provider?

Yes. Since our August 2026 release, the reconciliation service uses Anthropic's API (Claude Sonnet 4.5) to draft short exception memos for statement lines that cannot be matched to a ledger entry. For each unmatched line we send the counterparty name, amount, value date and remittance text as they appear on the statement, together with the nearest candidate ledger entries. Under our order form with Anthropic, these inputs are deleted within 30 days and are not used to train models. This use did not go through our vendor security review before launch. The DPA with Anthropic is not yet signed; it is due to be signed by 2026-11-21.

- receipt: `company/services/recon/memo.py:1-5`
- receipt: `company/services/recon/memo.py:13-27`
- receipt: `company/policies/vendor-management.md:15`
- receipt: `human:@rosa in ~legal at 2026-11-07T09:32`
- receipt: `human:@rosa in ~legal at 2026-11-07T09:38`

### CW-08 · People
> Is security awareness training mandatory and annual?

Yes. Security awareness training (KnowBe4) is mandatory and annual for all employees and contractors. Completion for the 2026 cycle was 100% at the October 2026 deadline.

- receipt: `human:@rosa in ~legal at 2026-11-07T09:32`

### CW-09 · People
> Do you background-check staff with access to member data?

Yes. Every employee with access to member data is background-checked by Checkr at hire. Contractors are background-checked by the agencies that engage them, as our contracts with those agencies require. Contractors have read-only access to our production AWS environment; this includes one contractor based in Portugal, who was background-checked by her agency.

- receipt: `human:@rosa in ~legal at 2026-11-07T09:32`
- receipt: `company/idp/okta-policies.json:10`
- receipt: `human:@rosa in ~legal at 2026-11-07T09:43`

### CW-10 · Insurance
> What is your cyber insurance coverage limit?

Yes. We carry cyber liability insurance with Coalition, with a $5,000,000 aggregate limit. The policy renews on 2027-03-01.

- receipt: `human:@rosa in ~legal at 2026-11-07T09:32`

### CW-11 · Notification
> What is your contractual breach-notification window for credit union customers?

We notify credit union customers within 36 hours of confirming a security incident involving their data.

- receipt: `human:@rosa in ~legal at 2026-11-07T10:03`
- receipt: `company/policies/incident-response.md:8-10`

### CW-12 · Access
> When did you last review production access rights?

Production access rights are reviewed quarterly in Okta. The most recent review was completed on 2026-10-06; the next is scheduled for January 2027.

- receipt: `company/policies/access-control.md:13`
- receipt: `human:@dev in ~infra at 2026-11-07T09:32`
