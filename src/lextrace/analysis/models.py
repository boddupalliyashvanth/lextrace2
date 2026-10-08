"""Pydantic models for the analysis subsystem (Contradictions & Missing Info)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from lextrace.grounding.models import VerifiedClaim


class FactTuple(BaseModel):
    """A structured fact extracted from a verified claim."""
    entity: str
    attribute: str
    value: str
    claim: VerifiedClaim


class Contradiction(BaseModel):
    """A contradiction between two claims."""
    claim_a: VerifiedClaim
    claim_b: VerifiedClaim
    explanation: str


class SlotSpec(BaseModel):
    """Specification for information to extract."""
    name: str
    description: str
    required: bool = False
    value_type: str = "string"
    source_hints: list[str] = Field(default_factory=list)


class SlotStatus(str):
    FILLED = "filled"
    CONFLICTING = "conflicting"
    LOW_CONFIDENCE = "low_confidence"
    NOT_FOUND = "not_found"


class SlotValue(BaseModel):
    """The result of a slot filling attempt."""
    spec: SlotSpec
    status: str
    value: str | None = None
    claim: VerifiedClaim | None = None


class MissingItem(BaseModel):
    """An anomaly or missing procedural item."""
    description: str
    evidence_context: str | None = None
