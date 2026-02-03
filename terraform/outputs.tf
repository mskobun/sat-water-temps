output "r2_bucket_name" {
  value = cloudflare_r2_bucket.data.name
}

output "pages_project_name" {
  value = var.pages_project_name != "" ? cloudflare_pages_project.static[0].name : null
}

output "pages_project_url" {
  description = "URL of the Cloudflare Pages project"
  value       = var.pages_project_name != "" ? "https://${cloudflare_pages_project.static[0].subdomain}" : null
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

output "d1_database_id" {
  value       = cloudflare_d1_database.main.id
  description = "ID of the D1 database"
}

output "d1_database_name" {
  value       = cloudflare_d1_database.main.name
  description = "Name of the D1 database"
}

# Cognito outputs
output "cognito_user_pool_id" {
  value       = aws_cognito_user_pool.admin_pool.id
  description = "Cognito User Pool ID"
}

output "cognito_client_id" {
  value       = aws_cognito_user_pool_client.admin_client.id
  description = "Cognito App Client ID"
}

output "cognito_client_secret" {
  value       = aws_cognito_user_pool_client.admin_client.client_secret
  description = "Cognito App Client Secret"
  sensitive   = true
}

output "cognito_domain" {
  value       = "https://${aws_cognito_user_pool_domain.admin_domain.domain}.auth.ap-southeast-1.amazoncognito.com"
  description = "Cognito Hosted UI domain URL"
}

output "cognito_jwks_url" {
  value       = "https://cognito-idp.ap-southeast-1.amazonaws.com/${aws_cognito_user_pool.admin_pool.id}/.well-known/jwks.json"
  description = "Cognito JWKS URL for token verification"
}

output "session_secret" {
  value       = random_password.session_secret.result
  description = "Session encryption secret"
  sensitive   = true
}
