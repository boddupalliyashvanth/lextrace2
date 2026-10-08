"""TASK 2 — Contradiction Detection.

Identifies material inconsistencies across documents.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from lextrace.analysis.models import Contradiction, FactTuple
from lextrace.grounding.models import VerifiedClaim

logger = logging.getLogger(__name__)


class ContradictionDetector:
    def __init__(
        self,
        llm_call: Callable[[str, str], str] | None = None,
        nli_call: Callable[[str, str], float] | None = None,
    ):
        self.llm_call = llm_call
        self.nli_call = nli_call

    def extract_fact_tuples(self, claims: list[VerifiedClaim]) -> list[FactTuple]:
        """Extract FactTuples from verified claims.

        In a real implementation, this would use an LLM or specific regex to parse the text.
        For this prototype, we'll assume a basic mapping or invoke the LLM to structure it.
        """
        tuples = []
        if not self.llm_call:
            return tuples

        prompt = "Extract facts from the following claims as JSON array of {entity, attribute, value, claim_id}:\\n"
        claims_map = {}
        for c in claims:
            if c.id:
                claims_map[c.id] = c
                prompt += f"[{c.id}] {c.text}\\n"

        # Fake extraction for simplicity, or we can use llm_call
        try:
            resp = self.llm_call(prompt, "extractor")
            # Extract JSON from response
            text = resp.strip()
            if text.startswith("```"):
                lines = text.split("\\n")
                start = 1
                end = len(lines)
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].strip().startswith("```"):
                        end = i
                        break
                text = "\\n".join(lines[start:end]).strip()

            data = json.loads(text)
            for item in data:
                cid = item.get("claim_id")
                if cid in claims_map:
                    tuples.append(FactTuple(
                        entity=item["entity"],
                        attribute=item["attribute"],
                        value=str(item["value"]),
                        claim=claims_map[cid]
                    ))
        except Exception as e:
            logger.warning("Fact extraction failed: %s", e)

        return tuples

    def _normalise_entity(self, entity: str) -> str:
        return entity.lower().strip()

    def block_candidates(self, tuples: list[FactTuple]) -> list[tuple[FactTuple, FactTuple]]:
        """Block candidate pairs by normalised entity and attribute."""
        blocks: dict[tuple[str, str], list[FactTuple]] = {}

        for t in tuples:
            key = (self._normalise_entity(t.entity), t.attribute.lower().strip())
            if key not in blocks:
                blocks[key] = []
            blocks[key].append(t)

        candidates = []
        for _key, group in blocks.items():
            if len(group) > 1:
                # Create all pairs
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        candidates.append((group[i], group[j]))
        return candidates

    def detect(self, claims: list[VerifiedClaim]) -> list[Contradiction]:
        """Detect contradictions among a list of verified claims."""
        tuples = self.extract_fact_tuples(claims)
        candidates = self.block_candidates(tuples)

        contradictions = []

        for t1, t2 in candidates:
            # Check if they are actually contradictory
            is_contradiction = False

            if self.nli_call:
                # Check entailment both ways or contradiction
                # A high contradiction score means they contradict
                score = self.nli_call(t1.claim.text, t2.claim.text)
                if score < 0.2: # Assuming low score = contradiction in this dummy setup
                    is_contradiction = True
            elif self.llm_call:
                # LLM Judge
                prompt = f"Are these two claims consistent, contradictory, or unrelated?\\nClaim A: {t1.claim.text}\\nClaim B: {t2.claim.text}\\nAnswer:"
                resp = self.llm_call(prompt, "judge").lower()
                if "contradictory" in resp:
                    is_contradiction = True

            if is_contradiction:
                # Fetch docs - naively assuming the first evidence chunk holds the doc name
                doc_a = t1.claim.evidence[0].chunk_id if t1.claim.evidence else "Doc A"
                doc_b = t2.claim.evidence[0].chunk_id if t2.claim.evidence else "Doc B"

                explanation = f"{doc_a} says {t1.value}; {doc_b} says {t2.value}."
                contradictions.append(Contradiction(
                    claim_a=t1.claim,
                    claim_b=t2.claim,
                    explanation=explanation
                ))

        return contradictions
