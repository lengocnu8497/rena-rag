#!/usr/bin/env bash
# Create Secrets Manager secrets for rena-rag.
# Run once before deploying the ecs.yml stack.
# After running, update each secret's value in the AWS console or with:
#   aws secretsmanager put-secret-value --secret-id <name> --secret-string '<value>'

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"

create_secret() {
  local name="$1"
  local description="$2"
  # Returns existing ARN without error if already exists
  aws secretsmanager create-secret \
    --name "$name" \
    --description "$description" \
    --secret-string "PLACEHOLDER_REPLACE_ME" \
    --region "$REGION" \
    --query ARN \
    --output text 2>/dev/null \
  || aws secretsmanager describe-secret \
    --secret-id "$name" \
    --region "$REGION" \
    --query ARN \
    --output text
}

echo "Creating Secrets Manager secrets in region $REGION ..."

ANTHROPIC_ARN=$(create_secret \
  "rena-rag/anthropic-api-key" \
  "Anthropic API key for Claude Sonnet + Haiku")
echo "  anthropic_api_key  → $ANTHROPIC_ARN"

OPENAI_ARN=$(create_secret \
  "rena-rag/openai-api-key" \
  "OpenAI API key for text-embedding-3-small")
echo "  openai_api_key     → $OPENAI_ARN"

SUPABASE_URL_ARN=$(create_secret \
  "rena-rag/supabase-url" \
  "Supabase project URL (https://xxx.supabase.co)")
echo "  supabase_url       → $SUPABASE_URL_ARN"

SUPABASE_KEY_ARN=$(create_secret \
  "rena-rag/supabase-service-role-key" \
  "Supabase service role key (bypasses RLS)")
echo "  supabase_service_role_key → $SUPABASE_KEY_ARN"

echo ""
echo "Done. Now update each secret with real values:"
echo "  aws secretsmanager put-secret-value --secret-id rena-rag/anthropic-api-key --secret-string 'sk-ant-...'"
echo "  aws secretsmanager put-secret-value --secret-id rena-rag/openai-api-key --secret-string 'sk-...'"
echo "  aws secretsmanager put-secret-value --secret-id rena-rag/supabase-url --secret-string 'https://xxx.supabase.co'"
echo "  aws secretsmanager put-secret-value --secret-id rena-rag/supabase-service-role-key --secret-string 'eyJ...'"
echo ""
echo "Then export these ARNs for deploy.sh:"
echo "export ANTHROPIC_SECRET_ARN=$ANTHROPIC_ARN"
echo "export OPENAI_SECRET_ARN=$OPENAI_ARN"
echo "export SUPABASE_URL_SECRET_ARN=$SUPABASE_URL_ARN"
echo "export SUPABASE_KEY_SECRET_ARN=$SUPABASE_KEY_ARN"
