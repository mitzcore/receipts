resource "aws_secretsmanager_secret" "db_password" {
  name       = "prod/ledger/db-password"
  kms_key_id = aws_kms_key.data.arn
}

resource "aws_secretsmanager_secret_rotation" "db_password" {
  secret_id           = aws_secretsmanager_secret.db_password.id
  rotation_lambda_arn = aws_lambda_function.rotate_db_secret.arn
  rotation_rules { automatically_after_days = 30 }
}

resource "aws_secretsmanager_secret" "llm_api_key" {
  name       = "prod/recon/llm-api-key"
  kms_key_id = aws_kms_key.data.arn
}
