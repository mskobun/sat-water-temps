# GitHub Actions

The `deploy.yml` workflow deploys the project on relevant pushes to `main`.

It runs Python tests for Lambda changes, builds and pushes the Lambda Docker image to ECR, applies Terraform, applies D1 migrations, builds the SvelteKit app, and deploys it to Cloudflare Pages.

## Setup

Add these repository secrets under **Settings -> Secrets and variables -> Actions**:

| Secret | Purpose |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | AWS access for ECR and Terraform |
| `AWS_SECRET_ACCESS_KEY` | AWS access for ECR and Terraform |
| `EARTHDATA_USERNAME` | NASA Earthdata access for Lambda processors |
| `EARTHDATA_PASSWORD` | NASA Earthdata access for Lambda processors |
| `CLOUDFLARE_API_TOKEN` | Terraform, D1 migrations, and Pages deployment |
| `CLOUDFLARE_ACCOUNT_ID` | Terraform, D1 migrations, and Pages deployment |
| `R2_BUCKET_NAME` | R2 bucket configuration |
| `R2_ACCESS_KEY_ID` | R2 access for Lambda processors |
| `R2_SECRET_ACCESS_KEY` | R2 access for Lambda processors |
| `R2_ENDPOINT` | R2 S3-compatible endpoint |
| `PAGES_DOMAIN` | Cloudflare Pages production domain |
