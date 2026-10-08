"""TASK 3 — Missing Information / Slot Filling.

Extracts targeted information and runs procedural anomaly checks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from lextrace.analysis.models import MissingItem, SlotSpec, SlotStatus, SlotValue
from lextrace.grounding.models import Claim

logger = logging.getLogger(__name__)


class SlotFiller:
    def __init__(
        self,
        llm_call: Callable[[str, str], str],
    ):
        self.llm_call = llm_call

    def fill_slots(self, specs: list[SlotSpec], chunks: dict[str, str]) -> list[SlotValue]:
        """Attempt to fill slots from the provided chunks."""
        results = []

        for spec in specs:
            prompt = f"Find information for: {spec.name}\\nDescription: {spec.description}\\nHints: {spec.source_hints}\\nChunks: {chunks}\\nExtract the value as a factual claim, or output 'NOT_FOUND'."
            resp = self.llm_call(prompt, "retriever").strip()

            if "NOT_FOUND" in resp.upper():
                results.append(SlotValue(
                    spec=spec,
                    status=SlotStatus.NOT_FOUND,
                    value="not found in the provided documents"
                ))
            else:
                # We would normally parse this into a Claim, verify it, etc.
                # For this prototype we will assume it's filled and create a dummy verified claim.
                # Since we don't have the verifier here, we'll just store the value.
                results.append(SlotValue(
                    spec=spec,
                    status=SlotStatus.FILLED,
                    value=resp
                ))

        return results

    def check_anomalies(self, claims: list[Claim], chunks: dict[str, str]) -> list[MissingItem]:
        """Run rule-based anomaly checks (e.g. unsigned pages, missing docs)."""
        items = []

        chunk_text = " ".join(chunks.values()).lower()

        # 1. Unsigned or undated pages
        if "unsigned" in chunk_text or "undated" in chunk_text:
            items.append(MissingItem(
                description="Reference to unsigned or undated pages found in documents.",
            ))

        # 2. Missing annexures
        if "annexure" in chunk_text and "not found" in chunk_text:
            items.append(MissingItem(
                description="Annexure referenced but potentially missing from bundle."
            ))

        # In a real implementation, we'd do a rigorous chronological check for Incident -> FIR delay

        return items

def get_default_slots(doc_kinds: list[str]) -> list[SlotSpec]:
    """Provide default slots based on document types."""
    slots = []
    if "FIR" in doc_kinds:
        slots.extend([
            SlotSpec(name="FIR Date", description="The date the FIR was filed.", source_hints=["FIR form top right"]),
            SlotSpec(name="Informant Name", description="Name of the person who filed the FIR.", source_hints=["Informant section"])
        ])
    if "Judgment" in doc_kinds:
        slots.extend([
            SlotSpec(name="Verdict", description="The final decision of the court.", source_hints=["Operative portion"]),
        ])
    return slots
