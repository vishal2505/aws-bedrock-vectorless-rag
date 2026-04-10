"""
pageindex_like_indexer.py
-------------------------
Simplified PageIndex-style hierarchical tree builder.

Design
------
1. Parse a PDF or Markdown document into sections.
2. Build a tree where each node has:
     node_id  – unique sequential identifier (e.g. "N0001")
     title    – section heading or "Page N" for PDFs
     summary  – 2-3 sentence Bedrock-generated summary
     text     – full text (leaf nodes only)
     children – child nodes (parent nodes only)
3. Return the tree as a JSON-serialisable list of root nodes.

The caller (ingest_handler) is responsible for:
  - Stripping `text` from nodes before storing tree metadata.
  - Flattening the tree to a {node_id: text} map for node storage.
"""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Callable, Optional

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Lazy import so that the module can be imported without pypdf installed
# (e.g. during unit tests that only test Markdown parsing).
_pypdf_available: Optional[bool] = None


def _check_pypdf() -> None:
    global _pypdf_available
    if _pypdf_available is None:
        try:
            import pypdf  # noqa: F401
            _pypdf_available = True
        except ImportError:
            _pypdf_available = False
    if not _pypdf_available:
        raise ImportError(
            "pypdf is required for PDF parsing. "
            "Install it with: pip install pypdf"
        )


# ---------------------------------------------------------------------------
# Node ID generator
# ---------------------------------------------------------------------------

def _make_counter() -> Callable[[], str]:
    """
    Return a closure that yields sequential node IDs: N0001, N0002, …

    A new counter is created per build_tree() call so that each
    document's IDs start from N0001 regardless of Lambda container reuse.
    """
    state = {"n": 0}

    def next_id() -> str:
        state["n"] += 1
        return f"N{state['n']:04d}"

    return next_id


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def parse_markdown(content: str, next_id: Callable[[], str]) -> list[dict]:
    """
    Parse a Markdown document into a hierarchical section tree.

    Heading levels:
      #  → root node (h1)
      ## → child node (h2), nested under the current h1
      Any text before the first heading → a preamble leaf node.
      Documents with no headings → a single "Full Document" leaf node.

    Args:
        content: Raw Markdown text.
        next_id: Node-ID generator from _make_counter().

    Returns:
        List of root node dicts (JSON-serialisable, without summaries yet).
    """
    lines = content.split("\n")
    root_nodes: list[dict] = []

    current_h1: Optional[dict] = None
    current_h2: Optional[dict] = None
    text_buffer: list[str] = []

    def flush_h2_text() -> None:
        """Attach buffered lines as the current h2 node's text."""
        nonlocal current_h2
        if current_h2 is not None:
            current_h2["text"] = "\n".join(text_buffer).strip()
        text_buffer.clear()

    def close_h2() -> None:
        """Finalise current h2 and attach it to current h1 (or root)."""
        nonlocal current_h2
        if current_h2 is None:
            return
        flush_h2_text()
        if current_h1 is not None:
            current_h1.setdefault("children", []).append(current_h2)
        else:
            root_nodes.append(current_h2)
        current_h2 = None

    def close_h1() -> None:
        """Finalise current h1 and attach it to root list."""
        nonlocal current_h1
        close_h2()
        if current_h1 is not None:
            root_nodes.append(current_h1)
        current_h1 = None

    for line in lines:
        h1_match = re.match(r"^#\s+(.+)$", line)
        h2_match = re.match(r"^##\s+(.+)$", line)
        h3_match = re.match(r"^###\s+(.+)$", line)  # treat h3+ as inline text

        if h1_match and not h2_match:  # '#' but not '##'
            close_h1()
            current_h1 = {
                "node_id": next_id(),
                "title": h1_match.group(1).strip(),
                "children": [],
            }
        elif h2_match and not h3_match:  # '##' but not '###'
            close_h2()
            current_h2 = {
                "node_id": next_id(),
                "title": h2_match.group(1).strip(),
            }
        else:
            text_buffer.append(line)

    # Flush any remaining content
    close_h1()

    # Edge case: document has no headings at all
    if not root_nodes:
        root_nodes.append({
            "node_id": next_id(),
            "title": "Full Document",
            "text": content.strip(),
        })

    # Remove empty-children lists so the tree is clean
    _prune_empty_children(root_nodes)

    return root_nodes


def _prune_empty_children(nodes: list[dict]) -> None:
    """Remove 'children' key when the list is empty (in-place)."""
    for node in nodes:
        children = node.get("children", [])
        if not children:
            node.pop("children", None)
        else:
            _prune_empty_children(children)


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------

