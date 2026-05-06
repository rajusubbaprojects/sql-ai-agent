#!/bin/bash
set -e

AWS_REGION="us-east-1"
BUCKET_NAME="sql-ai-agent-ui-prod"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Account: $AWS_ACCOUNT_ID"

# ── S3 ────────────────────────────────────────────────────────
echo "Creating S3 bucket..."
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$AWS_REGION" 2>/dev/null || echo "Bucket exists, continuing..."

aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# ── OAC ───────────────────────────────────────────────────────
echo "Creating Origin Access Control..."
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config '{
    "Name": "sql-ai-agent-oac",
    "Description": "OAC for SQL AI Agent UI",
    "SigningProtocol": "sigv4",
    "SigningBehavior": "always",
    "OriginAccessControlOriginType": "s3"
  }' \
  --query "OriginAccessControl.Id" \
  --output text 2>/dev/null || \
  aws cloudfront list-origin-access-controls \
    --query "OriginAccessControlList.Items[?Name=='sql-ai-agent-oac'].Id" \
    --output text)
echo "OAC: $OAC_ID"

# ── CloudFront ────────────────────────────────────────────────
echo "Creating CloudFront distribution..."
DIST_OUTPUT=$(aws cloudfront create-distribution \
  --distribution-config "{
    \"CallerReference\": \"sql-ai-agent-$(date +%s)\",
    \"Comment\": \"SQL AI Agent Phase 8 UI\",
    \"DefaultRootObject\": \"index.html\",
    \"Origins\": {
      \"Quantity\": 1,
      \"Items\": [{
        \"Id\": \"S3-${BUCKET_NAME}\",
        \"DomainName\": \"${BUCKET_NAME}.s3.${AWS_REGION}.amazonaws.com\",
        \"S3OriginConfig\": {\"OriginAccessIdentity\": \"\"},
        \"OriginAccessControlId\": \"${OAC_ID}\"
      }]
    },
    \"DefaultCacheBehavior\": {
      \"TargetOriginId\": \"S3-${BUCKET_NAME}\",
      \"ViewerProtocolPolicy\": \"redirect-to-https\",
      \"CachePolicyId\": \"658327ea-f89d-4fab-a63d-7e88639e58f6\",
      \"AllowedMethods\": {
        \"Quantity\": 2,
        \"Items\": [\"GET\", \"HEAD\"],
        \"CachedMethods\": {\"Quantity\": 2, \"Items\": [\"GET\", \"HEAD\"]}
      },
      \"Compress\": true,
      \"ForwardedValues\": {
        \"QueryString\": false,
        \"Cookies\": {\"Forward\": \"none\"}
      },
      \"MinTTL\": 0
    },
    \"CustomErrorResponses\": {
      \"Quantity\": 1,
      \"Items\": [{
        \"ErrorCode\": 403,
        \"ResponsePagePath\": \"/index.html\",
        \"ResponseCode\": \"200\",
        \"ErrorCachingMinTTL\": 0
      }]
    },
    \"ViewerCertificate\": {
      \"CloudFrontDefaultCertificate\": true,
      \"MinimumProtocolVersion\": \"TLSv1.2_2021\"
    },
    \"Enabled\": true,
    \"HttpVersion\": \"http2and3\",
    \"PriceClass\": \"PriceClass_100\"
  }" --output json)

DIST_ID=$(echo "$DIST_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['Id'])")
DIST_DOMAIN=$(echo "$DIST_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['DomainName'])")

# ── Bucket policy ─────────────────────────────────────────────
echo "Attaching bucket policy..."
aws s3api put-bucket-policy \
  --bucket "$BUCKET_NAME" \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Sid\": \"AllowCloudFrontOnly\",
      \"Effect\": \"Allow\",
      \"Principal\": {\"Service\": \"cloudfront.amazonaws.com\"},
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::${BUCKET_NAME}/*\",
      \"Condition\": {
        \"StringEquals\": {
          \"AWS:SourceArn\": \"arn:aws:cloudfront::${AWS_ACCOUNT_ID}:distribution/${DIST_ID}\"
        }
      }
    }]
  }"

# ── Save outputs ──────────────────────────────────────────────
cat > infra/phase8/phase8_outputs.env << ENVEOF
CLOUDFRONT_DIST_ID=$DIST_ID
CLOUDFRONT_DOMAIN=https://$DIST_DOMAIN
S3_BUCKET=$BUCKET_NAME
ENVEOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CloudFront domain : https://$DIST_DOMAIN"
echo "Distribution ID   : $DIST_ID"
echo "S3 Bucket         : $BUCKET_NAME"
echo ""
echo "Next steps:"
echo "1. Paste https://$DIST_DOMAIN into 2_update_task_definition.sh and re-run it"
echo "2. Add to GitHub secrets: CLOUDFRONT_DIST_ID, S3_BUCKET, FRONTEND_API_KEY"
echo "3. Run 4_deploy_frontend.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
