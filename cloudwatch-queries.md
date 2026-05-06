# CloudWatch Logs Insights Queries

## Slow queries (over 5 seconds)
fields @timestamp, query, sql, latency_ms
| filter event = "query_executed" and latency_ms > 5000
| sort latency_ms desc
| limit 20

## Error rate
fields @timestamp, query, error
| filter event = "query_executed" and success = false
| sort @timestamp desc
| limit 20

## Request latency by path
fields @timestamp, path, latency_ms, status_code
| filter event = "request_completed"
| stats avg(latency_ms), max(latency_ms), count() by path
| sort avg(latency_ms) desc

## All queries today
fields @timestamp, query, sql, success, latency_ms
| filter event = "query_executed"
| sort @timestamp desc
| limit 50
