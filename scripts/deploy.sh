#!/usr/bin/env bash
# deploy.sh — build the Lambda package and apply Terraform
# Usage: ./scripts/deploy.sh [--region ap-southeast-1] [--model anthropic.claude-3-haiku-20240307-v1:0]
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAMBDA_SRC_DIR="${ROOT_DIR}/lambda"
LAMBDA_PKG_DIR="${ROOT_DIR}/lambda_package"
TF_DIR="${ROOT_DIR}/terraform"

# ---------------------------------------------------------------------------
# Optional overrides via CLI flags
# ---------------------------------------------------------------------------
TF_REGION=""
TF_MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)  TF_REGION="$2"; shift 2 ;;
    --model)   TF_MODEL="$2";  shift 2 ;;
    *)         echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
echo "==> Checking prerequisites…"

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.11+."
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "    Python version: ${PYTHON_VERSION}"

if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null 2>&1; then
  echo "ERROR: pip not found."
  exit 1
fi

if ! command -v terraform &>/dev/null; then
  echo "ERROR: terraform not found. Install from https://developer.hashicorp.com/terraform/downloads"
  exit 1
fi

if ! command -v node &>/dev/null; then
  echo "ERROR: node not found. Install from https://nodejs.org"
  exit 1
fi

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js from https://nodejs.org"
  exit 1
fi

echo "    Node version: $(node --version)"
echo "    npm  version: $(npm --version)"

if ! command -v aws &>/dev/null; then
  echo "ERROR: aws CLI not found. Install from https://aws.amazon.com/cli/"
  exit 1
fi

# Verify AWS credentials are configured
if ! aws sts get-caller-identity &>/dev/null; then
  echo "ERROR: AWS credentials not configured or not valid."
  echo "  Run: aws configure"
  exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "    AWS account: ${AWS_ACCOUNT}"

# ---------------------------------------------------------------------------
# Build React frontend (placeholder config.js — will be regenerated after TF)
# ---------------------------------------------------------------------------
echo ""
echo "==> Installing React dependencies…"
npm --prefix "${ROOT_DIR}/frontend" install

echo ""
echo "==> Building React app (production bundle)…"
# Inject a temporary config.js so TypeScript build doesn't fail
# The real one (with live API URL) is generated after Terraform
mkdir -p "${ROOT_DIR}/frontend/public"
echo "/* placeholder — replaced after terraform apply */" \
  > "${ROOT_DIR}/frontend/public/config.js"

npm --prefix "${ROOT_DIR}/frontend" run build
echo "    React build complete → frontend/dist/"

# ---------------------------------------------------------------------------
# Build Lambda package
# ---------------------------------------------------------------------------
echo ""
echo "==> Building Lambda package…"

# Clean previous build
rm -rf "${LAMBDA_PKG_DIR}"
mkdir -p "${LAMBDA_PKG_DIR}"

# Install third-party dependencies into the package directory.
# boto3 is excluded because Lambda's Python 3.11 runtime already includes it.
echo "    Installing Python dependencies from lambda/requirements.txt…"
python3 -m pip install \
  --requirement "${LAMBDA_SRC_DIR}/requirements.txt" \
  --target "${LAMBDA_PKG_DIR}" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  --quiet

