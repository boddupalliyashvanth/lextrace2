"""Acceptance tests for the full grounding pipeline.

Ensures the pipeline orchestrates Claim Generation -> Verification -> Gate -> Render,
and correctly filters out hallucinations, fabricated quotes, unsupported claims, etc.
"""

from __future__ import annotations

import json

from lextrace.grounding.citation_registry import CitationRegistry
from lextrace.grounding.gate import run_gate
from lextrace.grounding.models import Claim, ClaimKind, Evidence, Verdict
from lextrace.grounding.render import Renderer
from lextrace.grounding.verifier import Verifier


def test_pipeline_acceptance(tmp_path):
    """Test that the full pipeline correctly filters adversarial claims."""

    chunks = {
        "chunk1": "The Supreme Court in K.S. Puttaswamy v. Union of India held that privacy is a fundamental right under Article 21. Damages were set at Rs 100,000.",
    }

    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text(json.dumps({
        "id": "case1",
        "type": "case",
        "canonical_name": "K.S. Puttaswamy v. Union of India",
        "aliases": ["Puttaswamy", "Privacy case"],
        "document": "doc1",
        "metadata": {}
    }) + "\n" + json.dumps({
        "id": "art21",
        "type": "section",
        "canonical_name": "Article 21 of the Constitution of India",
        "aliases": ["Article 21", "section 21"],
        "document": "doc1",
        "statute": "const",
        "metadata": {}
    }) + "\n")

    registry = CitationRegistry(registry_path=registry_path)

    # ---------------------------------------------------------
    # 1. Generator Phase (Simulated by FakeLLM)
    # ---------------------------------------------------------

    # The generator produces 5 claims:
    # (a) good claim
    # (b) fabricated quote
    # (c) true but unsupported claim
    # (d) mismatched number
    # (e) fake case citation

    generated_claims = [
        Claim(
            id="c1", text="Privacy is a fundamental right under Article 21.", kind=ClaimKind.LEGAL,
            evidence=[Evidence(chunk_id="chunk1", quote="privacy is a fundamental right under Article 21.")]
        ),
        Claim(
            id="c2", text="The court awarded costs.", kind=ClaimKind.FACTUAL,
            evidence=[Evidence(chunk_id="chunk1", quote="awarded costs.")] # Fabricated quote
        ),
        Claim(
            id="c3", text="The moon is made of cheese.", kind=ClaimKind.FACTUAL,
            evidence=[Evidence(chunk_id="chunk1", quote="Damages were set at Rs 100,000.")] # True/False, but unsupported by quote
        ),
        Claim(
            id="c4", text="Damages were set at Rs 500,000.", kind=ClaimKind.NUMERICAL,
            evidence=[Evidence(chunk_id="chunk1", quote="Damages were set at Rs 100,000.")] # Mismatched number
        ),
        Claim(
            id="c5", text="As held in Fake v. State, privacy is important.", kind=ClaimKind.LEGAL,
            evidence=[Evidence(chunk_id="chunk1", quote="privacy is a fundamental right")] # Fake citation
        )
    ]

    # ---------------------------------------------------------
    # 2. Verifier Phase
    # ---------------------------------------------------------

    # Fake LLM for the verifier
    def fake_verifier_llm(prompt: str, role: str) -> str:
        # We look at the prompt to decide the verdict
        # If it's c3 (moon), it's unsupported
        if "The moon is made of cheese" in prompt:
            return json.dumps([{"text": "The moon is made of cheese.", "verdict": "unsupported", "score": 0.0, "rationale": "Irrelevant."}])

        # All other claims are 'supported' according to the LLM (but deterministic checks will fail them before the LLM, or the gate will catch them)
        # Note: verifier.py runs deterministic checks FIRST. So c2 and c4 will fail deterministically.
        # c1 and c5 will pass deterministic (c5 is a fake citation, but the quote exists).
        # We'll make the LLM support c1 and c5.
        if "Fake v. State" in prompt:
            return json.dumps([{"text": "As held in Fake v. State, privacy is important.", "verdict": "supported", "score": 1.0, "rationale": "LLM hallucinated support."}])

        return json.dumps([{"text": "Privacy is a fundamental right under Article 21.", "verdict": "supported", "score": 1.0, "rationale": "Directly supported."}])

    verifier = Verifier(llm_call=fake_verifier_llm)
    verified_claims = verifier.verify(generated_claims, chunks)

    # Check verifier output
    assert len(verified_claims) == 5

    # c1 should be supported
    assert verified_claims[0].id == "c1"
    assert verified_claims[0].verdict == Verdict.SUPPORTED

    # c2 should fail deterministic check (quote not verbatim)
    assert verified_claims[1].id == "c2"
    assert verified_claims[1].verdict == Verdict.UNSUPPORTED
    assert "QUOTE_NOT_VERBATIM" in verified_claims[1].rationale

    # c3 should fail LLM check
    assert verified_claims[2].id == "c3"
    assert verified_claims[2].verdict == Verdict.UNSUPPORTED

    # c4 should fail deterministic check (number mismatch)
    assert verified_claims[3].id == "c4"
    assert verified_claims[3].verdict == Verdict.UNSUPPORTED
    assert "NUMBER_MISMATCH" in verified_claims[3].rationale

    # c5 fails deterministic check because 'Fake' and 'State' are not in the chunk text
    assert verified_claims[4].id == "c5"
    assert verified_claims[4].verdict == Verdict.UNSUPPORTED

    # ---------------------------------------------------------
    # 3. Renderer Phase
    # ---------------------------------------------------------
    renderer = Renderer(registry=registry)
    rendered_text = renderer.render(verified_claims)

    # ---------------------------------------------------------
    # 4. Gatekeeper Phase
    # ---------------------------------------------------------
    _, violations_c1 = registry.scan(rendered_text)
    print("Rendered text:", rendered_text)
    print("Violations:", violations_c1)

    final_output = run_gate(rendered_text, chunks, registry)

    # The final output should ONLY contain c1, because c5 contains a fake citation which the gate catches via registry.scan
    assert "Privacy is a fundamental right under Article 21." in final_output
    assert "Fake v. State" not in final_output

    # Make sure we didn't abstain entirely
    assert "I could not find sufficient evidence" not in final_output
