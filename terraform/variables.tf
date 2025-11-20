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

variable "supabase_url" {
  description = "Supabase URL"
  type        = string
  sensitive   = true
}

variable "supabase_key" {
  description = "Supabase Key"
  type        = string
  sensitive   = true
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
