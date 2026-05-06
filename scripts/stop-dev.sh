#!/bin/bash
echo "Stopping sql-ai-agent for the day..."
aws rds stop-db-instance --db-instance-identifier sql-ai-agent-db --region us-east-1
aws ecs update-service --cluster sql-ai-agent-cluster --service sql-ai-agent-service --desired-count 0 --region us-east-1
echo "Done. Saving ~$1.30/day while stopped."
