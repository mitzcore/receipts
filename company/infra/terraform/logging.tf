resource "aws_cloudtrail" "org" {
  name                          = "ledgerline-org-trail"
  s3_bucket_name                = aws_s3_bucket.audit_logs.id
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true
  cloud_watch_logs_group_arn    = "${aws_cloudwatch_log_group.trail.arn}:*"
  cloud_watch_logs_role_arn     = aws_iam_role.trail_to_cw.arn
}

resource "aws_cloudwatch_log_group" "trail" {
  name              = "/ledgerline/cloudtrail"
  retention_in_days = 90
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ledgerline/api"
  retention_in_days = 30
}

resource "aws_s3_bucket" "audit_logs" {
  bucket = "ledgerline-audit-logs"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    id     = "audit-retention"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "GLACIER_IR"
    }
    expiration { days = 180 }
  }
}
