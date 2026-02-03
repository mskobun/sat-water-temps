#!/usr/bin/env bash
# One-time script to import existing auto-created CloudWatch log groups
# into Terraform state. Run BEFORE the first `terraform apply` after adding
# explicit aws_cloudwatch_log_group resources.
set -euo pipefail
cd "$(dirname "$0")/../terraform"

echo "Importing existing CloudWatch log groups into Terraform state..."

terraform import aws_cloudwatch_log_group.initiator_logs /aws/lambda/eco-water-temps-initiator
terraform import aws_cloudwatch_log_group.status_checker_logs /aws/lambda/eco-water-temps-status-checker
terraform import aws_cloudwatch_log_group.processor_logs /aws/lambda/eco-water-temps-processor
terraform import aws_cloudwatch_log_group.manifest_processor_logs /aws/lambda/eco-water-temps-manifest-processor

echo "Done. You can now run: terraform plan && terraform apply"
