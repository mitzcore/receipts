resource "aws_db_instance" "ledger" {
  identifier              = "ledgerline-prod"
  engine                  = "postgres"
  engine_version          = "16.4"
  instance_class          = "db.r6g.xlarge"
  allocated_storage       = 500
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.data.arn
  multi_az                = true
  publicly_accessible     = false
  db_subnet_group_name    = aws_db_subnet_group.private.name
  vpc_security_group_ids  = [aws_security_group.db.id]

  # Automated snapshots run nightly in the backup window. PITR is enabled
  # for the whole retention period.
  backup_window           = "03:00-04:00"
  backup_retention_period = 7 # cut from 35 during the 2026-03 cost review (PLAT-412)

  deletion_protection     = true
  copy_tags_to_snapshot   = true
}

resource "aws_db_subnet_group" "private" {
  name       = "ledgerline-private"
  subnet_ids = aws_subnet.private[*].id
}
