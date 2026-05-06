#!/bin/bash
echo "WARNING: This will delete all AWS resources for sql-ai-agent"
read -p "Are you sure? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "Aborted"
  exit 1
fi

echo "Scaling ECS to 0..."
aws ecs update-service --cluster sql-ai-agent-cluster --service sql-ai-agent-service --desired-count 0 --region us-east-1

echo "Deleting ECS service..."
aws ecs delete-service --cluster sql-ai-agent-cluster --service sql-ai-agent-service --region us-east-1

echo "Stopping RDS..."
aws rds stop-db-instance --db-instance-identifier sql-ai-agent-db --region us-east-1

echo "Deleting ALB..."
aws elbv2 delete-load-balancer --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:490841876782:loadbalancer/app/sql-ai-agent-alb/fa318aaf57ee7d0f

echo "Deleting target group..."
aws elbv2 delete-target-group --target-group-arn arn:aws:elasticloadbalancing:us-east-1:490841876782:targetgroup/sql-ai-agent-tg/a0a20e66192c8907

echo "Deleting WAF..."
LOCK=$(aws wafv2 get-web-acl --name sql-ai-agent-waf --scope REGIONAL --id bc2ee157-ccbd-4f8b-a98d-c293bcca5fb0 --region us-east-1 --query 'LockToken' --output text)
aws wafv2 disassociate-web-acl --resource-arn arn:aws:elasticloadbalancing:us-east-1:490841876782:loadbalancer/app/sql-ai-agent-alb/fa318aaf57ee7d0f --region us-east-1
aws wafv2 delete-web-acl --name sql-ai-agent-waf --scope REGIONAL --id bc2ee157-ccbd-4f8b-a98d-c293bcca5fb0 --lock-token $LOCK --region us-east-1

echo "Deleting RDS scheduler..."
aws scheduler delete-schedule --name rds-stop-sql-ai-agent --region us-east-1
aws scheduler delete-schedule --name rds-start-sql-ai-agent --region us-east-1

echo "Deleting secrets..."
aws secretsmanager delete-secret --secret-id sql-ai-agent/db-credentials --force-delete-without-recovery --region us-east-1
aws secretsmanager delete-secret --secret-id sql-ai-agent/anthropic-api-key --force-delete-without-recovery --region us-east-1

echo "Done. RDS and ECR must be deleted manually from the AWS console."
echo "Remember to delete the RDS instance and ECR repository when ready."
