output "r2_bucket_name" {
  value = cloudflare_r2_bucket.data.name
}

output "pages_project_name" {
  value = var.pages_project_name != "" ? cloudflare_pages_project.static[0].name : null
}
output "ecr_repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.lambda_repo.repository_url
}

output "initiator_lambda_name" {
  value = aws_lambda_function.initiator_lambda.function_name
}

output "step_function_arn" {
  value = aws_sfn_state_machine.polling_machine.arn
}
