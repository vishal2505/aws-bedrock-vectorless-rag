"""
ingest_handler.py
-----------------
AWS Lambda handler for POST /ingest.

Workflow
--------
1. Receive { "s3_key": "...", "doc_id": "optional" } from API Gateway.
2. Download the document from S3.
3. Detect file type (PDF or Markdown).
4. Build a hierarchical tree via pageindex_like_indexer.build_tree()
   — this calls Bedrock to summarise each node.
5. Persist to DynamoDB:
     PK=doc_id, SK="tree_metadata"   → JSON tree without text fields
     PK=doc_id, SK="node#<node_id>"  → full text for each leaf node
6. Return { "doc_id", "status": "indexed", "node_count" }.

DynamoDB schema
---------------
Table:       ${DYNAMODB_TABLE}
Partition key: doc_id   (String)
Sort key:      record_type (String)

record_type values:
  "tree_metadata"   → item.tree  (JSON string of stripped tree)
  "node#<node_id>"  → item.text  (full leaf-node text)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from pageindex_like_indexer import build_tree, flatten_tree, strip_text_from_tree
from utils import error, get_dynamodb, get_s3, parse_body, success

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

BUCKET_NAME: str = os.environ.get("DOCUMENTS_BUCKET", "")
TABLE_NAME: str = os.environ.get("DYNAMODB_TABLE", "")

# ---------------------------------------------------------------------------
# Async self-invocation
#
# API Gateway has a hard 29-second timeout but ingestion can take 30-90s
# (one Bedrock call per document node). When called from API Gateway we
# immediately return 202 and re-invoke ourselves asynchronously to do the
# real work. The frontend polls GET /documents until the doc appears.
# ---------------------------------------------------------------------------

_lambda_client = None

def _get_lambda():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client(
            "lambda", region_name=os.environ.get("AWS_REGION", "ap-southeast-1")
        )
    return _lambda_client


def _is_apigw_event(event: dict) -> bool:
    """Return True when invoked through API Gateway (has httpMethod)."""
    return "httpMethod" in event or "requestContext" in event


def _invoke_async(function_name: str, payload: dict) -> None:
    """Fire-and-forget Lambda invocation (InvocationType=Event)."""
    _get_lambda().invoke(
        FunctionName=function_name,
        InvocationType="Event",       # async — returns immediately
        Payload=json.dumps(payload).encode(),
    )
    logger.info("Async self-invocation triggered for function=%s", function_name)

# DynamoDB items cannot exceed 400 KB. Chunk large texts so that a single
# page never exceeds this limit (with headroom for attribute overhead).
_MAX_ITEM_TEXT_BYTES: int = 350_000


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """
    Lambda handler for POST /ingest.

    When called from API Gateway:
        • Validates input, fires async self-invocation, returns 202 immediately.
        • The frontend polls GET /documents until the doc appears.

    When called asynchronously (re-invoked by itself):
        • Runs the full Bedrock indexing pipeline and persists results.
        • Return value is ignored by Lambda async invocation.

    Request body (JSON):
        {
            "s3_key": "documents/my-report.pdf",
            "doc_id": "optional-custom-id"   ← omit to auto-generate
        }

    202 response (API Gateway path):
        { "doc_id": "...", "status": "processing" }

    200 response (local dev / direct invocation):
        { "doc_id": "...", "status": "indexed", "node_count": 14 }
    """
    logger.info("Ingest invoked | event keys: %s", list(event.keys()))

    # ── Async worker path (re-invoked by ourselves) ──────────────────────────
    # The async payload does NOT have httpMethod/requestContext, so we detect
    # it by the absence of those keys. We still parse body the same way.
    if not _is_apigw_event(event):
        return _run_ingestion(event, context)

    # ── API Gateway path ─────────────────────────────────────────────────────
    try:
        body = parse_body(event)

        s3_key: Optional[str] = body.get("s3_key")
        if not s3_key:
            return error(400, "Missing required field: s3_key")

        doc_id: str = body.get("doc_id") or str(uuid.uuid4())
        logger.info("API Gateway call — triggering async ingest | doc_id=%s s3_key=%s", doc_id, s3_key)

        _invoke_async(
            context.function_name,
            {"s3_key": s3_key, "doc_id": doc_id},
        )

        return success({"doc_id": doc_id, "status": "processing"}, status_code=202)

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.exception("AWS ClientError triggering async ingest: %s", error_code)
        return error(500, f"AWS error [{error_code}]: {exc.response['Error']['Message']}")
    except Exception as exc:
        logger.exception("Unhandled error triggering async ingest")
        return error(500, f"Internal error: {exc}")


def _run_ingestion(event: dict, context) -> dict:
    """Full ingestion pipeline — runs asynchronously (or in local dev)."""
    logger.info("Running ingestion pipeline | event keys: %s", list(event.keys()))

    try:
        body = parse_body(event)

        s3_key: Optional[str] = body.get("s3_key")
        if not s3_key:
            logger.error("Async ingest missing s3_key — cannot proceed")
            return error(400, "Missing required field: s3_key")

        doc_id: str = body.get("doc_id") or str(uuid.uuid4())
        logger.info("Starting ingestion | doc_id=%s s3_key=%s", doc_id, s3_key)

        # Step 1 — Download document
        file_bytes, file_type = _download_document(s3_key)
        logger.info(
            "Downloaded %d bytes from s3://%s/%s (type=%s)",
            len(file_bytes),
            BUCKET_NAME,
            s3_key,
            file_type,
        )

        # Step 2 — Build the hierarchical tree (calls Bedrock for summaries)
        logger.info("Building document tree with Bedrock summaries…")
        tree = build_tree(file_bytes, file_type)

        # Step 3 — Separate metadata (for fast tree search) from node texts
        tree_metadata = strip_text_from_tree(tree)
        node_texts: dict[str, str] = flatten_tree(tree)
        logger.info("Tree ready | %d leaf nodes", len(node_texts))

        # Step 4 — Persist to DynamoDB
        _persist_to_dynamodb(doc_id, s3_key, tree_metadata, node_texts)

        logger.info("Ingestion complete | doc_id=%s node_count=%d", doc_id, len(node_texts))
        return success({
            "doc_id": doc_id,
            "status": "indexed",
            "node_count": len(node_texts),
        })

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.exception("AWS ClientError during ingestion: %s", error_code)
        return error(500, f"AWS error [{error_code}]: {exc.response['Error']['Message']}")
    except Exception as exc:
        logger.exception("Unhandled error in ingest pipeline")
        return error(500, f"Internal error: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_document(s3_key: str) -> tuple[bytes, str]:
    """
    Download a document from the documents S3 bucket and detect its type.

    Returns:
        (file_bytes, file_type)  where file_type is "pdf" or "markdown".
    """
    try:
        response = get_s3().get_object(Bucket=BUCKET_NAME, Key=s3_key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            raise ValueError(f"Document not found in S3: {s3_key}") from exc
        raise

    file_bytes: bytes = response["Body"].read()

    # Detect type from key extension first, then from magic bytes
    key_lower = s3_key.lower()
    if key_lower.endswith(".pdf"):
        return file_bytes, "pdf"
    if key_lower.endswith((".md", ".markdown", ".txt")):
        return file_bytes, "markdown"

    # Magic bytes fallback: PDF starts with "%PDF"
    if file_bytes[:4] == b"%PDF":
        return file_bytes, "pdf"

    # Default to Markdown/text
    return file_bytes, "markdown"


def _persist_to_dynamodb(
    doc_id: str,
    s3_key: str,
    tree_metadata: list[dict],
    node_texts: dict[str, str],
) -> None:
    """
    Write tree metadata and per-node texts to DynamoDB.

    Layout:
      PK=doc_id SK=tree_metadata  → full JSON tree (without text)
      PK=doc_id SK=node#<id>      → text for that leaf node
    """
    table = get_dynamodb().Table(TABLE_NAME)

    # --- Store leaf node texts FIRST (batched for efficiency) ---
    # IMPORTANT: node texts must be written before tree_metadata.
    # The frontend polls for tree_metadata to appear; writing it last
    # guarantees all node texts exist by the time the poll succeeds,
    # preventing "Selected node IDs were not found in storage" errors.
    with table.batch_writer() as batch:
        for node_id, text in node_texts.items():
            # Truncate oversized texts to stay within DynamoDB 400 KB item limit
            if len(text.encode("utf-8")) > _MAX_ITEM_TEXT_BYTES:
                logger.warning(
                    "Node %s text exceeds %d bytes — truncating",
                    node_id,
                    _MAX_ITEM_TEXT_BYTES,
                )
                text = text.encode("utf-8")[:_MAX_ITEM_TEXT_BYTES].decode("utf-8", errors="ignore")

            batch.put_item(Item={
                "doc_id": doc_id,
                "record_type": f"node#{node_id}",
                "node_id": node_id,
                "text": text,
            })

    logger.debug("Stored %d node text items for doc_id=%s", len(node_texts), doc_id)

    # --- Store tree metadata LAST (signals readiness to the frontend poller) ---
    tree_json = json.dumps(tree_metadata, ensure_ascii=False)
    table.put_item(Item={
        "doc_id": doc_id,
        "record_type": "tree_metadata",
        "s3_key": s3_key,
        "tree": tree_json,
        "node_count": len(node_texts),
    })
    logger.debug("Stored tree_metadata for doc_id=%s (%d chars)", doc_id, len(tree_json))


