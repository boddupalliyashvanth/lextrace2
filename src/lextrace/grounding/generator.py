import uuid

from contracts.interfaces import ClaimGenerator
from contracts.schemas import Claim, ClaimKind, Evidence, Hit


class DefaultClaimGenerator(ClaimGenerator):
    def __init__(self, llm):
        self.llm = llm

    def generate(self, task: str, hits: list[Hit], *, kinds: list[ClaimKind]) -> list[Claim]:
        # In a real implementation, this would use self.llm to prompt for claims
        # For this prototype, we will return some structured claims directly
        claims = []
        for i, hit in enumerate(hits):
            # Just create a claim of the first requested kind
            kind = kinds[0] if kinds else 'fact'
            claims.append(Claim(
                claim_id=str(uuid.uuid4()),
                text=f"Generated {kind} claim based on: {hit.chunk.text[:50]}...",
                kind=kind,
                evidence=[Evidence(chunk_id=hit.chunk.chunk_id, quote=hit.chunk.text[:20])],
                depends_on=[]
            ))
        return claims
