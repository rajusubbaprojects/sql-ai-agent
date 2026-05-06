# Cost Optimization — Phase 7D

## Fargate Spot
- 70% of tasks run on Spot (up to 70% cheaper)
- 30% on-demand with base=1 guarantees at least 1 task always runs
- Estimated saving: ~$8-12/month

## RDS Scheduled Stop/Start
- Stops at midnight UTC (8PM Eastern)
- Starts at noon UTC (8AM Eastern)
- 8 hours off per day = ~33% cost reduction
- Estimated saving: ~$7-8/month on db.t3.micro

## CloudWatch Log Retention
- Logs retained for 30 days in CloudWatch
- Archived to S3 Glacier after 30 days (85% cheaper)
- Deleted after 365 days
- Bucket: s3://sql-ai-agent-logs-490841876782

## Summary
| Resource | Before | After | Saving |
|---|---|---|---|
| ECS Fargate | On-demand only | 70% Spot | ~$10/month |
| RDS db.t3.micro | Always on | 16hrs/day | ~$8/month |
| CloudWatch logs | Indefinite | 30d + S3 Glacier | ~$2/month |
| **Total** | | | **~$20/month** |
