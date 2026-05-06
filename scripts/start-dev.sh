#!/bin/bash
echo "Starting sql-ai-agent..."
aws rds start-db-instance --db-instance-identifier sql-ai-agent-db --region us-east-1
aws ecs update-service --cluster sql-ai-agent-cluster --service sql-ai-agent-service --desired-count 1 --region us-east-1
echo "Done. RDS takes ~2 minutes to become available."
