# GitHub Actions Setup

## Required Secrets

To use the deployment workflow, add these secrets to your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add the following repository secrets:

| Secret Name | Value |
|-------------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |

## How It Works

The `deploy.yml` workflow:
1. **Triggers** on:
   - Push to `main` branch (when Lambda code or Dockerfile changes)
   - Manual trigger via "Actions" tab
2. **Builds** the Docker image for `linux/amd64`
3. **Pushes** to ECR with both a commit SHA tag and `latest` tag
4. **Updates** all three Lambda functions to use the new image

## Manual Trigger

To manually trigger a deployment:
1. Go to **Actions** tab
2. Select **Build and Deploy Lambda**
3. Click **Run workflow**
