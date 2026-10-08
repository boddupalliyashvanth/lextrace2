"""TASK 1 — Verifier.

Runs deterministic checks, and semantic entailment to verify claims.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path

from lextrace.grounding.checks import run_checks
from lextrace.grounding.models import Claim, ClaimKind, Verdict, VerifiedClaim

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "grounding" / "verifier.v1.md"


def _extract_context(quote: str, chunk_text: str) -> str:
    """Extract a 1-sentence context window around the quote from the chunk."""
    # A simplified approach to find the quote and extract surrounding sentences.
    # We split by basic sentence boundaries (. )
    sentences = re.split(r"(?<=[.!?])\s+", chunk_text)

    start_idx = -1
    end_idx = -1
    quote_clean = re.sub(r"\s+", " ", quote).strip()

    for i, sent in enumerate(sentences):
        if quote_clean in re.sub(r"\s+", " ", sent).strip():
            start_idx = i
            end_idx = i
            break

    # If exact match not found in a single sentence (e.g. spans multiple), just find overlap
    if start_idx == -1:
        # Fallback: just return the whole chunk if it's too complex
        # Or a more robust substring search
        return chunk_text

    start_context = max(0, start_idx - 1)
    end_context = min(len(sentences), end_idx + 2)
    return " ".join(sentences[start_context:end_context])


class Verifier:
    def __init__(
        self,
        llm_call: Callable[[str, str], str],
        nli_call: Callable[[str, str], float] | None = None,
        use_nli_cross_encoder: bool = False,
    ):
        self.llm_call = llm_call
        self.nli_call = nli_call
        self.use_nli_cross_encoder = use_nli_cross_encoder
        self.template = _PROMPT_PATH.read_text(encoding="utf-8")

    def _extract_json(self, raw: str) -> str:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            text = "\n".join(lines[start:end]).strip()
        return text

    def verify(self, claims: list[Claim], chunks: dict[str, str]) -> list[VerifiedClaim]:
        """Verify a list of claims."""
        verified = []

        # Run deterministic checks on all claims first
        check_results = {cr.claim_text: cr for cr in run_checks(claims, chunks)}

        # Keep track of verified claims by ID for inference resolution
        verified_by_id: dict[str, VerifiedClaim] = {}

        for claim in claims:
            # 1. User input bypass
            if any(ev.chunk_id == "USER_INPUT" for ev in claim.evidence):
                vc = VerifiedClaim(
                    **claim.model_dump(),
                    verdict=Verdict.SUPPORTED,
                    score=1.0,
                    rationale="Provided by user.",
                    supported_by_user=True,
                )
                verified.append(vc)
                if claim.id:
                    verified_by_id[claim.id] = vc
                continue

            # 2. Deterministic checks
            cr = check_results.get(claim.text)
            if cr and not cr.passed:
                vc = VerifiedClaim(
                    **claim.model_dump(),
                    verdict=Verdict.UNSUPPORTED,
                    score=0.0,
                    rationale=f"Failed deterministic checks: {cr.violations[0].type}",
                )
                verified.append(vc)
                if claim.id:
                    verified_by_id[claim.id] = vc
                continue

            # 3. Inference claims
            if claim.kind == ClaimKind.INFERENCE:
                deps_supported = True
                dep_texts = []
                for dep_id in claim.depends_on:
                    dep_claim = verified_by_id.get(dep_id)
                    if not dep_claim or dep_claim.verdict != Verdict.SUPPORTED:
                        deps_supported = False
                        break
                    dep_texts.append(dep_claim.text)

                if not deps_supported:
                    vc = VerifiedClaim(
                        **claim.model_dump(),
                        verdict=Verdict.UNSUPPORTED,
                        score=0.0,
                        rationale="Dependencies are not fully supported.",
                    )
                    verified.append(vc)
                    if claim.id:
                        verified_by_id[claim.id] = vc
                    continue

                # Format evidence as the supported claims it depends on
                evidence_text = "\n".join(f"- {t}" for t in dep_texts)
            else:
                # Format standard evidence
                evidence_blocks = []
                for ev in claim.evidence:
                    chunk_text = chunks.get(ev.chunk_id, "")
                    context = _extract_context(ev.quote, chunk_text)
                    evidence_blocks.append(f"Quote: {ev.quote}\nContext: {context}")
                evidence_text = "\n\n".join(evidence_blocks)

            # 4. Semantic Verification
            prompt = self.template.replace("{{claim}}", claim.text).replace("{{evidence}}", evidence_text)
            raw_response = self.llm_call(prompt, "verifier")

            try:
                data = json.loads(self._extract_json(raw_response))
            except json.JSONDecodeError:
                logger.error("Failed to parse verifier response")
                continue

            for item in data:
                try:
                    verdict = Verdict(item["verdict"])
                    text = item["text"]
                    score = float(item["score"])
                    rationale = item["rationale"]

                    # 5. Optional NLI cross-encoder
                    if self.use_nli_cross_encoder and self.nli_call and verdict == Verdict.SUPPORTED:
                        nli_score = self.nli_call(evidence_text, text)
                        if nli_score < 0.5:
                            verdict = Verdict.UNSUPPORTED
                            rationale = "NLI cross-encoder contradicted the LLM verdict."
                            score = nli_score

                    vc = VerifiedClaim(
                        id=claim.id if text == claim.text else None,  # Keep ID only if not split
                        text=text,
                        kind=claim.kind,
                        evidence=claim.evidence,
                        depends_on=claim.depends_on,
                        verdict=verdict,
                        score=score,
                        rationale=rationale,
                    )
                    verified.append(vc)
                    if vc.id:
                        verified_by_id[vc.id] = vc
                except (KeyError, ValueError) as e:
                    logger.warning("Invalid verifier item: %s", e)

        return verified
