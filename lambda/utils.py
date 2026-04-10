"""
utils.py
--------
Shared utilities for all Lambda handlers.

Centralises:
  - HTTP response construction (CORS headers in one place)
  - Request body parsing (API Gateway proxy event or plain dict)
  - Lazy AWS client/resource factories (import without credentials configured)
"""

from __future__ import annotations

import json
import os
from typing import Any

# ---------------------------------------------------------------------------
# CORS headers applied to every response
# ---------------------------------------------------------------------------

_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def success(body: Any, status_code: int = 200) -> dict:
    """Return a Lambda proxy success response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": _CORS_HEADERS,
        "body": json.dumps(body),
    }


def error(status_code: int, message: str) -> dict:
    """Return a Lambda proxy error response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": _CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def parse_body(event: dict) -> dict:
    """
    Extract the JSON body from a Lambda event.

    API Gateway wraps the body as a JSON string; direct Lambda
    invocations (and local FastAPI tests) may pass a dict directly.
    """
    body = event.get("body", event)
    if isinstance(body, str):
        return json.loads(body)
    return body if isinstance(body, dict) else {}


# ---------------------------------------------------------------------------
# Lazy AWS client factories
#
# Initialised on first request rather than at module load so that Lambda
# handlers can be imported without AWS credentials configured (e.g. during
# local startup before .env is loaded).
# ---------------------------------------------------------------------------

_aws_region = os.environ.get("AWS_REGION", "ap-southeast-1")

_s3_client = None
_dynamodb_resource = None


def get_s3():
    """Return a shared boto3 S3 client, creating it on first call."""
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client(
            "s3", region_name=os.environ.get("AWS_REGION", _aws_region)
        )
    return _s3_client


def get_dynamodb():
    """Return a shared boto3 DynamoDB resource, creating it on first call."""
    global _dynamodb_resource
    if _dynamodb_resource is None:
        import boto3
        _dynamodb_resource = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", _aws_region)
        )
    return _dynamodb_resource
