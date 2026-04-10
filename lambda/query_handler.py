"""
query_handler.py
----------------
AWS Lambda handler for POST /query.

Vectorless RAG workflow (PageIndex-style)
-----------------------------------------
Step 1  Load tree metadata (node IDs + titles + summaries, NO full text)
        from DynamoDB for the requested doc_id.

Step 2  RETRIEVAL — call Bedrock with:
          • The user's question
          • The compact tree (id + title + summary per node)
        Bedrock reasons over the summaries and returns a JSON list of
        node IDs most likely to contain the answer.
        ↳ No embeddings, no vector search — pure LLM reasoning.

Step 3  FETCH — load full text for the selected node IDs from DynamoDB.

Step 4  ANSWER — call Bedrock again with the question + retrieved text
        and ask for a grounded, structured JSON answer.

Response shape:
    {
        "answer":              "...",
        "used_node_ids":       ["N0003", "N0007"],
        "raw_context_excerpt": "Short verbatim quote..."
    }
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from botocore.exceptions import ClientError

from bedrock_client import BedrockClient
from utils import error, get_dynamodb, parse_body, success

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Lazy Bedrock client — initialised on first request
_bedrock: Optional[BedrockClient] = None


def _get_bedrock() -> BedrockClient:
    global _bedrock
    if _bedrock is None:
        _bedrock = BedrockClient()
    return _bedrock


TABLE_NAME: str = os.environ.get("DYNAMODB_TABLE", "")

# Maximum number of nodes to retrieve full text for in a single query.
# Keeps context size manageable and latency predictable.
_MAX_RETRIEVED_NODES: int = int(os.environ.get("MAX_RETRIEVED_NODES", "5"))

# ---------------------------------------------------------------------------
# Retrieval prompt
# ---------------------------------------------------------------------------

_RETRIEVAL_PROMPT_TEMPLATE = """\
You are a document retrieval assistant. Your task is to identify which sections of \
a document are most likely to contain the answer to a given question.

You will be given:
  1. A QUESTION
  2. A DOCUMENT TREE — a list of sections, each with a node_id, title, and \
summary (NOT the full text)

Your job is to return a JSON object with a single key "node_list" whose value is \
an array of node_id strings for the sections most likely to contain the answer.

Rules:
  - Return ONLY the JSON object — no markdown, no explanation, no surrounding text.
  - Include between 1 and {max_nodes} node IDs.
  - Prefer the most specific (leaf) nodes. Include a parent node only when its \
children all seem relevant.
  - If the question cannot be answered from any section, return {{"node_list": []}}.

--- EXAMPLES ---

Example tree:
[
  {{"node_id": "N0001", "title": "Executive Summary", "summary": "High-level overview of annual revenue and strategy."}},
  {{"node_id": "N0002", "title": "Q1 Results",         "summary": "Revenue of $4.2M in Q1, up 12% year-over-year."}},
  {{"node_id": "N0003", "title": "Q2 Results",         "summary": "Revenue of $5.1M in Q2 with new product launch."}}
]

Example question: "What was the revenue in Q1?"
Example output: {{"node_list": ["N0002"]}}

Example question: "Summarise the company's financial performance."
Example output: {{"node_list": ["N0001", "N0002", "N0003"]}}

--- ACTUAL INPUT ---

QUESTION: {question}

DOCUMENT TREE:
{tree_json}

