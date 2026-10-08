import uuid

from pydantic import BaseModel, Field

from contracts.interfaces import LLM
from contracts.schemas import (
    Chunk,
    Claim,
    ClaimKind,
    Evidence,
    Hit,
    VerificationReport,
    Violation,
)


class GeneratedClaim(BaseModel):
    text: str = Field(..., description="The main factual claim or argument.")
    chunk_id: str = Field(..., description="The chunk ID supporting this claim.")
    quote: str = Field(..., description="Exact substring from the chunk supporting the claim.")

class ClaimGenerationOutput(BaseModel):
    claims: list[GeneratedClaim]

class VerifierCheck(BaseModel):
    passed: bool = Field(..., description="True if the quote is found exactly and strongly supports the claim.")
    reasons: list[str] = Field(..., description="Explanation of why it passed or failed.")
    score: float = Field(..., description="Confidence score from 0.0 to 1.0.")
    corrected_quote: str | None = Field(None, description="If quote was slightly off but can be fixed.")

class RealClaimGenerator:
    def __init__(self, llm: LLM):
        self.llm = llm

    def generate(self, task: str, hits: list[Hit], *, kinds: list[ClaimKind]) -> list[Claim]:
        if not hits:
            return []
            
        context = ""
        for h in hits:
            context += f"\n--- Chunk {h.chunk.chunk_id} ---\n{h.chunk.text}\n"

        system = "You are a legal assistant. Generate specific claims backed by exact quotes from the provided chunks. Return JSON matching ClaimGenerationOutput."
        prompt = f"Task: {task}\n\nAllowed kinds: {kinds}\n\nContext:{context}"
        
        try:
            output: ClaimGenerationOutput = self.llm.complete(
                prompt=prompt,
                system=system,
                model_role='generator',
                json_schema=ClaimGenerationOutput
            )
            
            claims = []
            for i, c in enumerate(output.claims):
                claims.append(Claim(
                    claim_id=f"c_{uuid.uuid4().hex[:8]}",
                    text=c.text,
                    kind=kinds[0] if kinds else ClaimKind.FACT,
                    evidence=[Evidence(chunk_id=c.chunk_id, quote=c.quote)]
                ))
            return claims
        except Exception as e:
            print(f"Error generating claims: {e}")
            return []

class RealVerifier:
    def __init__(self, llm: LLM):
        self.llm = llm

    def verify(self, claims: list[Claim], chunks: dict[str, Chunk]) -> VerificationReport:
        violations = []
        all_passed = True
        
        system = "You are a strict legal verification engine. Verify if the provided quote strictly supports the claim, and if the quote exists verbatim in the chunk text."
        
        for claim in claims:
            if not claim.evidence:
                claim.status = 'unsupported'
                all_passed = False
                continue
                
            evidence = claim.evidence[0]
            chunk = chunks.get(evidence.chunk_id)
            if not chunk:
                claim.status = 'unsupported'
                all_passed = False
                violations.append(Violation(claim_id=claim.claim_id, rule="missing_chunk", description=f"Chunk {evidence.chunk_id} not found."))
                continue
                
            # Verbatim check
            if evidence.quote not in chunk.text:
                # Ask LLM if it can be corrected or if it's completely wrong
                prompt = f"Claim: {claim.text}\nQuote: {evidence.quote}\nChunk text: {chunk.text}\n\nThe quote is NOT a perfect verbatim match. Can it be corrected to an exact substring of the chunk? Return VerifierCheck."
                try:
                    check: VerifierCheck = self.llm.complete(prompt, system=system, model_role='verifier', json_schema=VerifierCheck)
                    if check.passed and check.corrected_quote and check.corrected_quote in chunk.text:
                        evidence.quote = check.corrected_quote
                        claim.status = 'supported'
                        claim.verifier_score = check.score
                        claim.reasons = check.reasons
                    else:
                        claim.status = 'unsupported'
                        all_passed = False
                        violations.append(Violation(claim_id=claim.claim_id, rule="verbatim_quote", description="Quote is not verbatim or fails support."))
                        claim.reasons = check.reasons
                except Exception as e:
                    claim.status = 'unsupported'
                    all_passed = False
                    violations.append(Violation(claim_id=claim.claim_id, rule="verifier_error", description=str(e)))
            else:
                # Ask LLM if the verbatim quote actually supports the claim
                prompt = f"Claim: {claim.text}\nQuote: {evidence.quote}\nChunk text: {chunk.text}\n\nDoes this quote strongly support the claim? Return VerifierCheck."
                try:
                    check: VerifierCheck = self.llm.complete(prompt, system=system, model_role='verifier', json_schema=VerifierCheck)
                    if check.passed:
                        claim.status = 'supported'
                        claim.verifier_score = check.score
                        claim.reasons = check.reasons
                    else:
                        claim.status = 'unsupported'
                        all_passed = False
                        violations.append(Violation(claim_id=claim.claim_id, rule="weak_support", description="Quote verbatim but doesn't support claim."))
                        claim.reasons = check.reasons
                except Exception as e:
                    claim.status = 'unsupported'
                    all_passed = False
                    violations.append(Violation(claim_id=claim.claim_id, rule="verifier_error", description=str(e)))
                    
        return VerificationReport(claims=claims, violations=violations, passed=all_passed)