def parse_pdf(pdf_bytes: bytes, next_id: Callable[[], str]) -> list[dict]:
    """
    Parse a PDF into a flat list of page nodes grouped under a root node.

    Each page becomes a leaf node titled "Page N".  Empty pages (no
    extractable text) are skipped.

    Args:
        pdf_bytes: Raw PDF bytes.
        next_id:   Node-ID generator.

    Returns:
        A list containing a single root node whose children are the pages.
    """
    _check_pypdf()
    import pypdf  # type: ignore[import]

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page_nodes: list[dict] = []

    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if not text:
            logger.debug("PDF page %d has no extractable text — skipping", i + 1)
            continue
        page_nodes.append({
            "node_id": next_id(),
            "title": f"Page {i + 1}",
            "text": text,
        })

    if not page_nodes:
        # Return a single placeholder rather than an empty tree
        return [{
            "node_id": next_id(),
            "title": "Empty Document",
            "text": "No extractable text found in this PDF.",
        }]

    return [{
        "node_id": next_id(),
        "title": "Document",
        "children": page_nodes,
    }]


# ---------------------------------------------------------------------------
# Summary enrichment (calls Bedrock)
# ---------------------------------------------------------------------------

def _add_summaries(node: dict, bedrock_client: "BedrockClient") -> None:  # noqa: F821
    """
    Recursively attach a 'summary' field to every node.

    Leaf nodes (have 'text'): summarise their own text.
    Parent nodes (have 'children'): summarise from child summaries upward.

    This bottom-up approach means parent summaries reflect the combined
    content of all their descendants — an accurate table-of-contents entry.
    """
    if "children" in node:
        # Recurse depth-first so children are summarised first
        for child in node["children"]:
            _add_summaries(child, bedrock_client)

        # Build a digest of child summaries for the parent
        child_digest = "\n\n".join(
            f"{c.get('title', 'Section')}: {c.get('summary', '')}"
            for c in node["children"]
            if c.get("summary")
        )
        if child_digest.strip():
            logger.info("Summarising parent node %s (%s)", node["node_id"], node.get("title"))
            node["summary"] = bedrock_client.summarize_text(child_digest)
        else:
            node["summary"] = node.get("title", "No content")

    elif node.get("text", "").strip():
        logger.info("Summarising leaf node %s (%s)", node["node_id"], node.get("title"))
        node["summary"] = bedrock_client.summarize_text(node["text"])

    else:
        node["summary"] = "Empty section"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_tree(file_bytes: bytes, file_type: str) -> list[dict]:
    """
    Parse a document and build a hierarchical tree with Bedrock summaries.

    Args:
        file_bytes: Raw bytes of the document.
        file_type:  "pdf" or "markdown".

    Returns:
        A JSON-serialisable list of root nodes.  Each node contains:
          node_id, title, summary, and either 'text' (leaf) or 'children'.
    """
    # Import here to avoid circular imports at module level
    from bedrock_client import BedrockClient

    bedrock = BedrockClient()
    next_id = _make_counter()

    logger.info("Parsing document as %s…", file_type)

    if file_type == "pdf":
        sections = parse_pdf(file_bytes, next_id)
    else:
        content = file_bytes.decode("utf-8", errors="replace")
        sections = parse_markdown(content, next_id)

    logger.info("Parsed %d root section(s). Adding Bedrock summaries…", len(sections))

    for root_node in sections:
        _add_summaries(root_node, bedrock)

    logger.info("Tree build complete.")
    return sections


def flatten_tree(tree: list[dict]) -> dict[str, str]:
    """
    Flatten the tree into a mapping of node_id → full_text.

    Only leaf nodes (those with a 'text' field) are included.
    Parent nodes do not carry text — their content is the union of
    their children's text.

    Args:
        tree: The full document tree as returned by build_tree().

    Returns:
        Dict mapping each leaf node_id to its text content.
    """
    result: dict[str, str] = {}

    def _recurse(node: dict) -> None:
        if "text" in node and node["text"].strip():
            result[node["node_id"]] = node["text"]
        for child in node.get("children", []):
            _recurse(child)

    for root in tree:
        _recurse(root)

    return result


def strip_text_from_tree(tree: list[dict]) -> list[dict]:
    """
    Return a deep copy of the tree with all 'text' fields removed.

    The stripped tree (node_id + title + summary + children) is stored
    as the document's metadata index.  The full text is stored separately
    per node so the query handler can load only what it needs.

    Args:
        tree: Full tree as returned by build_tree().

    Returns:
        New tree with 'text' keys omitted at every level.
    """
    import copy

    def _strip(node: dict) -> dict:
        stripped: dict = {
            "node_id": node["node_id"],
            "title": node.get("title", ""),
            "summary": node.get("summary", ""),
        }
        if "children" in node:
            stripped["children"] = [_strip(c) for c in node["children"]]
        return stripped

    return [_strip(n) for n in tree]
