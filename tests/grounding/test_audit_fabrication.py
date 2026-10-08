"""Tests for TASK 4 — audit_fabrication.py (independent audit script).

10+ tests verifying the audit script catches fabricated quotes, citations,
and facts, and passes clean data.
"""

from __future__ import annotations

# Import from the script directly (it's independent of the pipeline)
import importlib.util
import json
from pathlib import Path

from tests.conftest import CHUNKS, CORPUS_DOCS, SAMPLE_REGISTRY_DATA

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "audit_fabrication.py"
_spec = importlib.util.spec_from_file_location("audit_fabrication", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

audit_output = _mod.audit_output
load_registry = _mod.load_registry
main = _mod.main
_norm = _mod._norm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corpus(chunks: dict[str, str]) -> dict[str, str]:
    """Normalise chunks into a corpus for the audit."""
    return {k: _norm(v) for k, v in chunks.items()}


def _make_registry_file(tmp_path: Path) -> Path:
    p = tmp_path / "registry.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for entry in SAMPLE_REGISTRY_DATA:
            f.write(json.dumps(entry) + "\n")
    return p


def _make_output(claims: list[dict]) -> dict:
    return {"claims": claims}


# ---------------------------------------------------------------------------
# Quote audit
# ---------------------------------------------------------------------------


class TestQuoteAudit:
    def test_clean_quote_passes(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "The court held.",
                "evidence": [
                    {"chunk_id": "chunk-001", "quote": "the accused was entitled to bail"}
                ],
            }
        ])
        fq, _, _ = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert fq == 0

    def test_fabricated_quote_caught(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "The court held.",
                "evidence": [
                    {
                        "chunk_id": "chunk-001",
                        "quote": "This text appears absolutely nowhere in the corpus at all",
                    }
                ],
            }
        ])
        fq, _, _ = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert fq >= 1

    def test_ellipsis_quote_passes(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "Test.",
                "evidence": [
                    {
                        "chunk_id": "chunk-003",
                        "quote": "possession of small quantities…may extend to one year",
                    }
                ],
            }
        ])
        fq, _, _ = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert fq == 0


# ---------------------------------------------------------------------------
# Citation audit
# ---------------------------------------------------------------------------


class TestCitationAudit:
    def test_valid_case_no_violation(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "In Ramesh Kumar v. State of Chhattisgarh, bail was granted.",
                "evidence": [
                    {"chunk_id": "chunk-005", "quote": "Ramesh Kumar against the State of Chhattisgarh"}
                ],
            }
        ])
        _, fc, _ = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert fc == 0

    def test_fake_case_name_caught(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "In Verma v. State of Bihar, the court ruled.",
                "evidence": [
                    {"chunk_id": "chunk-001", "quote": "the accused was entitled to bail"}
                ],
            }
        ])
        _, fc, _ = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert fc >= 1


# ---------------------------------------------------------------------------
# Fact audit
# ---------------------------------------------------------------------------


class TestFactAudit:
    def test_correct_amount_passes(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "The compensation was Rs. 5,00,000.",
                "evidence": [
                    {"chunk_id": "chunk-002", "quote": "Rs. 5,00,000 (Rupees Five Lakhs)"}
                ],
            }
        ])
        _, _, ff = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert ff == 0

    def test_altered_amount_caught(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "The compensation was Rs. 5,50,000.",
                "evidence": [
                    {"chunk_id": "chunk-002", "quote": "Rs. 5,00,000"}
                ],
            }
        ])
        _, _, ff = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert ff >= 1

    def test_altered_date_caught(self, tmp_path):
        corpus = _make_corpus(CHUNKS)
        reg_path = _make_registry_file(tmp_path)
        registry = load_registry(reg_path)
        output = _make_output([
            {
                "text": "The order was dated 12.03.2020.",
                "evidence": [
                    {"chunk_id": "chunk-002", "quote": "the order dated 12.03.2019"}
                ],
            }
        ])
        _, _, ff = audit_output(output, corpus, registry, CORPUS_DOCS)
        assert ff >= 1


# ---------------------------------------------------------------------------
# main() integration via CLI
# ---------------------------------------------------------------------------


class TestMainCLI:
    def test_clean_output_exit_zero(self, tmp_path):
        # Write a clean OUTPUTS.jsonl
        outputs_path = tmp_path / "OUTPUTS.jsonl"
        corpus_path = tmp_path / "corpus.jsonl"
        reg_path = _make_registry_file(tmp_path)

        # Corpus
        with open(corpus_path, "w", encoding="utf-8") as f:
            for cid, text in CHUNKS.items():
                f.write(json.dumps({"chunk_id": cid, "text": text}) + "\n")

        # Clean output
        output = {
            "claims": [
                {
                    "text": "The accused was entitled to bail.",
                    "evidence": [
                        {
                            "chunk_id": "chunk-001",
                            "quote": "the accused was entitled to bail",
                        }
                    ],
                }
            ]
        }
        with open(outputs_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(output) + "\n")

        exit_code = main([
            str(outputs_path),
            "--corpus", str(corpus_path),
            "--registry", str(reg_path),
        ])
        assert exit_code == 0

    def test_fabricated_output_exit_nonzero(self, tmp_path):
        outputs_path = tmp_path / "OUTPUTS.jsonl"
        corpus_path = tmp_path / "corpus.jsonl"
        reg_path = _make_registry_file(tmp_path)

        with open(corpus_path, "w", encoding="utf-8") as f:
            for cid, text in CHUNKS.items():
                f.write(json.dumps({"chunk_id": cid, "text": text}) + "\n")

        # Fabricated output
        output = {
            "claims": [
                {
                    "text": "The amount was Rs. 99,99,999.",
                    "evidence": [
                        {
                            "chunk_id": "chunk-002",
                            "quote": "A completely fabricated quote that is nowhere",
                        }
                    ],
                }
            ]
        }
        with open(outputs_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(output) + "\n")

        exit_code = main([
            str(outputs_path),
            "--corpus", str(corpus_path),
            "--registry", str(reg_path),
        ])
        assert exit_code == 1
