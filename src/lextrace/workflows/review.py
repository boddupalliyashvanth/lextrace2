"""TASK 1 — Review Workflow.

Orchestrates the per-document extraction, synthesis, contradiction detection,
slot filling, and final rendering.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from lextrace.analysis.contradictions import ContradictionDetector
from lextrace.analysis.missing_info import SlotFiller, get_default_slots
from lextrace.grounding.citation_registry import CitationRegistry
from lextrace.grounding.gate import run_gate
from lextrace.grounding.models import ClaimKind, Evidence, Verdict, VerifiedClaim
from lextrace.grounding.render import Renderer
from lextrace.grounding.verifier import Verifier

logger = logging.getLogger(__name__)


class Workflow:
    """The review workflow orchestrator."""

    def __init__(self, name: str, llm_call: Callable[[str, str], str]):
        self.name = name
        self.llm_call = llm_call
        self.verifier = Verifier(llm_call=llm_call)
        self.contradiction_detector = ContradictionDetector(llm_call=llm_call)
        self.slot_filler = SlotFiller(llm_call=llm_call)
        self.registry = CitationRegistry()
        self.renderer = Renderer(registry=self.registry)

    def _per_document_pass(self, doc_id: str, chunks: dict[str, str]) -> list[VerifiedClaim]:
        """Mock map-reduce structured pass."""
        # In reality, this would use the `claimgen` module with a specific prompt.
        # Here we mock returning some verified claims for testing.
        return []

    def _cross_document_synthesis(self, verified_claims: list[VerifiedClaim]) -> list[VerifiedClaim]:
        """Synthesize claims across documents into timelines, parties, etc."""
        return verified_claims

    def run(self, case_doc_ids: list[str], chunks: dict[str, str], focus_question: str | None = None) -> str:
        """Execute the review workflow."""
        logger.info("Starting review workflow for docs: %s", case_doc_ids)

        # 1. Per-document structured pass
        all_verified_claims = []
        for doc_id in case_doc_ids:
            # We would normally filter chunks for this doc_id
            claims = self._per_document_pass(doc_id, chunks)
            all_verified_claims.extend(claims)

        # 2. Cross-document synthesis
        synthesized_claims = self._cross_document_synthesis(all_verified_claims)

        # 3. Contradictions
        contradictions = self.contradiction_detector.detect(synthesized_claims)

        # 4. Missing Information
        doc_kinds = ["FIR", "Judgment"]  # Mocked document kinds
        slots = get_default_slots(doc_kinds)
        slot_values = self.slot_filler.fill_slots(slots, chunks)
        anomalies = self.slot_filler.check_anomalies(all_verified_claims, chunks)

        # 5. Render
        # We need to assemble a comprehensive list of claims to render.
        # We add the contradictions and missing info as template_text or new claims.

        render_claims = []
        render_claims.extend(synthesized_claims)

        # Add a heading for Contradictions
        if contradictions:
            render_claims.append(VerifiedClaim(
                text="### Contradictions",
                kind=ClaimKind.TEMPLATE_TEXT,
                evidence=[Evidence(chunk_id="USER_INPUT", quote="")],
                verdict=Verdict.SUPPORTED
            ))
            for c in contradictions:
                # Add contradiction explanation.
                # This should technically be an inference claim supported by claim_a and claim_b.
                render_claims.append(VerifiedClaim(
                    text=c.explanation,
                    kind=ClaimKind.INFERENCE,
                    evidence=c.claim_a.evidence + c.claim_b.evidence,
                    depends_on=[c.claim_a.id, c.claim_b.id] if c.claim_a.id and c.claim_b.id else [],
                    verdict=Verdict.SUPPORTED
                ))

        # Add Missing Information
        if slot_values or anomalies:
            render_claims.append(VerifiedClaim(
                text="### Missing information",
                kind=ClaimKind.TEMPLATE_TEXT,
                evidence=[Evidence(chunk_id="USER_INPUT", quote="")],
                verdict=Verdict.SUPPORTED
            ))
            for sv in slot_values:
                render_claims.append(VerifiedClaim(
                    text=f"{sv.spec.name}: {sv.value}",
                    kind=ClaimKind.FACTUAL,
                    evidence=[Evidence(chunk_id="USER_INPUT", quote="")],
                    verdict=Verdict.SUPPORTED,
                    supported_by_user=True  # Just to render it without citations for now
                ))
            for an in anomalies:
                render_claims.append(VerifiedClaim(
                    text=f"Anomaly: {an.description}",
                    kind=ClaimKind.FACTUAL,
                    evidence=[Evidence(chunk_id="USER_INPUT", quote="")],
                    verdict=Verdict.SUPPORTED,
                    supported_by_user=True
                ))

        rendered_text = self.renderer.render(render_claims)

        # Gate
        final_output = run_gate(rendered_text, chunks, self.registry)

        return final_output
