resource "cloudflare_r2_bucket" "data" {
  account_id = var.cloudflare_account_id
  name       = var.r2_bucket_name
}

resource "cloudflare_pages_project" "static" {
  count              = var.pages_project_name == "" ? 0 : 1
  account_id         = var.cloudflare_account_id
  name               = var.pages_project_name
  production_branch  = var.pages_production_branch
}
