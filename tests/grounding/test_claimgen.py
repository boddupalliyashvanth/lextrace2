"""Tests for TASK 1 — claimgen.py (claim generation)."""

from __future__ import annotations

import json

from lextrace.grounding.claimgen import (
    _format_chunk_xml,
    format_prompt,
    generate_claims,
    parse_claims,
)
from lextrace.grounding.models import Claim, ClaimKind
from lextrace.types import Hit

# ---------------------------------------------------------------------------
# Hit helpers
# ---------------------------------------------------------------------------


def _hit(chunk_id: str, doc: str, text: str, page: int | None = 1) -> Hit:
    return Hit(chunk_id=chunk_id, doc=doc, page=page, text=text)


SAMPLE_HITS = [
    _hit("c1", "doc-1", "The court held that Section 302 applies.", 1),
    _hit("c2", "doc-2", "The penalty was Rs. 5,00,000.", 3),
]


# ---------------------------------------------------------------------------
# Prompt formatting tests
# ---------------------------------------------------------------------------


class TestFormatChunkXml:
    def test_basic(self):
        h = _hit("c1", "doc-1", "Hello world", 1)
        xml = _format_chunk_xml(h)
        assert xml == "<chunk id='c1' doc='doc-1' page='1'>Hello world</chunk>"

    def test_no_page(self):
        h = _hit("c1", "doc-1", "Hello world", None)
        xml = _format_chunk_xml(h)
        assert "page=" not in xml
        assert xml == "<chunk id='c1' doc='doc-1'>Hello world</chunk>"


class TestFormatPrompt:
    def test_contains_task(self):
        prompt = format_prompt("What is Section 302?", SAMPLE_HITS)
        assert "What is Section 302?" in prompt

    def test_contains_all_chunks(self):
        prompt = format_prompt("task", SAMPLE_HITS)
        assert "c1" in prompt
        assert "c2" in prompt
        assert "The court held" in prompt
        assert "Rs. 5,00,000" in prompt

    def test_system_rules_present(self):
        prompt = format_prompt("task", SAMPLE_HITS)
        assert "VERBATIM" in prompt or "verbatim" in prompt.lower()
        assert "DATA" in prompt

    def test_empty_hits(self):
        prompt = format_prompt("task", [])
        assert "task" in prompt


# ---------------------------------------------------------------------------
# Response parsing tests
# ---------------------------------------------------------------------------


class TestParseClaims:
    def test_valid_json_array(self):
        raw = json.dumps([
            {
                "text": "The penalty was Rs. 5,00,000.",
                "kind": "numerical",
                "evidence": [{"chunk_id": "c2", "quote": "Rs. 5,00,000"}],
            }
        ])
        claims = parse_claims(raw)
        assert len(claims) == 1
        assert claims[0].kind == ClaimKind.NUMERICAL
        assert claims[0].evidence[0].chunk_id == "c2"

    def test_empty_array(self):
        assert parse_claims("[]") == []

    def test_empty_string(self):
        assert parse_claims("") == []

    def test_markdown_fenced(self):
        raw = "```json\n" + json.dumps([
            {
                "text": "Test claim.",
                "kind": "factual",
                "evidence": [{"chunk_id": "c1", "quote": "Test"}],
            }
        ]) + "\n```"
        claims = parse_claims(raw)
        assert len(claims) == 1

    def test_invalid_json(self):
        assert parse_claims("{not valid json}") == []

    def test_not_an_array(self):
        assert parse_claims('{"text": "single object"}') == []

    def test_missing_evidence_skipped(self):
        raw = json.dumps([
            {"text": "No evidence.", "kind": "factual", "evidence": []},
            {
                "text": "Valid.",
                "kind": "factual",
                "evidence": [{"chunk_id": "c1", "quote": "Valid"}],
            },
        ])
        claims = parse_claims(raw)
        # First claim should be skipped (no evidence), second should pass
        assert len(claims) == 1
        assert claims[0].text == "Valid."

    def test_quote_too_long_skipped(self):
        raw = json.dumps([
            {
                "text": "Long quote claim.",
                "kind": "factual",
                "evidence": [{"chunk_id": "c1", "quote": "x" * 301}],
            }
        ])
        claims = parse_claims(raw)
        assert len(claims) == 0

    def test_invalid_kind_skipped(self):
        raw = json.dumps([
            {
                "text": "Bad kind.",
                "kind": "nonexistent_kind",
                "evidence": [{"chunk_id": "c1", "quote": "test"}],
            }
        ])
        claims = parse_claims(raw)
        assert len(claims) == 0


# ---------------------------------------------------------------------------
# generate_claims integration
# ---------------------------------------------------------------------------


class TestGenerateClaims:
    def test_returns_parsed_claims(self):
        response = json.dumps([
            {
                "text": "Section 302 applies.",
                "kind": "legal",
                "evidence": [{"chunk_id": "c1", "quote": "Section 302 applies"}],
            }
        ])

        def mock_llm(prompt: str) -> str:
            return response

        claims = generate_claims("What applies?", SAMPLE_HITS, llm_call=mock_llm)
        assert len(claims) == 1
        assert isinstance(claims[0], Claim)

    def test_empty_hits_returns_empty(self):
        claims = generate_claims("task", [], llm_call=lambda p: "[]")
        assert claims == []

    def test_llm_returns_empty(self):
        claims = generate_claims(
            "task", SAMPLE_HITS, llm_call=lambda p: "[]"
        )
        assert claims == []
