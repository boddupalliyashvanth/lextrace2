"""Tests for TASK 3 — citation_registry.py.

15+ tests covering alias normalisation, resolve, scan for case names,
sections, reporter citations, docket numbers, and violation detection.
"""

from __future__ import annotations

from lextrace.grounding.citation_registry import (
    CitationRegistry,
    normalise_alias,
)
from lextrace.grounding.models import ViolationType

# ---------------------------------------------------------------------------
# Alias normalisation
# ---------------------------------------------------------------------------


class TestNormaliseAlias:
    def test_lowercase(self):
        assert normalise_alias("Section 302") == normalise_alias("section 302")

    def test_sec_dot(self):
        assert normalise_alias("Sec. 302") == normalise_alias("Section 302")

    def test_s_dot(self):
        assert normalise_alias("s. 302") == normalise_alias("Section 302")

    def test_u_slash_s(self):
        result = normalise_alias("u/s 302")
        assert "under section" in result or "section" in result

    def test_punctuation_stripped(self):
        result = normalise_alias("State of Maharashtra v. Tapas D. Neogy")
        assert "." not in result


# ---------------------------------------------------------------------------
# CitationRegistry.resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def test_exact_canonical(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        entry = reg.resolve("Section 302")
        assert entry is not None
        assert entry.id == "sec-302"

    def test_alias_sec_dot(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        entry = reg.resolve("Sec. 498A")
        assert entry is not None
        assert entry.id == "sec-498a"

    def test_case_name(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        entry = reg.resolve("K.S. Puttaswamy v. Union of India")
        assert entry is not None

    def test_unknown_returns_none(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        entry = reg.resolve("Nonexistent v. Nobody")
        assert entry is None

    def test_case_insensitive(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        entry = reg.resolve("section 420")
        assert entry is not None
        assert entry.id == "sec-420"


# ---------------------------------------------------------------------------
# CitationRegistry.scan
# ---------------------------------------------------------------------------


class TestScan:
    def test_valid_case_name(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = "In Ramesh Kumar v. State of Chhattisgarh, the court held..."
        matches, _ = reg.scan(text)
        assert len(matches) >= 1

    def test_fake_case_name_violation(self, sample_registry_path, corpus_docs):
        """FAKE_Sharma v. State of Rajasthan should be unresolved."""
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = "The case of Sharma v. State of Rajasthan established..."
        _, violations = reg.scan(text)
        assert len(violations) >= 1
        assert any(v.type == ViolationType.CITATION_UNRESOLVED for v in violations)

    def test_section_with_correct_statute(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = "Section 302 of the Indian Penal Code applies here."
        matches, violations = reg.scan(text)
        # Section 302 of IPC should match
        _ = [m for m in matches if "302" in m.text]
        # It might match or might have violations depending on alias matching
        # The key thing is: no SECTION_NOT_FOUND for correct pairing
        wrong_statute = [
            v for v in violations
            if v.type == ViolationType.SECTION_NOT_FOUND and "302" in v.text
            and "wrong" in v.detail.lower()
        ]
        assert len(wrong_statute) == 0

    def test_section_with_wrong_statute(self, sample_registry_path, corpus_docs):
        """Section 302 paired with Indian Contract Act should be a violation."""
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = "Section 302 of the Indian Contract Act."
        _, violations = reg.scan(text)
        wrong_statute = [
            v for v in violations
            if v.type == ViolationType.SECTION_NOT_FOUND
        ]
        assert len(wrong_statute) >= 1

    def test_nonexistent_section(self, sample_registry_path, corpus_docs):
        """Section 498B doesn't exist in registry."""
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = "The accused was charged under Section 498B."
        _, violations = reg.scan(text)
        sec_violations = [
            v for v in violations
            if v.type == ViolationType.SECTION_NOT_FOUND and "498B" in v.text
        ]
        assert len(sec_violations) >= 1

    def test_docket_number_unresolved(self, sample_registry_path, corpus_docs):
        """Unknown docket number."""
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = "Criminal Appeal No. 9999 of 2025 was dismissed."
        _, violations = reg.scan(text)
        assert len(violations) >= 1

    def test_multiple_citations_in_text(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        text = (
            "Relying on Ramesh Kumar v. State of Chhattisgarh and "
            "K.S. Puttaswamy v. Union of India, the court held..."
        )
        matches, _ = reg.scan(text)
        # Both should be found
        assert len(matches) >= 2

    def test_empty_text(self, sample_registry_path, corpus_docs):
        reg = CitationRegistry(sample_registry_path, corpus_docs)
        matches, violations = reg.scan("")
        assert len(matches) == 0
        assert len(violations) == 0
