"""
delete_handler.py
-----------------
Lambda handler for DELETE /documents/{doc_id}.

Removes all DynamoDB items for a document (tree_metadata + every node text)
so the document can be cleanly re-uploaded and re-indexed.

Note: the S3 object is intentionally left in place — only the index is
deleted. Re-ingesting the same s3_key will rebuild the index from the
existing S3 file without needing another upload.
"""

from __future__ import annotations

import logging
import os

from botocore.exceptions import ClientError

from utils import error, get_dynamodb, success

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TABLE_NAME: str = os.environ.get("DYNAMODB_TABLE", "")


def handler(event: dict, context) -> dict:
    """
    Lambda handler for DELETE /documents/{doc_id}.

    Path parameter:
        doc_id — the document identifier to delete

    Success response (200):
        { "doc_id": "...", "deleted_items": 43 }

    Error responses:
        404 — document not found
        500 — AWS error
    """
    logger.info("delete_document invoked | path params: %s", event.get("pathParameters"))

    try:
        path_params = event.get("pathParameters") or {}
        doc_id: str = path_params.get("doc_id", "")

        if not doc_id:
            return error(400, "Missing path parameter: doc_id")

        table = get_dynamodb().Table(TABLE_NAME)

        # Query ALL items for this doc_id (tree_metadata + all node#* items).
        # We only need the keys for deletion.
        response = table.query(
            KeyConditionExpression="doc_id = :pk",
            ExpressionAttributeValues={":pk": doc_id},
            ProjectionExpression="doc_id, record_type",
        )

        items = response.get("Items", [])

        # Handle DynamoDB pagination (unlikely but correct)
        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression="doc_id = :pk",
                ExpressionAttributeValues={":pk": doc_id},
                ProjectionExpression="doc_id, record_type",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        if not items:
            return error(404, f"No indexed document found with doc_id='{doc_id}'")

        logger.info("Deleting %d items for doc_id=%s", len(items), doc_id)

        # Batch delete all items
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={
                    "doc_id":      item["doc_id"],
                    "record_type": item["record_type"],
                })

        logger.info("Deleted %d items for doc_id=%s", len(items), doc_id)
        return success({"doc_id": doc_id, "deleted_items": len(items)})

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.exception("AWS ClientError in delete_handler: %s", error_code)
        return error(500, f"AWS error [{error_code}]: {exc.response['Error']['Message']}")
    except Exception as exc:
        logger.exception("Unhandled error in delete_handler")
        return error(500, f"Internal error: {exc}")
