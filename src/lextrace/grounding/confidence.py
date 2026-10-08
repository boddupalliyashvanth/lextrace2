"""TASK 1 — Confidence scoring.

Computes multi-factorial confidence for verified claims and produces a report.
"""

from __future__ import annotations

import logging
from pydantic import BaseModel
from typing import Any

from lextrace.grounding.models import VerifiedClaim, Verdict
from lextrace.analysis.models import SlotValue, SlotStatus

logger = logging.getLogger(__name__)


class ConfidenceReport(BaseModel):
    """Report generated before P4's drafting workflow."""
    slots_filled_with_confidence: list[SlotValue]
    conflicting_slots: list[SlotValue]
    slots_not_found: list[SlotValue]
    recommended_documents_to_obtain: list[str]


def compute_claim_confidence(
    claim: VerifiedClaim, 
    retrieval_rank: int = 1, 
    verifier_score: float = 1.0, 
    quote_snapped: bool = False
) -> float:
    """Compute a single float confidence [0.0, 1.0] for a claim.
    
    Args:
        claim: The VerifiedClaim object.
        retrieval_rank: The rank of the retrieved chunk (mocked as 1 by default).
        verifier_score: Score from verifier (e.g. 0.0 to 1.0).
        quote_snapped: True if fuzzy matching was required to snap the quote.
    """
    if claim.verdict != Verdict.SUPPORTED:
        return 0.0
        
    # Base confidence comes from the verifier
    confidence = verifier_score
    
    # Retrieval rank penalty (simple decay)
    rank_penalty = 1.0 / (retrieval_rank + 1) if retrieval_rank > 0 else 0.5
    confidence *= rank_penalty
    
    # Independent chunks bonus
    independent_chunks = len({e.chunk_id for e in claim.evidence})
    if independent_chunks > 1:
        confidence = min(1.0, confidence + 0.1 * (independent_chunks - 1))
        
    # Quote snapped penalty
    if quote_snapped:
        confidence *= 0.8
        
    return max(0.0, min(1.0, confidence))


def compute_overall_confidence(claims: list[VerifiedClaim]) -> float:
    """Compute overall confidence across all supported claims."""
    supported = [c for c in claims if c.verdict == Verdict.SUPPORTED]
    if not supported:
        return 0.0
    scores = [compute_claim_confidence(c) for c in supported]
    return sum(scores) / len(scores)


def generate_confidence_report(slot_values: list[SlotValue]) -> ConfidenceReport:
    """Generate a Confidence and Missing Info Report for P4."""
    filled = []
    conflicting = []
    not_found = []
    missing_doc_kinds = set()
    
    for sv in slot_values:
        if sv.status == SlotStatus.FILLED:
            # Here we might also check if confidence > threshold
            filled.append(sv)
        elif sv.status == SlotStatus.CONFLICTING:
            conflicting.append(sv)
        elif sv.status == SlotStatus.NOT_FOUND:
            not_found.append(sv)
            # Infer missing document type based on slot description/hints
            hints = " ".join(sv.spec.source_hints).lower()
            if "fir" in hints:
                missing_doc_kinds.add("FIR Document")
            elif "medical" in hints or "injury" in hints:
                missing_doc_kinds.add("Medical Report")
            else:
                missing_doc_kinds.add(f"Document containing {sv.spec.name}")
                
    return ConfidenceReport(
        slots_filled_with_confidence=filled,
        conflicting_slots=conflicting,
        slots_not_found=not_found,
        recommended_documents_to_obtain=list(missing_doc_kinds)
    )