# Copy Lambda source files
echo "    Copying Lambda source files…"
cp "${LAMBDA_SRC_DIR}"/*.py "${LAMBDA_PKG_DIR}/"

echo "    Lambda package ready: ${LAMBDA_PKG_DIR}/"
echo "    Contents:"
ls -1 "${LAMBDA_PKG_DIR}/"

# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------
echo ""
echo "==> Initialising Terraform…"
cd "${TF_DIR}"
# Use local backend when no TF_STATE_BUCKET is set (typical for local dev).
# In CI the GitHub Actions workflow passes -backend-config flags instead.
if [[ -n "${TF_STATE_BUCKET:-}" ]]; then
  terraform init -upgrade -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="key=vectorless-rag/terraform.tfstate" \
    -backend-config="region=${TF_REGION:-ap-southeast-1}"
else
  terraform init -upgrade -reconfigure -backend=false
fi

echo ""
echo "==> Planning Terraform changes…"

# Build -var overrides only for flags that were passed
TF_VAR_ARGS=()
[[ -n "${TF_REGION}" ]] && TF_VAR_ARGS+=("-var" "aws_region=${TF_REGION}")
[[ -n "${TF_MODEL}"  ]] && TF_VAR_ARGS+=("-var" "bedrock_model_id=${TF_MODEL}")

terraform plan "${TF_VAR_ARGS[@]+"${TF_VAR_ARGS[@]}"}" -out=tfplan

echo ""
echo "==> Applying Terraform…"
terraform apply tfplan
rm -f tfplan

# ---------------------------------------------------------------------------
# Capture Terraform outputs
# ---------------------------------------------------------------------------
API_BASE_URL=$(terraform output -raw api_base_url       2>/dev/null || echo "")
WEBSITE_BUCKET=$(terraform output -raw website_bucket_name 2>/dev/null || echo "")
WEBSITE_URL=$(terraform output -raw website_url          2>/dev/null || echo "")
DOCS_BUCKET=$(terraform output -raw documents_bucket_name 2>/dev/null || echo "")

# ---------------------------------------------------------------------------
# Deploy frontend to S3 website bucket
# ---------------------------------------------------------------------------
if [[ -n "${WEBSITE_BUCKET}" && -n "${API_BASE_URL}" ]]; then
  echo ""
  echo "==> Deploying React frontend to s3://${WEBSITE_BUCKET}…"

  FRONTEND_DIR="${ROOT_DIR}/frontend"

  # Inject real API URL into config.js and rebuild
  cat > "${FRONTEND_DIR}/public/config.js" <<CONFIG
// Auto-generated by deploy.sh — do not edit manually.
window.RAG_API_URL = "${API_BASE_URL}";
CONFIG

  # Rebuild with real API URL baked into public/config.js
  npm --prefix "${FRONTEND_DIR}" run build

  # Sync entire dist/ to S3 (JS chunks, CSS, index.html, config.js)
  aws s3 sync "${FRONTEND_DIR}/dist/" "s3://${WEBSITE_BUCKET}/" \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "index.html" \
    --exclude "config.js"

  # HTML + config: no-cache so updates take effect immediately
  aws s3 cp "${FRONTEND_DIR}/dist/index.html" "s3://${WEBSITE_BUCKET}/index.html" \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate"

  aws s3 cp "${FRONTEND_DIR}/dist/config.js" "s3://${WEBSITE_BUCKET}/config.js" \
    --content-type "application/javascript" \
    --cache-control "no-cache, no-store, must-revalidate" \
    2>/dev/null || true  # config.js may not exist in dist if vite excluded it

  # Also upload from public/ directly in case vite didn't copy it
  aws s3 cp "${FRONTEND_DIR}/public/config.js" "s3://${WEBSITE_BUCKET}/config.js" \
    --content-type "application/javascript" \
    --cache-control "no-cache, no-store, must-revalidate"

  echo "    Frontend deployed! ✓"
else
  echo ""
  echo "  WARN: Could not deploy frontend (missing WEBSITE_BUCKET or API_BASE_URL)."
  echo "        Run 'terraform output' and upload frontend/dist/ manually."
fi

# ---------------------------------------------------------------------------
# Print outputs
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Deployment complete!"
echo "============================================================"
terraform output

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🌐  Open the demo UI in your browser:"
echo "      ${WEBSITE_URL}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The UI lets you:"
echo "  1. Upload PDF or Markdown files directly from your browser"
echo "  2. Wait for Bedrock to index them (30-90s)"
echo "  3. Ask natural language questions and get grounded answers"
echo ""
echo "Or use curl:"
INGEST_URL=$(terraform output -raw ingest_endpoint 2>/dev/null || echo "<ingest_endpoint>")
QUERY_URL=$(terraform output -raw query_endpoint   2>/dev/null || echo "<query_endpoint>")
echo "  aws s3 cp my-doc.pdf s3://${DOCS_BUCKET}/documents/my-doc.pdf"
echo "  curl -s -X POST '${INGEST_URL}' -H 'Content-Type: application/json' \\"
echo "    -d '{\"s3_key\": \"documents/my-doc.pdf\", \"doc_id\": \"my-doc\"}'"
echo "  curl -s -X POST '${QUERY_URL}'  -H 'Content-Type: application/json' \\"
echo "    -d '{\"doc_id\": \"my-doc\", \"question\": \"What is this about?\"}'"
