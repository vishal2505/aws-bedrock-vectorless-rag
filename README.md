# Vectorless RAG on AWS Bedrock

A production-structured Retrieval-Augmented Generation (RAG) system built on AWS using **no vector database** and **no embeddings**. Instead it uses a PageIndex-style hierarchical tree where an LLM reasons over document summaries to identify relevant sections before generating a grounded answer.

---

## How it works

```
Document
   │
   ▼
[Ingest Lambda]
   ├─ Parse PDF/Markdown → sections
   ├─ Build hierarchical tree (node_id, title, text)
   ├─ Call Bedrock to SUMMARISE each node (bottom-up)
   ├─ Store tree metadata (no text) → DynamoDB
   └─ Store node texts separately   → DynamoDB

Query
   │
   ▼
[Query Lambda]
   ├─ Load tree metadata for doc_id (titles + summaries only)
   ├─ Call Bedrock: "Which node IDs contain the answer?" → node_list
   ├─ Fetch full text for those nodes ← DynamoDB
   └─ Call Bedrock: generate grounded answer → JSON response
```

**Why vectorless?**
Traditional RAG embeds every chunk and does cosine similarity search. Vectorless RAG asks the LLM to *reason* over a compact document map (titles + summaries) to select the right sections — no embeddings, no vector store, no similarity math.

---

## Architecture

| Component | Service |
|-----------|---------|
| Document storage | S3 |
| Tree index + node texts | DynamoDB (PK: `doc_id`, SK: `record_type`) |
| Ingestion logic | AWS Lambda (Python 3.11) |
| Query / RAG logic | AWS Lambda (Python 3.11) |
| REST API | Amazon API Gateway |
| LLM | Amazon Bedrock (Claude via Converse API) |
| Frontend UI | React + Vite + Tailwind, hosted on S3 |
| Infrastructure | Terraform |

---

## Project structure

```
.
├── README.md
├── app.py                     # FastAPI local dev server (wraps Lambda handlers)
├── requirements-dev.txt       # Local dev dependencies (fastapi, uvicorn, boto3…)
├── .env.example               # Template for local environment variables
│
├── lambda/                    # AWS Lambda function source
│   ├── utils.py               # Shared helpers (CORS, response, body parsing, AWS clients)
│   ├── bedrock_client.py      # Bedrock Converse API wrapper (retry, summarise, answer)
│   ├── pageindex_like_indexer.py  # Document parser + hierarchical tree builder
│   ├── ingest_handler.py      # Lambda: POST /ingest
│   ├── query_handler.py       # Lambda: POST /query
│   ├── presign_handler.py     # Lambda: POST /presign (S3 presigned upload URLs)
│   ├── list_handler.py        # Lambda: GET /documents
│   └── requirements.txt       # Lambda runtime deps (pypdf only; boto3 is built-in)
│
├── frontend/                  # React + TypeScript + Tailwind UI
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── types.ts
│       ├── components/        # Header, UploadPanel, DocumentList, QueryPanel, …
│       └── hooks/             # useTypewriter
│
├── terraform/                 # Infrastructure as Code
│   ├── provider.tf            # Terraform & AWS provider
│   ├── variables.tf           # Input variables (region, model, timeouts…)
│   ├── main.tf                # S3, DynamoDB, Lambda, API Gateway
│   ├── iam.tf                 # IAM roles and inline policies
│   ├── cors.tf                # API Gateway OPTIONS CORS preflight methods
│   ├── website.tf             # S3 static website + S3 CORS for browser uploads
│   └── outputs.tf             # Outputs (API URL, bucket names, website URL)
│
└── scripts/
    └── deploy.sh              # One-shot build + Terraform deploy
```

---

## Local Development

Run the full stack on your machine against real AWS resources (S3, DynamoDB, Bedrock). No Docker, no LocalStack required.

### Prerequisites

| Tool | Required for |
|------|-------------|
| Python 3.9+ | FastAPI backend |
| pip | Python packages |
| Node.js 18+ & npm | React frontend |
| AWS CLI v2 | S3 / DynamoDB / Bedrock access |
| AWS account | With Bedrock model access enabled |

### 1. Enable Bedrock model access

In the AWS Console → **Amazon Bedrock → Model access**, request access for **Claude 3 Haiku** (or whichever model you intend to use) in your target region.

### 2. Create AWS resources for local testing

These commands create the S3 bucket and DynamoDB table used by the local server.
Replace `YOUR_ACCOUNT_ID` with your 12-digit AWS account ID.

