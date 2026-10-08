from contracts.interfaces import ClaimGenerator, Renderer, Retriever, Verifier
from contracts.schemas import GroundedOutput, WorkflowRequest


class ReviewWorkflow:
    workflow = 'review'

    def __init__(self, retriever: Retriever, claimgen: ClaimGenerator, verifier: Verifier, renderer: Renderer):
        self.retriever = retriever
        self.claimgen = claimgen
        self.verifier = verifier
        self.renderer = renderer

    def run(self, req: WorkflowRequest) -> GroundedOutput:
        # Step 1: Search relevant documents
        hits = self.retriever.search(req.query, k=5, doc_ids=req.case_doc_ids)
        
        # Step 2: Generate claims
        claims = self.claimgen.generate(f"Review query: {req.query}", hits, kinds=['fact', 'law'])
        
        # Step 3: Verify claims
        chunk_dict = {h.chunk.chunk_id: h.chunk for h in hits}
        verification = self.verifier.verify(claims, chunk_dict)
        
        verified_claims = [c for c in verification.claims if c.status == 'supported']
        
        # Step 4: Render
        return self.renderer.render(
            self.workflow,
            verified_claims,
            chunk_dict,
            missing=[],
            contradictions=[]
        )