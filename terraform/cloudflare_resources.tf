resource "cloudflare_r2_bucket" "data" {
  account_id = var.cloudflare_account_id
  name       = var.r2_bucket_name
}

resource "cloudflare_d1_database" "main" {
  account_id = var.cloudflare_account_id
  name       = "sat-water-temps-db"
  read_replication = {
    mode = "disabled"
  }
}

resource "cloudflare_pages_project" "static" {
  count             = var.pages_project_name == "" ? 0 : 1
  account_id        = var.cloudflare_account_id
  name              = var.pages_project_name
  production_branch = var.pages_production_branch

  # Build is managed by GitHub Actions with Wrangler, not by Cloudflare's automatic builds
  build_config = {
    destination_dir = ".svelte-kit/cloudflare"
  }

  # Deployment configuration including secrets for Cognito authentication
  deployment_configs = {
    production = {
      compatibility_date = "2025-12-11"
      fail_open          = true

      # Environment variables and secrets
      env_vars = {
        COGNITO_REGION = {
          value = "ap-southeast-1"
          type  = "plain_text"
        }
        COGNITO_USER_POOL_ID = {
          value = aws_cognito_user_pool.admin_pool.id
          type  = "secret_text"
        }
        COGNITO_CLIENT_ID = {
          value = aws_cognito_user_pool_client.admin_client.id
          type  = "secret_text"
        }
        COGNITO_CLIENT_SECRET = {
          value = aws_cognito_user_pool_client.admin_client.client_secret
          type  = "secret_text"
        }
        SESSION_SECRET = {
          value = random_password.session_secret.result
          type  = "secret_text"
        }
        AUTH_SECRET = {
          value = random_password.session_secret.result
          type  = "secret_text"
        }
      }

      # D1 database binding
      d1_databases = {
        DB = {
          id = cloudflare_d1_database.main.id
        }
      }

      # R2 bucket binding
      r2_buckets = {
        R2_DATA = {
          name = cloudflare_r2_bucket.data.name
        }
      }
    }

    preview = {
      compatibility_date = "2025-12-11"
      fail_open          = true

      # Environment variables and secrets
      env_vars = {
        COGNITO_REGION = {
          value = "ap-southeast-1"
          type  = "plain_text"
        }
        COGNITO_USER_POOL_ID = {
          value = aws_cognito_user_pool.admin_pool.id
          type  = "secret_text"
        }
        COGNITO_CLIENT_ID = {
          value = aws_cognito_user_pool_client.admin_client.id
          type  = "secret_text"
        }
        COGNITO_CLIENT_SECRET = {
          value = aws_cognito_user_pool_client.admin_client.client_secret
          type  = "secret_text"
        }
        SESSION_SECRET = {
          value = random_password.session_secret.result
          type  = "secret_text"
        }
        AUTH_SECRET = {
          value = random_password.session_secret.result
          type  = "secret_text"
        }
      }

      # D1 database binding
      d1_databases = {
        DB = {
          id = cloudflare_d1_database.main.id
        }
      }

      # R2 bucket binding
      r2_buckets = {
        R2_DATA = {
          name = cloudflare_r2_bucket.data.name
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      build_config
    ]
  }
}
