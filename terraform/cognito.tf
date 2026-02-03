# Cognito User Pool for admin authentication
# Deployed in Singapore (ap-southeast-1) for lower latency

provider "aws" {
  alias  = "singapore"
  region = "ap-southeast-1"
}

resource "aws_cognito_user_pool" "admin_pool" {
  provider = aws.singapore
  name     = "${local.name_prefix}-admin-pool"

  # Strong password policy
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  # Admin-only user creation (no self-registration)
  admin_create_user_config {
    allow_admin_create_user_only = true

    invite_message_template {
      email_subject = "Your admin account for ${local.name_prefix}"
      email_message = "Your username is {username} and temporary password is {####}. Please sign in at the admin portal to set a new password."
      sms_message   = "Your username is {username} and temporary password is {####}."
    }
  }

  # Account recovery via email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # MFA optional (can enable later)
  mfa_configuration = "OFF"

  # Schema attributes
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 3
      max_length = 254
    }
  }

  # Auto-verify email
  auto_verified_attributes = ["email"]

  tags = {
    Project     = var.project_name
    Environment = var.environment != "" ? var.environment : "production"
    Purpose     = "Admin authentication"
  }
}

resource "aws_cognito_user_pool_client" "admin_client" {
  provider     = aws.singapore
  name         = "${local.name_prefix}-admin-client"
  user_pool_id = aws_cognito_user_pool.admin_pool.id

  # Generate client secret for confidential OAuth client
  generate_secret = true

  # OAuth 2.0 configuration
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  # Callback URLs for OAuth redirect (Auth.js uses /auth/callback/cognito)
  callback_urls = [
    "https://${var.pages_domain}/auth/callback/cognito",
    "http://localhost:5173/auth/callback/cognito",
    "http://localhost:8788/auth/callback/cognito"
  ]

  # Logout URLs
  logout_urls = [
    "https://${var.pages_domain}/admin/login",
    "http://localhost:5173/admin/login",
    "http://localhost:8788/admin/login"
  ]

  # Auth flows
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  # Token validity
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent token revocation on sign out (simpler flow)
  enable_token_revocation = true

  # No need for propagate_additional_user_context
  enable_propagate_additional_user_context_data = false
}

resource "aws_cognito_user_pool_domain" "admin_domain" {
  provider     = aws.singapore
  domain       = "${local.name_prefix}-admin"
  user_pool_id = aws_cognito_user_pool.admin_pool.id
}

# Generate a secure session secret for encrypting cookies
resource "random_password" "session_secret" {
  length  = 32
  special = false
}
