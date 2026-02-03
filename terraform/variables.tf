variable "aws_region" {
  description = "AWS region"
  default     = "us-west-2"
}

variable "project_name" {
  description = "Project name for resource naming"
  default     = "eco-water-temps"
}

variable "lambda_image_uri" {
  description = "URI of the Docker image for Lambda functions"
  type        = string
}

variable "appeears_user" {
  description = "AppEEARS Username"
  type        = string
  sensitive   = true
}

variable "appeears_pass" {
  description = "AppEEARS Password"
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with R2/Workers/Pages permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "r2_bucket_name" {
  description = "Cloudflare R2 bucket name for precalculated data"
  type        = string
  default     = "multitifs"
}

variable "pages_project_name" {
  description = "Cloudflare Pages project name (leave blank to skip Pages creation)"
  type        = string
  default     = ""
}

variable "pages_production_branch" {
  description = "Git branch that deploys to production for Pages"
  type        = string
  default     = "main"
}

variable "r2_access_key_id" {
  description = "Cloudflare R2 access key ID (for Lambdas/CI)"
  type        = string
  sensitive   = true
}

variable "r2_secret_access_key" {
  description = "Cloudflare R2 secret access key (for Lambdas/CI)"
  type        = string
  sensitive   = true
}

variable "r2_endpoint" {
  description = "Cloudflare R2 S3-compatible endpoint (e.g., https://<accountid>.r2.cloudflarestorage.com)"
  type        = string
}

variable "pages_domain" {
  description = "Production domain for Cloudflare Pages (e.g., your-app.pages.dev or custom domain)"
  type        = string
}
