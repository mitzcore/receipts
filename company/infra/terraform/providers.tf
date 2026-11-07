terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.60" }
  }
  backend "s3" {
    bucket = "ledgerline-tfstate"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1" # all production workloads and customer data live here
  default_tags {
    tags = { env = "prod", owner = "platform", managed_by = "terraform" }
  }
}