Return the JSON object now:"""


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """
    Lambda handler for POST /query.

    Expected request body (JSON):
        {
            "doc_id":   "previously-ingested-document-id",
            "question": "What are the key findings?"
        }

    Success response (HTTP 200):
        {
            "answer":              "The key findings are…",
            "used_node_ids":       ["N0003", "N0007"],
            "raw_context_excerpt": "…verbatim excerpt…"
        }

    Error responses (HTTP 4xx / 5xx):
        { "error": "human-readable message" }
    """
    logger.info("Query invoked | event keys: %s", list(event.keys()))

    try:
        body = parse_body(event)

        doc_id: Optional[str] = body.get("doc_id")
        question: Optional[str] = body.get("question")

        if not doc_id:
            return error(400, "Missing required field: doc_id")
        if not question:
            return error(400, "Missing required field: question")
        if len(question) > 2_000:
            return error(400, "Field 'question' must be ≤ 2000 characters")

        logger.info("Query | doc_id=%s question=%r", doc_id, question[:120])

        # Step 1 — Load tree metadata (no full text)
        tree_metadata = _load_tree_metadata(doc_id)
        if tree_metadata is None:
            return error(404, f"No indexed document found with doc_id='{doc_id}'")

        flat_nodes = _flatten_for_prompt(tree_metadata)
        logger.info("Loaded tree | %d total nodes", len(flat_nodes))

        # Step 2 — LLM-driven retrieval: which node IDs answer the question?
        node_ids = _select_relevant_nodes(question, flat_nodes)
        logger.info("Retrieval selected %d node(s): %s", len(node_ids), node_ids)

        if not node_ids:
            # Bedrock couldn't identify relevant sections — return a safe response
            return success({
                "answer": (
                    "The retrieval step could not identify relevant sections in "
                    "the document for your question. Please try rephrasing."
                ),
                "used_node_ids": [],
                "raw_context_excerpt": "",
            })

        # Step 3 — Fetch full text for selected nodes
        node_texts = _fetch_node_texts(doc_id, node_ids)
        if not node_texts:
            return error(
                500,
                "Selected node IDs were not found in storage. "
                "The document may need to be re-indexed."
            )

        # Step 4 — Generate grounded answer
        context = _build_context(node_texts)
        logger.info(
            "Calling Bedrock for final answer | context_length=%d chars", len(context)
        )

        raw_answer = _get_bedrock().generate_answer(question, context)
        answer_obj = _parse_answer(raw_answer)

        logger.info("Query complete | doc_id=%s", doc_id)
        return success(answer_obj)

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.exception("AWS ClientError during query: %s", error_code)
        return error(500, f"AWS error [{error_code}]: {exc.response['Error']['Message']}")
    except Exception as exc:
        logger.exception("Unhandled error in query_handler")
        return error(500, f"Internal error: {exc}")


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------

def _load_tree_metadata(doc_id: str) -> Optional[list]:
    """
    Load the tree metadata record from DynamoDB.

    Returns:
        Parsed tree list, or None if the document is not found.
    """
    table = get_dynamodb().Table(TABLE_NAME)
    response = table.get_item(
        Key={"doc_id": doc_id, "record_type": "tree_metadata"}
    )
    item = response.get("Item")
    if not item:
        return None
    return json.loads(item["tree"])


def _flatten_for_prompt(tree: list[dict]) -> list[dict]:
    """
    Recursively flatten the tree into a simple list for inclusion in the
    retrieval prompt.  Each entry has node_id, title, summary only.
    """
    result: list[dict] = []

    def _recurse(node: dict) -> None:
        result.append({
            "node_id": node["node_id"],
            "title": node.get("title", ""),
            "summary": node.get("summary", ""),
        })
        for child in node.get("children", []):
            _recurse(child)

    for root in tree:
        _recurse(root)

    return result


def _select_relevant_nodes(question: str, flat_nodes: list[dict]) -> list[str]:
    """
    Ask Bedrock to identify which node IDs are most relevant to *question*.

    The model sees only node_id + title + summary (no full text), so it
    must reason over the summaries — the core of the vectorless approach.

    Returns:
        List of valid node ID strings (limited to _MAX_RETRIEVED_NODES).
    """
    tree_json = json.dumps(flat_nodes, indent=2, ensure_ascii=False)

    prompt = _RETRIEVAL_PROMPT_TEMPLATE.format(
        question=question,
        tree_json=tree_json,
        max_nodes=_MAX_RETRIEVED_NODES,
    )

    result = _get_bedrock().call_for_json(prompt)
    node_list: list = result.get("node_list", [])

    # Validate: only keep IDs that actually exist in this tree
    valid_ids: set[str] = {n["node_id"] for n in flat_nodes}
    valid_list = [nid for nid in node_list if nid in valid_ids]

    # Respect the cap
    return valid_list[:_MAX_RETRIEVED_NODES]


def _fetch_node_texts(doc_id: str, node_ids: list[str]) -> dict[str, str]:
    """
    Fetch the full text for each node ID from DynamoDB.

    Returns:
        Dict mapping node_id → text.  Missing nodes are logged and skipped.
    """
    table = get_dynamodb().Table(TABLE_NAME)
    result: dict[str, str] = {}

    for node_id in node_ids:
        response = table.get_item(
            Key={"doc_id": doc_id, "record_type": f"node#{node_id}"}
        )
        item = response.get("Item")
        if item and item.get("text"):
            result[node_id] = item["text"]
        else:
            logger.warning(
                "No text stored for node_id=%s in doc_id=%s", node_id, doc_id
            )

    return result


def _build_context(node_texts: dict[str, str]) -> str:
    """
    Combine node texts into a single context string with clear delimiters.

    The [NODE: id] … [/NODE: id] markers let the answer model cite
    specific sections and help the user trace where information came from.
    """
    parts: list[str] = []
    for node_id, text in node_texts.items():
        parts.append(f"[NODE: {node_id}]\n{text}\n[/NODE: {node_id}]")
    return "\n\n".join(parts)


def _parse_answer(raw: str) -> dict:
    """
    Parse the JSON answer string returned by BedrockClient.generate_answer().

    Falls back gracefully if the model returns malformed JSON.
    """
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw).strip()

    try:
        obj = json.loads(raw)
        return {
            "answer":              obj.get("answer", raw),
            "used_node_ids":       obj.get("used_node_ids", []),
            "raw_context_excerpt": obj.get("raw_context_excerpt", ""),
        }
    except json.JSONDecodeError:
        logger.warning("Could not parse JSON answer from Bedrock — returning raw text")
        return {
            "answer":              raw,
            "used_node_ids":       [],
            "raw_context_excerpt": "",
        }