```bash
export AWS_REGION=ap-southeast-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# S3 bucket for documents
aws s3 mb s3://vectorless-rag-docs-${AWS_ACCOUNT_ID} --region ${AWS_REGION}

# DynamoDB table (on-demand billing, no capacity planning)
aws dynamodb create-table \
  --table-name vectorless-rag-rag-index \
  --attribute-definitions \
      AttributeName=doc_id,AttributeType=S \
      AttributeName=record_type,AttributeType=S \
  --key-schema \
      AttributeName=doc_id,KeyType=HASH \
      AttributeName=record_type,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region ${AWS_REGION}

# Confirm both resources exist
aws s3 ls | grep vectorless-rag-docs
aws dynamodb describe-table --table-name vectorless-rag-rag-index \
  --query "Table.TableStatus" --output text
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```ini
# .env
AWS_REGION=ap-southeast-1
DOCUMENTS_BUCKET=vectorless-rag-docs-YOUR_ACCOUNT_ID
DYNAMODB_TABLE=vectorless-rag-rag-index
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
MAX_RETRIEVED_NODES=5
```

### 4. Start the FastAPI backend

```bash
# Install dependencies (using your Python — adjust path if using Anaconda)
pip install -r requirements-dev.txt
# or: /opt/anaconda3/bin/pip install -r requirements-dev.txt

# Start the server (auto-reloads on code changes)
python -m uvicorn app:app --reload --port 8000
# or: /opt/anaconda3/bin/python3 -m uvicorn app:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
```

### 5. Start the React frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 6. Connect the UI to the local API

1. Open [http://localhost:5173](http://localhost:5173)
2. Click the gear icon (⚙️) in the top-right
3. Enter `http://localhost:8000` as the API URL
4. Click **Save & Connect**

The document list will load and you're ready to test.

### 7. Test with curl (local)

```bash
export BUCKET="vectorless-rag-docs-$(aws sts get-caller-identity --query Account --output text)"

# Upload a document to S3
aws s3 cp ./my-report.pdf s3://${BUCKET}/documents/my-report.pdf

# Ingest it (calls Bedrock to build the tree — takes 30-90 s for a typical PDF)
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"s3_key": "documents/my-report.pdf", "doc_id": "my-report"}' | python3 -m json.tool

# Query it
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "my-report", "question": "What are the main recommendations?"}' | python3 -m json.tool

# List all indexed documents
curl -s http://localhost:8000/documents | python3 -m json.tool
```

### 8. Clean up local testing resources

When you are done with local testing and want to remove the manually-created AWS resources:

```bash
export AWS_REGION=ap-southeast-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET="vectorless-rag-docs-${AWS_ACCOUNT_ID}"

# 1. Delete all objects inside the S3 bucket first
aws s3 rm s3://${BUCKET} --recursive

# 2. Delete the S3 bucket itself
aws s3 rb s3://${BUCKET}

# 3. Delete the DynamoDB table
aws dynamodb delete-table \
  --table-name vectorless-rag-rag-index \
  --region ${AWS_REGION}

# Confirm deletion
echo "Waiting for DynamoDB table to be deleted..."
aws dynamodb wait table-not-exists --table-name vectorless-rag-rag-index
echo "All local testing resources deleted."
```

> **Note:** Do not run these if you have already deployed via Terraform — Terraform manages those resources and `terraform destroy` should be used instead.

---

## AWS Deployment (Terraform)

Deploy the entire stack to AWS with a single command.

### Prerequisites

In addition to the local dev prerequisites above, you need:

| Tool | Install |
|------|---------|
| Terraform ≥ 1.5 | [hashicorp.com/terraform](https://developer.hashicorp.com/terraform/downloads) |
| Node.js 18+ & npm | Required by `deploy.sh` to build the React app |

### 0. Create the Terraform state bucket (one-time setup)

Terraform stores its state remotely in S3 so that both local runs and GitHub Actions share the same state. This bucket must be created **once** before any deployment.

```bash
# The state bucket for this project
export TF_STATE_BUCKET="vectorless-rag-infra-tf-state-1"
export AWS_REGION=ap-southeast-1

# Create the bucket
aws s3 mb s3://${TF_STATE_BUCKET} --region ${AWS_REGION}

# Enable versioning so you can recover from accidental state corruption
aws s3api put-bucket-versioning \
  --bucket ${TF_STATE_BUCKET} \
  --versioning-configuration Status=Enabled

# Block all public access (state files must never be public)
aws s3api put-public-access-block \
  --bucket ${TF_STATE_BUCKET} \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "Terraform state bucket ready: s3://${TF_STATE_BUCKET}"
```

> This bucket is **separate** from the application documents bucket (`vectorless-rag-docs-*`). Never delete it while you have live Terraform-managed infrastructure.

### 1. Run the deploy script

```bash
./scripts/deploy.sh
```

This script automatically:
1. Checks all prerequisites (python, node, npm, terraform, aws)
2. Installs React dependencies and builds the frontend
3. Installs Python Lambda dependencies into `lambda_package/`
4. Runs `terraform init && terraform plan && terraform apply`
5. Captures the API Gateway URL from Terraform outputs
6. Re-builds the React app with the real API URL injected
7. Syncs the React build to the S3 website bucket

**Optional flags:**

```bash
./scripts/deploy.sh \
  --region us-east-1 \
  --model anthropic.claude-3-sonnet-20240229-v1:0
```

Default region is `ap-southeast-1`. Default model is `Claude 3 Haiku`.

### 2. Note the outputs

After `deploy.sh` finishes you'll see:

```
api_base_url           = "https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod"
documents_bucket_name  = "vectorless-rag-docs-123456789012"
website_url            = "http://vectorless-rag-website-123456789012.s3-website-ap-southeast-1.amazonaws.com"
```

### 3. Open the web UI

Navigate to the `website_url` in your browser. The UI works exactly like the local version — upload, index, and query documents.

### 4. Test with curl (AWS)

```bash
export API_URL="https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod"
export BUCKET="vectorless-rag-docs-123456789012"

# Upload a document
aws s3 cp ./my-report.pdf s3://${BUCKET}/documents/my-report.pdf

# Ingest
curl -s -X POST "${API_URL}/ingest" \
  -H "Content-Type: application/json" \
  -d '{"s3_key": "documents/my-report.pdf", "doc_id": "my-report"}' | python3 -m json.tool

# Query
curl -s -X POST "${API_URL}/query" \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "my-report", "question": "What are the main recommendations?"}' | python3 -m json.tool
```

---

## DynamoDB schema

Table name: `${project_name}-rag-index`

| Attribute | Type | Description |
|-----------|------|-------------|
| `doc_id` | String (PK) | Document identifier |
| `record_type` | String (SK) | `"tree_metadata"` or `"node#<node_id>"` |
| `tree` | String | JSON tree without text (metadata record) |
| `s3_key` | String | Original S3 object key |
| `node_count` | Number | Number of leaf nodes |
| `node_id` | String | Node identifier (node records only) |
| `text` | String | Full section text (node records only) |

---

## Terraform variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `ap-southeast-1` | Deployment region |
| `project_name` | `vectorless-rag` | Resource name prefix |
| `bedrock_model_id` | `anthropic.claude-3-haiku-20240307-v1:0` | Bedrock model |
| `lambda_timeout` | `300` | Lambda timeout (seconds) |
| `lambda_memory_size` | `512` | Lambda memory (MB) |
| `max_retrieved_nodes` | `5` | Max nodes fetched per query |
| `log_retention_days` | `14` | CloudWatch log retention |
| `allowed_cors_origin` | `*` | CORS header value |

Override without editing files:

```bash
terraform -chdir=terraform apply \
  -var="aws_region=us-east-1" \
  -var="bedrock_model_id=anthropic.claude-3-sonnet-20240229-v1:0" \
  -var="max_retrieved_nodes=8"
```

---

## Viewing logs

```bash
# Ingest function (live tail)
aws logs tail /aws/lambda/vectorless-rag-ingest --follow

# Query function (live tail)
aws logs tail /aws/lambda/vectorless-rag-query --follow
```

---

## Re-deploying after code changes

Any change to Lambda Python files or the React frontend:

```bash
./scripts/deploy.sh
```

The script rebuilds the Lambda package and the React app. Terraform detects the changed zip hash and updates both.

---

## Destroying all resources

### Via GitHub Actions (recommended)

Go to **Actions → Deploy / Destroy Vectorless RAG → Run workflow**, select **action = destroy**, and click **Run workflow**. The workflow will empty the S3 buckets and run `terraform destroy` automatically.

### Via CLI (manual)

```bash
export AWS_REGION=ap-southeast-1
export TF_STATE_BUCKET="vectorless-rag-infra-tf-state-1"

# 1. Empty the application S3 buckets (Terraform cannot delete non-empty buckets)
DOCS_BUCKET=$(terraform -chdir=terraform output -raw documents_bucket_name 2>/dev/null || echo "")
WEBSITE_BUCKET=$(terraform -chdir=terraform output -raw website_bucket_name 2>/dev/null || echo "")

[ -n "$DOCS_BUCKET" ]    && aws s3 rm s3://$DOCS_BUCKET    --recursive
[ -n "$WEBSITE_BUCKET" ] && aws s3 rm s3://$WEBSITE_BUCKET --recursive

# 2. Destroy all Terraform-managed infrastructure
TF_VAR_aws_region=${AWS_REGION} \
terraform -chdir=terraform destroy \
  -var="aws_region=${AWS_REGION}"
```

> - This permanently deletes the application S3 buckets, DynamoDB table, Lambda functions, and API Gateway.
> - CloudWatch log groups are **not** deleted (they expire naturally per the `log_retention_days` variable).
> - The **Terraform state bucket** (`vectorless-rag-infra-tf-state-1`) is intentionally left intact so you can redeploy cleanly. Delete it manually only when you are done with the project entirely:
>   ```bash
>   aws s3 rm s3://vectorless-rag-infra-tf-state-1 --recursive
>   aws s3 rb s3://vectorless-rag-infra-tf-state-1
>   ```

---

## Troubleshooting

**`CloudWatch Logs role ARN must be set in account settings` during Terraform apply**

```
BadRequestException: CloudWatch Logs role ARN must be set in account settings to enable logging
```

API Gateway requires an IAM role to be registered at the AWS account level before any stage can write access logs to CloudWatch. This is handled automatically by Terraform via the `aws_api_gateway_account` resource in `iam.tf` — no manual action needed. If you see this error it means you applied Terraform without the `aws_api_gateway_account` resource (older version of the code). Pull the latest code and re-run the deployment.

---

**`S3 bucket does not exist` during `terraform init` (GitHub Actions or CLI)**

```
Error: Failed to get existing workspaces: S3 bucket "vectorless-rag-infra-tf-state-1" does not exist.
```

The Terraform remote state bucket must be created **manually once** before any deployment. This is a one-time prerequisite — run from your local terminal:

```bash
export TF_STATE_BUCKET="vectorless-rag-infra-tf-state-1"
export AWS_REGION=ap-southeast-1

aws s3 mb s3://${TF_STATE_BUCKET} --region ${AWS_REGION}

aws s3api put-bucket-versioning \
  --bucket ${TF_STATE_BUCKET} \
  --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
  --bucket ${TF_STATE_BUCKET} \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

Once the bucket exists, re-trigger the GitHub Actions workflow (push a commit or use **Run workflow**).

**`AccessDeniedException` from Bedrock**
- The model is not enabled. Go to AWS Console → Amazon Bedrock → Model access and enable the model in your region.
- Confirm the `bedrock_model_id` variable matches the enabled model exactly (case-sensitive).

**Ingestion times out**
- Increase `lambda_timeout` (max 900 s) and optionally `lambda_memory_size`.
- For very large PDFs, consider splitting the document first.

**`No indexed document found` on query**
- Confirm the `doc_id` matches what was returned by `/ingest`.
- Check DynamoDB directly:
  ```bash
  aws dynamodb get-item \
    --table-name vectorless-rag-rag-index \
    --key '{"doc_id":{"S":"my-doc"},"record_type":{"S":"tree_metadata"}}'
  ```

**`lambda_package/` not found during `terraform plan`**
- Always run `./scripts/deploy.sh` (not `terraform apply` directly) — the script builds the package first.

**React UI can't reach the API**
- On local: confirm the FastAPI server is running on port 8000 and the Settings modal shows `http://localhost:8000`.
- On AWS: check the `website_url` output and ensure the `config.js` file on S3 has the correct API URL (check via browser DevTools → Network → `config.js`).

---

## Adding authentication

The API currently uses `authorization = "NONE"`. To add an API key:

1. In `terraform/main.tf`, set `api_key_required = true` on each method and add:
   ```hcl
   resource "aws_api_gateway_api_key" "default" { ... }
   resource "aws_api_gateway_usage_plan" "default" { ... }
   ```
2. Pass the key in requests: `-H "x-api-key: YOUR_KEY"`

For IAM or Cognito auth, change `authorization` to `"AWS_IAM"` or `"COGNITO_USER_POOLS"` and add the corresponding Terraform resources.
