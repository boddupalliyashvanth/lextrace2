from contracts.interfaces import Verifier
from contracts.schemas import Chunk, Claim, VerificationReport, Violation


class ExactQuoteVerifier(Verifier):
    def verify(self, claims: list[Claim], chunks: dict[str, Chunk]) -> VerificationReport:
        violations = []
        passed = True
        
        for claim in claims:
            supported = True
            for ev in claim.evidence:
                if ev.chunk_id not in chunks:
                    violations.append(Violation(
                        code='CHUNK_NOT_FOUND', 
                        claim_id=claim.claim_id, 
                        detail=f"Chunk {ev.chunk_id} missing from retrieved context."
                    ))
                    supported = False
                    passed = False
                elif ev.quote not in chunks[ev.chunk_id].text:
                    violations.append(Violation(
                        code='QUOTE_NOT_VERBATIM', 
                        claim_id=claim.claim_id, 
                        detail=f"Quote '{ev.quote}' not found verbatim in chunk."
                    ))
                    supported = False
                    passed = False
                    
            claim.status = 'supported' if supported else 'unsupported'
            
        return VerificationReport(claims=claims, violations=violations, passed=passed)
