"""TASK 1 — Claim generation from retrieved chunks.

Formats a prompt from the template, calls the LLM, parses and validates
the JSON response into a list of Claim objects.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lextrace.grounding.models import Claim
from lextrace.types import Hit

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "grounding" / "claimgen.v1.md"


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def _load_prompt_template() -> str:
    """Load the prompt template from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_chunk_xml(hit: Hit) -> str:
    """Render a single Hit as a <chunk> XML element."""
    page_attr = f" page='{hit.page}'" if hit.page is not None else ""
    return f"<chunk id='{hit.chunk_id}' doc='{hit.doc}'{page_attr}>{hit.text}</chunk>"


def format_prompt(task: str, hits: list[Hit]) -> str:
    """Build the complete prompt by rendering the template with task and chunks."""
    template = _load_prompt_template()
    chunks_xml = "\n\n".join(_format_chunk_xml(h) for h in hits)
    prompt = template.replace("{{task}}", task).replace("{{chunks}}", chunks_xml)
    return prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> str:
    """Extract a JSON array from a potentially markdown-fenced response."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip().startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end]).strip()
    return text


def parse_claims(raw_response: str) -> list[Claim]:
    """Parse and validate LLM response into a list of Claim objects.

    Returns an empty list if the response is empty or cannot be parsed.
    Raises ValueError for structurally valid JSON that fails Pydantic validation.
    """
    text = _extract_json(raw_response)
    if not text or text == "[]":
        return []

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM response as JSON: %s", exc)
        return []

    if not isinstance(data, list):
        logger.error("LLM response is not a JSON array")
        return []

    claims: list[Claim] = []
    for i, item in enumerate(data):
        try:
            claims.append(Claim.model_validate(item))
        except ValidationError as exc:
            logger.warning("Claim %d failed validation: %s", i, exc)
            # Skip invalid claims rather than failing the entire batch
            continue
    return claims


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_claims(
    task: str,
    hits: list[Hit],
    *,
    llm_call: Callable[[str], str],
) -> list[Claim]:
    """Generate atomic claims from retrieved chunks.

    Parameters
    ----------
    task:
        The user's question or task string.
    hits:
        Retrieved document chunks.
    llm_call:
        A callable that takes a prompt string and returns the LLM's raw
        text response.  This is injected for testability.

    Returns
    -------
    list[Claim]
        Validated atomic claims, or an empty list if the chunks lack
        sufficient information.
    """
    if not hits:
        logger.info("No hits provided; returning empty claims.")
        return []

    prompt = format_prompt(task, hits)
    logger.debug("Claim generation prompt length: %d chars", len(prompt))

    raw_response = llm_call(prompt)
    claims = parse_claims(raw_response)

    logger.info("Generated %d validated claims from %d hits", len(claims), len(hits))
    return claims
