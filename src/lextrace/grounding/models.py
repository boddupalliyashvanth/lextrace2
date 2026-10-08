"""Pydantic models for the grounding subsystem."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Claim models
# ---------------------------------------------------------------------------


class ClaimKind(StrEnum):
    """The kind of atomic claim."""

    FACTUAL = "factual"
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    LEGAL = "legal"
    PROCEDURAL = "procedural"
    TEMPLATE_TEXT = "template_text"
    INFERENCE = "inference"


class Evidence(BaseModel):
    """A single piece of evidence backing a claim."""

    chunk_id: str
    quote: str = Field(max_length=300)


class Claim(BaseModel):
    """An atomic, evidence-backed proposition."""

    id: str | None = None
    text: str
    kind: ClaimKind
    evidence: list[Evidence]
    depends_on: list[str] = Field(default_factory=list)

    @field_validator("evidence")
    @classmethod
    def at_least_one_evidence(cls, v: list[Evidence]) -> list[Evidence]:
        if len(v) < 1:
            raise ValueError("At least one Evidence entry is required")
        return v


# ---------------------------------------------------------------------------
# Verifier models
# ---------------------------------------------------------------------------


class Verdict(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class VerifiedClaim(Claim):
    """A claim that has been processed by the verifier."""

    verdict: Verdict
    score: float = 0.0
    rationale: str = ""
    supported_by_user: bool = False


# ---------------------------------------------------------------------------
# Check / Violation models
# ---------------------------------------------------------------------------


class ViolationType(StrEnum):
    """Types of grounding violations."""

    CHUNK_NOT_FOUND = "CHUNK_NOT_FOUND"
    QUOTE_NOT_VERBATIM = "QUOTE_NOT_VERBATIM"
    NUMBER_MISMATCH = "NUMBER_MISMATCH"
    INJECTION_SUSPECTED = "INJECTION_SUSPECTED"
    CITATION_UNRESOLVED = "CITATION_UNRESOLVED"
    SECTION_NOT_FOUND = "SECTION_NOT_FOUND"


class Violation(BaseModel):
    """A single grounding violation."""

    type: ViolationType
    claim_text: str | None = None
    chunk_id: str | None = None
    detail: str = ""
    reason: str | None = None


class CheckResult(BaseModel):
    """Result of running deterministic checks on a single claim."""

    claim_text: str
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    snapped_quotes: dict[str, str] = Field(default_factory=dict)
    """Maps original quote -> snapped quote when quote_snapped applies."""


# ---------------------------------------------------------------------------
# Citation Registry models
# ---------------------------------------------------------------------------


class RegistryEntryType(StrEnum):
    CASE = "case"
    STATUTE = "statute"
    SECTION = "section"


class RegistryEntry(BaseModel):
    """An entry in the citation registry."""

    id: str
    type: RegistryEntryType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    document: str
    statute: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationMatch(BaseModel):
    """A citation-like string that resolved successfully."""

    text: str
    start: int
    end: int
    entry: RegistryEntry


class CitationViolation(BaseModel):
    """A citation-like string that failed to resolve."""

    type: ViolationType
    text: str
    start: int
    end: int
    detail: str = ""
