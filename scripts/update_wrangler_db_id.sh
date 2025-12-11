#!/bin/bash
# Update wrangler.toml with D1 database ID from Terraform output

set -e

echo "Getting D1 database ID from Terraform..."
cd terraform

if [ ! -f "terraform.tfstate" ]; then
  echo "Error: terraform.tfstate not found"
  echo "Run 'terraform apply' first"
  exit 1
fi

DB_ID=$(terraform output -raw d1_database_id 2>/dev/null)

if [ -z "$DB_ID" ]; then
  echo "Error: Could not get database ID from Terraform"
  echo "Make sure you've run 'terraform apply' successfully"
  exit 1
fi

cd ..

echo "Database ID: $DB_ID"
echo "Updating wrangler.toml..."

# Check if database_id line exists
if grep -q 'database_id = ""' wrangler.toml; then
  # Replace empty database_id
  sed -i '' "s/database_id = \"\"/database_id = \"$DB_ID\"/" wrangler.toml
elif grep -q 'database_id = ' wrangler.toml; then
  # Update existing database_id
  sed -i '' "s/database_id = \".*\"/database_id = \"$DB_ID\"/" wrangler.toml
else
  echo "Warning: database_id not found in wrangler.toml"
  echo "Please add it manually:"
  echo "database_id = \"$DB_ID\""
  exit 1
fi

echo "✓ Updated wrangler.toml with database_id"

# Show the updated section
echo ""
echo "Updated configuration:"
grep -A 3 "d1_databases" wrangler.toml

