"""
list_handler.py
---------------
Lambda handler for GET /documents.

Scans the DynamoDB table for all tree_metadata records and returns
a summary list of indexed documents so the frontend can populate
the document selector.

Response shape:
    {
        "documents": [
            {
                "doc_id":     "annual-report-2024",
                "s3_key":     "documents/uuid-annual-report.pdf",
                "node_count": 18
            },
            ...
        ]
    }
"""

from __future__ import annotations

import logging
import os

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from utils import error, get_dynamodb, success

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TABLE_NAME: str = os.environ.get("DYNAMODB_TABLE", "")


def handler(event: dict, context) -> dict:
    """
    Lambda handler for GET /documents.

    Returns all indexed documents sorted by doc_id.
    Uses a DynamoDB Scan with a FilterExpression on record_type —
    acceptable at demo scale (< a few thousand documents).
    """
    logger.info("list_documents invoked")

    try:
        table = get_dynamodb().Table(TABLE_NAME)

        # Scan for only tree_metadata records (skip individual node text items)
        response = table.scan(
            FilterExpression=Attr("record_type").eq("tree_metadata"),
            ProjectionExpression="doc_id, s3_key, node_count",
        )

        items = response.get("Items", [])

        # Handle DynamoDB pagination (unlikely for demo scale, but correct)
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression=Attr("record_type").eq("tree_metadata"),
                ProjectionExpression="doc_id, s3_key, node_count",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        # Sort alphabetically by doc_id for a consistent UI order
        documents = sorted(
            [
                {
                    "doc_id":     item.get("doc_id", ""),
                    "s3_key":     item.get("s3_key", ""),
                    "node_count": int(item.get("node_count", 0)),
                }
                for item in items
            ],
            key=lambda d: d["doc_id"],
        )

        logger.info("Returning %d document(s)", len(documents))
        return success({"documents": documents})

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.exception("AWS ClientError in list_handler: %s", error_code)
        return error(500, f"AWS error [{error_code}]: {exc.response['Error']['Message']}")
    except Exception as exc:
        logger.exception("Unhandled error in list_handler")
        return error(500, f"Internal error: {exc}")
