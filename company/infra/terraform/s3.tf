# Bank statement files uploaded by customers (BAI2, CAMT.053, CSV).
resource "aws_s3_bucket" "statements" {
  bucket = "ledgerline-customer-statements"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "statements" {
  bucket = aws_s3_bucket.statements.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "statements" {
  bucket                  = aws_s3_bucket.statements.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Reconciliation exports customers download from the app (matched/unmatched
# transaction reports). Added for the exports feature, 2026-05.
resource "aws_s3_bucket" "recon_exports" {
  bucket = "ledgerline-recon-exports"
}

resource "aws_s3_bucket_public_access_block" "recon_exports" {
  bucket                  = aws_s3_bucket.recon_exports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "recon_exports" {
  bucket = aws_s3_bucket.recon_exports.id
  rule {
    id     = "expire-exports"
    status = "Enabled"
    expiration { days = 30 }
  }
}
