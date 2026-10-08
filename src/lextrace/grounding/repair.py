"""TASK 3 — Repair.

Builds a prompt to repair a failed claim based on failure reasons.
"""

from __future__ import annotations

from lextrace.grounding.models import Claim


def build_repair_prompt(claim: Claim, failure_reasons: list[str], chunks: dict[str, str]) -> str:
    """Build a prompt to repair an unsupported or rejected claim."""

    reasons_str = "\n".join(f"- {r}" for r in failure_reasons)

    chunks_str = ""
    for ev in claim.evidence:
        if ev.chunk_id in chunks:
            chunks_str += f"Chunk {ev.chunk_id}:\n{chunks[ev.chunk_id]}\n\n"

    prompt = f"""You are a legal grounding repair agent.
A previously generated claim was rejected by the verifier/gatekeeper.

ORIGINAL CLAIM:
{claim.text}

FAILURE REASONS:
{reasons_str}

AVAILABLE EVIDENCE CHUNKS:
{chunks_str}

INSTRUCTIONS:
1. Revise the claim so that it perfectly aligns with the evidence and addresses the failure reasons.
2. The revised claim must be strictly factual and fully supported.
3. If the claim cannot be repaired using the available evidence, output exactly: DROP_CLAIM
4. Otherwise, output ONLY the revised claim text.
"""
    return prompt
