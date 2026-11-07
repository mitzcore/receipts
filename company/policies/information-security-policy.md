# Information Security Policy

Version 3.2 · Owner: Head of Platform (Dev Okafor) · Approved 2025-09-15 · Review: annually

## 1. Scope
Applies to all Ledgerline employees, contractors and systems that store or
process customer data.

## 2. Encryption
2.1 Customer data at rest is encrypted with AES-256 using customer-managed AWS
KMS keys. This covers every RDS instance and every S3 bucket.
2.2 KMS keys rotate automatically every year.
2.3 Data in transit over public networks uses TLS 1.2 or higher. Plain HTTP
is redirected to HTTPS.

## 3. Network
3.1 Databases sit in private subnets and are reachable only from the
application tier.
3.2 No production data store is publicly accessible.

## 4. Secrets
Secrets live in AWS Secrets Manager. Database credentials rotate every 30 days.
Secrets never appear in source code or CI logs.

## 5. Logging and monitoring
5.1 AWS CloudTrail is enabled in every region with log file validation.
5.2 Security audit logs are retained for at least 12 months.

## 6. Vulnerability management
6.1 Application dependencies are scanned automatically on every pull request
and at least weekly.
6.2 A third-party penetration test is performed at least annually. Critical
and high findings are fixed within 30 days.
