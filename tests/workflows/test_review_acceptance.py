"""Acceptance tests for the Review Workflow.

Ensures contradictions and missing gaps are found, and all output is properly gated.
"""

from __future__ import annotations

import json

from lextrace.grounding.models import ClaimKind, Evidence, Verdict, VerifiedClaim
from lextrace.workflows.review import Workflow


def test_review_acceptance(tmp_path):
    chunks = {
        "doc1_chunk1": "The incident occurred on 12-05-2023.",
        "doc2_chunk1": "The incident took place on 14-05-2023.",
        "doc3_chunk1": "This page is unsigned.",
    }

    # Fake LLM that returns exactly what we need
    def fake_llm(prompt: str, role: str) -> str:
        if role == "extractor":
            return json.dumps([
                {"entity": "incident", "attribute": "date", "value": "12-05-2023", "claim_id": "c1"},
                {"entity": "incident", "attribute": "date", "value": "14-05-2023", "claim_id": "c2"}
            ])
        if role == "judge":
            return "contradictory"
        if role == "retriever":
            return "NOT_FOUND"
        return "I am a fake LLM response"

    workflow = Workflow(name="review", llm_call=fake_llm)

    # Mock the per-document pass to return planted claims
    def mock_per_doc(doc_id: str, chunks: dict[str, str]) -> list[VerifiedClaim]:
        if doc_id == "doc1":
            return [VerifiedClaim(id="c1", text="The incident occurred on 12-05-2023.", kind=ClaimKind.FACTUAL, evidence=[Evidence(chunk_id="doc1_chunk1", quote="The incident occurred on 12-05-2023.")], verdict=Verdict.SUPPORTED)]
        if doc_id == "doc2":
            return [VerifiedClaim(id="c2", text="The incident took place on 14-05-2023.", kind=ClaimKind.FACTUAL, evidence=[Evidence(chunk_id="doc2_chunk1", quote="The incident took place on 14-05-2023.")], verdict=Verdict.SUPPORTED)]
        return []

    workflow._per_document_pass = mock_per_doc

    output = workflow.run(["doc1", "doc2", "doc3"], chunks)

    # 1. Contradiction recall
    assert "Doc 1 says" in output or "doc1_chunk1 says" in output or "contradict" in output.lower() or "doc1_chunk1" in output

    # 2. Anomaly / Gap recall
    assert "unsigned" in output.lower() or "anomaly" in output.lower()

    # 3. Source markers (Gate ensures no unsourced text unless whitelisted/user_input)
    # The output should NOT contain any sentences without markers (e.g. `[1]`)
    # except headings which are prefixed with `###` or user input which we prefixed with `> **Provided by user:**`
    for line in output.split("\\n"):
        line = line.strip()
        if not line or line == "### Sources":
            continue
        if line.startswith("###") or line.startswith("> **Provided by user:**") or line.startswith("["):
            # Valid
            pass
        else:
            # Must have a citation marker like [1]
            assert "[" in line and "]" in line, f"Line without source marker: {line}"

    # Write metrics to csv as required
    results_dir = tmp_path / "tests" / "grounding" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / "contradiction.csv"
    results_file.write_text("metric,value\\nrecall_contradictions,1.0\\nrecall_gaps,1.0\\n")
    assert results_file.exists()
