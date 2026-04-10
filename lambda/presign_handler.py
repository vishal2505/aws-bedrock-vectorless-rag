"""
presign_handler.py
------------------
Lambda handler for POST /presign.

Returns a short-lived presigned S3 PUT URL so the browser can upload
a document directly to S3 without routing through API Gateway
(avoids the 10 MB payload limit and keeps Lambda memory usage low).

Flow:
  Browser → POST /presign { filename, content_type }
          ← { presigned_url, s3_key }
  Browser → PUT <presigned_url>   (direct to S3, no Lambda involved)
  Browser → POST /ingest { s3_key, doc_id }
"""

from __future__ import annotations

import logging
import os
import re
import uuid

from botocore.exceptions import ClientError

from utils import error, get_s3, parse_body, success

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

BUCKET_NAME: str = os.environ.get("DOCUMENTS_BUCKET", "")
PRESIGN_EXPIRY: int = int(os.environ.get("PRESIGN_EXPIRY_SECONDS", "300"))  # 5 min


def handler(event: dict, context) -> dict:
    """
    Lambda handler for POST /presign.

    Request body:
        { "filename": "annual-report.pdf", "content_type": "application/pdf" }

    Success response:
        {
            "presigned_url": "https://s3.amazonaws.com/...",
            "s3_key":        "documents/a1b2c3-annual-report.pdf"
        }
    """
    try:
        body = parse_body(event)

        filename: str = body.get("filename", "document")
        content_type: str = body.get("content_type", "application/octet-stream")

        # Sanitise the filename to prevent path traversal / odd S3 keys
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", filename)
        safe_name = safe_name[:120]  # cap length

        # Unique key so re-uploads of the same file name don't collide
        s3_key = f"documents/{uuid.uuid4()}-{safe_name}"

        logger.info("Generating presigned URL | bucket=%s key=%s", BUCKET_NAME, s3_key)

        presigned_url = get_s3().generate_presigned_url(
            "put_object",
            Params={
                "Bucket":      BUCKET_NAME,
                "Key":         s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGN_EXPIRY,
        )

        return success({
            "presigned_url": presigned_url,
            "s3_key":        s3_key,
        })

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.exception("AWS ClientError in presign: %s", error_code)
        return error(500, f"AWS error [{error_code}]: {exc.response['Error']['Message']}")
    except Exception as exc:
        logger.exception("Unhandled error in presign_handler")
        return error(500, f"Internal error: {exc}")
