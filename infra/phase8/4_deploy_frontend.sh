#!/bin/bash
set -e

source infra/phase8/phase8_outputs.env

echo "Uploading frontend to S3..."
aws s3 cp frontend/index.html \
  s3://${S3_BUCKET}/index.html \
  --content-type "text/html" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --region us-east-1

echo "Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id "$CLOUDFRONT_DIST_ID" \
  --paths "/*"

echo ""
echo "Live at: $CLOUDFRONT_DOMAIN"
