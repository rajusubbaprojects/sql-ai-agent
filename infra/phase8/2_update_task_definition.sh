#!/bin/bash
set -e

AWS_REGION="us-east-1"
CLUSTER_NAME="sql-ai-agent-cluster"
SERVICE_NAME="sql-ai-agent-service"
TASK_FAMILY="sql-ai-agent-task"

# ── Paste ARN from step 1 ─────────────────────────────────────
FRONTEND_API_KEY_ARN="arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:sql-ai-agent/frontend-api-key-XXXXXX"  # pragma: allowlist secret

# ── Fill in after step 3 ──────────────────────────────────────
CLOUDFRONT_DOMAIN="https://PLACEHOLDER.cloudfront.net"

echo "Fetching current task definition..."
CURRENT_TASK_DEF=$(aws ecs describe-task-definition \
  --task-definition "$TASK_FAMILY" \
  --region "$AWS_REGION" \
  --query "taskDefinition" \
  --output json)

echo "Adding env vars..."
NEW_TASK_DEF=$(echo "$CURRENT_TASK_DEF" | python3 -c "
import json, sys
td = json.load(sys.stdin)
container = td['containerDefinitions'][0]

env = container.get('environment', [])
env = [e for e in env if e['name'] != 'CLOUDFRONT_DOMAIN']
env.append({'name': 'CLOUDFRONT_DOMAIN', 'value': '$CLOUDFRONT_DOMAIN'})
container['environment'] = env

secrets = container.get('secrets', [])
secrets = [s for s in secrets if s['name'] != 'FRONTEND_API_KEY']
secrets.append({'name': 'FRONTEND_API_KEY', 'valueFrom': '$FRONTEND_API_KEY_ARN'})
container['secrets'] = secrets

for field in ['taskDefinitionArn','revision','status','requiresAttributes',
              'compatibilities','registeredAt','registeredBy']:
    td.pop(field, None)
print(json.dumps(td))
")

echo "Registering new revision..."
NEW_TASK_ARN=$(echo "$NEW_TASK_DEF" | aws ecs register-task-definition \
  --cli-input-json file:///dev/stdin \
  --region "$AWS_REGION" \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

echo "Updating ECS service..."
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --task-definition "$NEW_TASK_ARN" \
  --region "$AWS_REGION" > /dev/null

echo ""
echo "Done. New task: $NEW_TASK_ARN"
echo "ECS is deploying — takes ~2 min."
