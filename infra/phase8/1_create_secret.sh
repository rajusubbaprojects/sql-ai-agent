#!/bin/bash
set -e

AWS_REGION="us-east-1"
SECRET_NAME="sql-ai-agent/frontend-api-key"  # pragma: allowlist secret  # pragma: allowlist secret

API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo ""
echo "Generated API key (save this for GitHub Actions secret):"
echo "  $API_KEY"
echo ""

if aws secretsmanager describe-secret \
     --secret-id "$SECRET_NAME" \
     --region "$AWS_REGION" > /dev/null 2>&1; then
  echo "Secret exists — updating..."
  aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "$API_KEY" \
    --region "$AWS_REGION"
else
  echo "Creating secret..."
  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "Frontend API key for SQL AI Agent Phase 8" \
    --secret-string "$API_KEY" \
    --region "$AWS_REGION"
fi

SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "$SECRET_NAME" \
  --region "$AWS_REGION" \
  --query "ARN" \
  --output text)

echo ""
echo "Secret ARN (paste into 2_update_task_definition.sh):"
echo "  $SECRET_ARN"
