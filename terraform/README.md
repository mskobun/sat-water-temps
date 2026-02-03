# Terraform – Staging vs production

Environments are distinguished by the `environment` variable and **separate state**. For **production** you leave `environment` unset (default `""`) so existing resource names stay `eco-water-temps-*`. For **staging** you set `environment = "staging"` so resources are named `eco-water-temps-staging-*`.

## Production (default)

- State key: `terraform.tfstate` in the S3 backend bucket.
- No `environment` variable (or leave default); resource names stay `eco-water-temps-*`.
- Use default variables or `production.tfvars`:

```bash
terraform init
terraform plan -var-file=production.tfvars   # optional
terraform apply -var-file=production.tfvars  # optional
```

## Staging

1. **Separate state** – Use a different state key so staging does not overwrite production state:

```bash
terraform init -reconfigure -backend-config=backend.staging.conf
```

   Or inline:

```bash
terraform init -reconfigure -backend-config="key=staging/terraform.tfstate"
```

2. **Staging variables** – Use a tfvars file with `environment = "staging"` and any staging-specific values (D1 name, R2 bucket, Pages domain, etc.):

```bash
cp environments/staging.tfvars.example environments/staging.tfvars
# Edit environments/staging.tfvars with real values

terraform plan -var-file=environments/staging.tfvars
terraform apply -var-file=environments/staging.tfvars
```

3. **Staging-specific resources** – With `environment = "staging"` you get:
   - AWS: separate SQS queue, Lambdas, Step Function, ECR repo, Cognito pool, CloudWatch rule (all prefixed with `eco-water-temps-staging-*`).
   - Cloudflare: use `d1_database_name` and `r2_bucket_name` in tfvars to point to a separate D1 DB and R2 bucket for staging.
   - Cognito: separate user pool and domain (`eco-water-temps-staging-admin`), so staging has its own admin users and callback URLs (set `pages_domain` to your staging frontend URL).

## Switching back to production

After working on staging, re-init with the default backend so you don’t accidentally apply to production state:

```bash
terraform init -reconfigure
```

Then run plan/apply without `-var-file=environments/staging.tfvars` (or with `production.tfvars` if you use one).

## Summary

| Goal              | Command |
|-------------------|--------|
| First-time staging | `terraform init -reconfigure -backend-config=backend.staging.conf` then `plan/apply -var-file=environments/staging.tfvars` |
| Work on staging   | Same backend init + staging tfvars for every plan/apply |
| Work on production | `terraform init -reconfigure` (no backend-config), then plan/apply without staging tfvars |
