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

from botocore.exceptions import ClientError

from pageindex_like_indexer import build_tree, flatten_tree, strip_text_from_tree
from utils import error, get_dynamodb, get_s3, parse_body, success

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

BUCKET_NAME: str = os.environ.get("DOCUMENTS_BUCKET", "")
TABLE_NAME: str = os.environ.get("DYNAMODB_TABLE", "")

# DynamoDB items cannot exceed 400 KB. Chunk large texts so that a single
# page never exceeds this limit (with headroom for attribute overhead).
_MAX_ITEM_TEXT_BYTES: int = 350_000


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """
    Lambda handler for POST /ingest.

    Expected request body (JSON):
        {
            "s3_key": "documents/my-report.pdf",
            "doc_id": "optional-custom-id"        ← omit to auto-generate
        }

    Success response (HTTP 200):
        {
            "doc_id": "...",
            "status": "indexed",
            "node_count": 14
        }

    Error responses (HTTP 4xx / 5xx):
        { "error": "human-readable message" }
    """
    logger.info("Ingest invoked | event keys: %s", list(event.keys()))

    try:
        body = parse_body(event)

        s3_key: Optional[str] = body.get("s3_key")
        if not s3_key:
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
        logger.exception("Unhandled error in ingest_handler")
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

    # --- Store tree metadata ---
    tree_json = json.dumps(tree_metadata, ensure_ascii=False)
    table.put_item(Item={
        "doc_id": doc_id,
        "record_type": "tree_metadata",
        "s3_key": s3_key,
        "tree": tree_json,
        "node_count": len(node_texts),
    })
    logger.debug("Stored tree_metadata for doc_id=%s (%d chars)", doc_id, len(tree_json))

    # --- Store leaf node texts (batched for efficiency) ---
    with table.batch_writer() as batch:
        for node_id, text in node_texts.items():
            # Truncate oversized texts to stay within DynamoDB 400 KB item limit
            if len(text.encode("utf-8")) > _MAX_ITEM_TEXT_BYTES:
                logger.warning(
                    "Node %s text exceeds %d bytes — truncating",
                    node_id,
                    _MAX_ITEM_TEXT_BYTES,
                )
                # Truncate safely at a UTF-8 boundary
                text = text.encode("utf-8")[:_MAX_ITEM_TEXT_BYTES].decode("utf-8", errors="ignore")

            batch.put_item(Item={
                "doc_id": doc_id,
                "record_type": f"node#{node_id}",
                "node_id": node_id,
                "text": text,
            })

    logger.debug("Stored %d node text items for doc_id=%s", len(node_texts), doc_id)


