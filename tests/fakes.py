import json
import os

from pydantic import BaseModel

from contracts.interfaces import (
    ClaimGenerator,
)
from contracts.schemas import (
    Chunk,
    CitationRender,
    Claim,
    ClaimKind,
    Contradiction,
    DocType,
    Evidence,
    GroundedOutput,
    Hit,
    MissingItem,
    VerificationReport,
    Violation,
    WorkflowName,
)


class FakeRetriever:
    def __init__(self, corpus_dir: str):
        self.corpus_dir = corpus_dir
        self.chunks = []
        for fn in os.listdir(corpus_dir):
            if fn.endswith('.json'):
                with open(os.path.join(corpus_dir, fn), 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                    for c in doc.get('chunks', []):
                        self.chunks.append(Chunk(**c, doc_id=doc['doc_id']))

    def search(self, query: str, k: int = 8, doc_types: list[DocType] | None = None, doc_ids: list[str] | None = None) -> list[Hit]:
        q_words = set(query.lower().split())
        hits = []
        for chunk in self.chunks:
            c_words = set(chunk.text.lower().split())
            overlap = len(q_words.intersection(c_words))
            if overlap > 0:
                hits.append(Hit(chunk=chunk, score=float(overlap), source='bm25'))
        hits.sort(key=lambda x: x.score, reverse=True)
        return hits[:k]

class FakeLLM:
    def complete(self, prompt: str, *, system: str | None = None, model_role: str = 'generator', json_schema: type[BaseModel] | None = None, temperature: float = 0.0) -> str | BaseModel:
        if json_schema:
            return json_schema() # May fail if missing required fields, stub for now
        return "Fake LLM output"

class FakeVerifier:
    def verify(self, claims: list[Claim], chunks: dict[str, Chunk]) -> VerificationReport:
        violations = []
        passed = True
        for claim in claims:
            supported = True
            for ev in claim.evidence:
                if ev.chunk_id not in chunks:
                    violations.append(Violation(code='CHUNK_NOT_FOUND', claim_id=claim.claim_id, detail=f"{ev.chunk_id} missing"))
                    supported = False
                    passed = False
                elif ev.quote not in chunks[ev.chunk_id].text:
                    violations.append(Violation(code='QUOTE_NOT_VERBATIM', claim_id=claim.claim_id, detail="Quote mismatch"))
                    supported = False
                    passed = False
            if supported:
                claim.status = 'supported'
            else:
                claim.status = 'unsupported'
        return VerificationReport(claims=claims, violations=violations, passed=passed)

class FakeClaimGenerator(ClaimGenerator):
    def generate(self, task: str, hits: list[Hit], *, kinds: list[ClaimKind]) -> list[Claim]:
        claims = []
        if hits:
            # Simulate a repair loop:
            if "Fix these issues:" in task:
                # Provide valid quote
                claims.append(Claim(claim_id="c1", text="Generated fake claim based on hits (repaired).", kind=kinds[0], evidence=[
                    Evidence(chunk_id=hits[0].chunk.chunk_id, quote=hits[0].chunk.text[:10])
                ]))
            else:
                # Provide invalid quote to trigger violation
                claims.append(Claim(claim_id="c1", text="Generated fake claim based on hits (initial).", kind=kinds[0], evidence=[
                    Evidence(chunk_id=hits[0].chunk.chunk_id, quote="THIS QUOTE DOES NOT EXIST IN THE CHUNK")
                ]))
        return claims

class FakeRenderer:
    def render(self, workflow: WorkflowName, claims: list[Claim], chunks: dict[str, Chunk], *, missing: list[MissingItem], contradictions: list[Contradiction]) -> GroundedOutput:
        return GroundedOutput(
            workflow=workflow,
            rendered_markdown="## Fake Rendered Output",
            claims=claims,
            citations=[CitationRender(marker="[1]", text="Fake Citation", chunk_id=c.chunk_id, quote="fake") for c in chunks.values()],
            missing_info=missing,
            contradictions=contradictions,
            confidence=0.9,
            abstained=False,
            trace=[]
        )
