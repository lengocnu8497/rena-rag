#!/usr/bin/env bash
# Deploy all rena-rag CloudFormation stacks in dependency order.
#
# Prerequisites:
#   0. Deploy GitHub OIDC role (one-time, before CI/CD can run):
#        aws cloudformation deploy \
#          --stack-name rena-rag-github-oidc \
#          --template-file infra/cloudformation/github-oidc.yml \
#          --capabilities CAPABILITY_NAMED_IAM \
#          --parameter-overrides GitHubOrg=<org> GitHubRepo=rena-rag
#      Then set the DeployRoleArn output as the AWS_DEPLOY_ROLE_ARN GitHub secret.
#   1. AWS CLI configured (aws configure or OIDC in CI)
#   2. Run secrets-init.sh and populate real secret values
#   3. Export the four secret ARNs (secrets-init.sh prints the commands)
#   4. Build and push the Docker image to ECR first:
#        IMAGE_TAG=$(git rev-parse --short HEAD)
#        IMAGE_URI=$(aws cloudformation list-exports \
#          --query "Exports[?Name=='rena-rag-EcrUri'].Value" --output text):$IMAGE_TAG
#        docker build -t $IMAGE_URI .
#        aws ecr get-login-password | docker login --username AWS --password-stdin $IMAGE_URI
#        docker push $IMAGE_URI
#
# Required env vars:
#   ANTHROPIC_SECRET_ARN, OPENAI_SECRET_ARN,
#   SUPABASE_URL_SECRET_ARN, SUPABASE_KEY_SECRET_ARN,
#   IMAGE_URI
#
# Optional env vars:
#   CERTIFICATE_ARN   — ACM cert ARN for HTTPS (omit for HTTP only)
#   ALARM_EMAIL       — SNS alarm notification email
#   AWS_DEFAULT_REGION (defaults to us-east-1)

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cloudformation"

# Validate required vars
: "${ANTHROPIC_SECRET_ARN:?Export ANTHROPIC_SECRET_ARN first (run secrets-init.sh)}"
: "${OPENAI_SECRET_ARN:?Export OPENAI_SECRET_ARN first}"
: "${SUPABASE_URL_SECRET_ARN:?Export SUPABASE_URL_SECRET_ARN first}"
: "${SUPABASE_KEY_SECRET_ARN:?Export SUPABASE_KEY_SECRET_ARN first}"
: "${IMAGE_URI:?Export IMAGE_URI (ECR image URI with tag)}"

deploy_stack() {
  local stack_name="$1"
  local template="$2"
  shift 2
  local params=("$@")

  echo ""
  echo "▶ Deploying stack: $stack_name"

  local param_overrides=()
  for p in "${params[@]}"; do
    param_overrides+=("ParameterKey=${p%%=*},ParameterValue=${p#*=}")
  done

  aws cloudformation deploy \
    --stack-name "$stack_name" \
    --template-file "$template" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    ${param_overrides:+--parameter-overrides "${param_overrides[@]}"} \
    --no-fail-on-empty-changeset

  echo "✓ $stack_name deployed"
}

# 1. Network (no dependencies)
deploy_stack "rena-rag-network" "$DIR/network.yml"

# 2. ECR (no dependencies)
deploy_stack "rena-rag-ecr" "$DIR/ecr.yml"

# 3. S3 document bucket (no dependencies)
deploy_stack "rena-rag-s3" "$DIR/s3.yml"

# 4. ECS service (depends on network + s3 exports)
ECS_PARAMS=(
  "ImageUri=${IMAGE_URI}"
  "AnthropicApiKeySecretArn=${ANTHROPIC_SECRET_ARN}"
  "OpenAiApiKeySecretArn=${OPENAI_SECRET_ARN}"
  "SupabaseUrlSecretArn=${SUPABASE_URL_SECRET_ARN}"
  "SupabaseServiceRoleKeySecretArn=${SUPABASE_KEY_SECRET_ARN}"
  "CertificateArn=${CERTIFICATE_ARN:-}"
  "AlarmEmail=${ALARM_EMAIL:-}"
)
deploy_stack "rena-rag-ecs" "$DIR/ecs.yml" "${ECS_PARAMS[@]}"

# 5. Dashboard CDN (no cross-stack dependencies)
deploy_stack "rena-rag-dashboard" "$DIR/dashboard.yml"

# ── Print outputs ──────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════"
echo " Deployment complete"
echo "═══════════════════════════════════════════"

ALB_DNS=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='rena-rag-AlbDns'].Value" \
  --output text)

DASHBOARD_URL=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='rena-rag-DashboardUrl'].Value" \
  --output text)

DASHBOARD_BUCKET=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='rena-rag-DashboardBucket'].Value" \
  --output text)

CF_DIST_ID=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='rena-rag-CloudFrontDistributionId'].Value" \
  --output text)

echo " API endpoint : http://${ALB_DNS}   (use HTTPS if cert configured)"
echo " Dashboard    : ${DASHBOARD_URL}"
echo ""
echo " To deploy the React dashboard:"
echo "   cd dashboard && npm run build"
echo "   aws s3 sync dist/ s3://${DASHBOARD_BUCKET}/ --delete"
echo "   aws cloudfront create-invalidation --distribution-id ${CF_DIST_ID} --paths '/*'"
