"""
bedrock_client.py
-----------------
Thin wrapper around Amazon Bedrock Runtime (Converse API).

All LLM calls in this project go through this module so that
prompt engineering, error handling, and model selection are
concentrated in one place and easy to swap or tune.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


class BedrockClient:
    """
    Wraps boto3 bedrock-runtime with three high-level helpers:
      - summarize_text(text)          → short summary string
      - call_for_json(prompt)         → parsed Python object
      - generate_answer(question, context) → raw JSON string
    """

    def __init__(self) -> None:
        self.model_id: str = os.environ.get(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-haiku-20240307-v1:0",
        )
        self.region: str = os.environ.get("AWS_REGION", "ap-southeast-1")
        self._client = boto3.client("bedrock-runtime", region_name=self.region)
        logger.info(
            "BedrockClient initialised | model=%s region=%s",
            self.model_id,
            self.region,
        )

    # ------------------------------------------------------------------
    # Core low-level helper
    # ------------------------------------------------------------------

    def _converse(
        self,
        messages: list[dict],
        *,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        retries: int = 3,
    ) -> str:
        """
        Call Bedrock Converse API with automatic retry on throttling.

        Args:
            messages:    List of {"role": "user"|"assistant", "content": [{"text": "..."}]}
            system:      Optional system-prompt string.
            temperature: Sampling temperature (0–1).
            max_tokens:  Maximum tokens in the response.
            retries:     Number of retry attempts on throttling errors.

        Returns:
            The model's response text.
        """
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
        }
        if system:
            kwargs["system"] = [{"text": system}]

        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                response = self._client.converse(**kwargs)
                return response["output"]["message"]["content"][0]["text"]
            except ClientError as exc:
                error_code = exc.response["Error"]["Code"]
                if error_code in ("ThrottlingException", "ServiceUnavailableException"):
                    wait = 2 ** attempt  # exponential back-off: 2s, 4s, 8s
                    logger.warning(
                        "Bedrock throttled (attempt %d/%d). Retrying in %ds…",
                        attempt,
                        retries,
                        wait,
                    )
                    time.sleep(wait)
                    last_exc = exc
                else:
                    logger.error("Bedrock ClientError: %s", exc)
                    raise

        raise RuntimeError(
            f"Bedrock call failed after {retries} retries"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def summarize_text(self, text: str) -> str:
        """
        Generate a concise 2-3 sentence summary of *text*.

        Used when building the document tree so that parent nodes
        carry meaningful summaries derived from their children.

        Args:
            text: The section text to summarise (truncated internally
                  to avoid exceeding context limits).

        Returns:
            A 2-3 sentence summary string.
        """
        # Truncate to ~3 000 chars to stay well within token limits for
        # haiku-class models while keeping latency low.
        truncated = text[:3_000]

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            "Summarise the following text in 2-3 concise sentences.\n"
                            "Focus on key concepts and main points.\n"
                            "Return ONLY the summary — no preamble, no labels.\n\n"
                            f"TEXT:\n{truncated}"
                        )
                    }
                ],
            }
        ]
        summary = self._converse(messages, temperature=0.1, max_tokens=256)
        logger.debug("summarize_text → %d chars", len(summary))
        return summary.strip()

    def call_for_json(self, prompt: str) -> Any:
        """
        Send *prompt* to Bedrock and parse the response as JSON.

        The system prompt instructs the model to return raw JSON with
        no markdown fences or prose so that parsing is reliable.

        Args:
            prompt: Full prompt text that asks for a JSON response.

        Returns:
            Parsed Python object (dict or list).

        Raises:
            json.JSONDecodeError: If the model returns non-JSON output
                                  even after stripping markdown fences.
        """
        system = (
            "You are a precise retrieval assistant. "
            "You ALWAYS respond with valid JSON only — "
            "no markdown code blocks, no explanation, no trailing text. "
            "Just the raw JSON object."
        )
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        raw = self._converse(
            messages,
            system=system,
            temperature=0.0,  # deterministic for structured output
            max_tokens=512,
        )

        # Strip accidental markdown fences the model sometimes adds
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(
                "call_for_json: failed to parse JSON.\nRaw response: %s", raw
            )
            raise

    def generate_answer(self, question: str, context: str) -> str:
        """
        Generate a grounded answer given *question* and retrieved *context*.

        The model is instructed to answer ONLY from the provided context
        and to return a structured JSON object so downstream code can
        extract the answer and citations cleanly.

        Args:
            question: The user's question.
            context:  Concatenated text of retrieved document nodes,
                      wrapped in [NODE: id] … [/NODE: id] markers.

        Returns:
            A raw JSON string (not yet parsed) with keys:
              - "answer"             – the answer text
              - "used_node_ids"      – list of node ID strings cited
              - "raw_context_excerpt"– short verbatim excerpt from context
        """
        prompt = f"""\
You are a helpful, precise assistant that answers questions strictly from provided context.

INSTRUCTIONS:
1. Read the CONTEXT sections below carefully.
2. Answer the QUESTION using ONLY information found in the context.
3. If the answer is not in the context, say: "The provided documents do not contain enough information to answer this question."
4. After composing your answer, return a JSON object with these exact keys:
   - "answer"              : your full answer as a plain string
   - "used_node_ids"       : JSON array of node IDs (strings) you actually used
   - "raw_context_excerpt" : 1-3 sentence verbatim quote from the context most relevant to the answer

Return ONLY the JSON object — no markdown, no code blocks, no surrounding text.

---
CONTEXT:
{context}
---

QUESTION: {question}

JSON response:"""

        system = (
            "You are a precise question-answering assistant. "
            "You return structured JSON responses and never add prose outside the JSON."
        )
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        raw = self._converse(
            messages,
            system=system,
            temperature=0.1,
            max_tokens=1_024,
        )

        # Strip markdown fences if the model added them
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw).strip()
        return raw
