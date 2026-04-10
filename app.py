"""
app.py — Local FastAPI dev server
----------------------------------
Wraps the Lambda handlers so you can call POST /ingest and POST /query
locally without deploying to AWS.

Requirements (install once):
    pip install -r requirements-dev.txt

Run:
    uvicorn app:app --reload --port 8000

Environment variables (set in .env or export before running):
    DOCUMENTS_BUCKET   - your S3 bucket name (must exist in AWS)
    DYNAMODB_TABLE     - your DynamoDB table name (must exist in AWS)
    BEDROCK_MODEL_ID   - e.g. anthropic.claude-3-haiku-20240307-v1:0
    AWS_REGION         - e.g. ap-southeast-1
    AWS_PROFILE        - optional, AWS named profile to use

Note: AWS credentials must be configured locally (aws configure / SSO / env vars).
      This server calls real AWS services — it is NOT a full offline emulator.
"""

import json
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env file if present (never committed to git)
load_dotenv()

# Add lambda/ to sys.path so handler imports work without packaging
_lambda_dir = os.path.join(os.path.dirname(__file__), "lambda")
if _lambda_dir not in sys.path:
    sys.path.insert(0, _lambda_dir)

# Lazy import after env is loaded
import ingest_handler
import query_handler
import presign_handler
import list_handler
import delete_handler

app = FastAPI(
    title="Vectorless RAG — local dev server",
    description="Local wrapper around Lambda handlers for development & testing.",
    version="0.0.1",
)

# Allow the React dev server (port 5173) to call the API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _lambda_event(body: dict) -> dict:
    """Wrap a plain dict as a minimal API Gateway proxy event."""
    return {"body": json.dumps(body)}


def _lambda_response(raw: dict) -> JSONResponse:
    """Convert a Lambda proxy response dict into a FastAPI JSONResponse."""
    status = raw.get("statusCode", 200)
    body = raw.get("body", "{}")
    return JSONResponse(content=json.loads(body), status_code=status)


@app.post("/ingest")
async def ingest(request: Request):
    """
    Trigger ingestion of a document already uploaded to S3.

    Body: { "s3_key": "documents/my.pdf", "doc_id": "optional-id" }
    """
    body = await request.json()
    result = ingest_handler.handler(_lambda_event(body), None)
    return _lambda_response(result)


@app.post("/query")
async def query(request: Request):
    """
    Ask a question against an indexed document.

    Body: { "doc_id": "my-doc", "question": "What are the findings?" }
    """
    body = await request.json()
    result = query_handler.handler(_lambda_event(body), None)
    return _lambda_response(result)


@app.post("/presign")
async def presign(request: Request):
    """
    Return a presigned S3 PUT URL so the browser can upload directly.

    Body: { "filename": "report.pdf", "content_type": "application/pdf" }
    """
    body = await request.json()
    result = presign_handler.handler(_lambda_event(body), None)
    return _lambda_response(result)


@app.get("/documents")
async def list_documents():
    """List all indexed documents from DynamoDB."""
    result = list_handler.handler({}, None)
    return _lambda_response(result)


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete all index data for a document so it can be re-uploaded."""
    event = {"pathParameters": {"doc_id": doc_id}}
    result = delete_handler.handler(event, None)
    return _lambda_response(result)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "env": {
            "DOCUMENTS_BUCKET": os.environ.get("DOCUMENTS_BUCKET", "NOT SET"),
            "DYNAMODB_TABLE":   os.environ.get("DYNAMODB_TABLE",   "NOT SET"),
            "BEDROCK_MODEL_ID": os.environ.get("BEDROCK_MODEL_ID", "NOT SET"),
            "AWS_REGION":       os.environ.get("AWS_REGION",       "NOT SET"),
        },
    }
