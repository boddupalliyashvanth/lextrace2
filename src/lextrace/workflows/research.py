from contracts.interfaces import ClaimGenerator, Renderer, Retriever, Verifier
from contracts.schemas import GroundedOutput, MissingItem, WorkflowRequest


class ResearchWorkflow:
    workflow = 'research'
    
    def __init__(self, retriever: Retriever, claimgen: ClaimGenerator, verifier: Verifier, renderer: Renderer):
        self.retriever = retriever
        self.claimgen = claimgen
        self.verifier = verifier
        self.renderer = renderer

    def run(self, req: WorkflowRequest) -> GroundedOutput:
        # Step 1: Retrieve case facts
        case_hits = []
        if req.case_doc_ids:
            case_hits = self.retriever.search(req.query, k=5, doc_types=['case_file'], doc_ids=req.case_doc_ids)
        fact_claims = self.claimgen.generate("Extract legal issues and facts", case_hits, kinds=['fact'])
        
        # Step 2 & 3: Per-issue sub-queries for statutes and judgments
        # To simplify, we treat the query as the single main issue for now.
        # Use case facts (fact_claims) to formulate the search for precedents
        fact_summary = " ".join([c.text for c in fact_claims])
        precedent_query = f"{req.query} {fact_summary}".strip()
        
        statute_hits = self.retriever.search(req.query, k=5, doc_types=['statute'])
        judgment_hits = self.retriever.search(precedent_query, k=5, doc_types=['judgment'])
        
        law_claims = self.claimgen.generate("Extract law quotes for provision/precedent", statute_hits + judgment_hits, kinds=['law'])
        
        # Step 4: Application step (Inference claims)
        # We pass fact and law claims to the generator to create inferences
        all_hits = case_hits + statute_hits + judgment_hits
        inference_claims = self.claimgen.generate("Connect laws to facts", all_hits, kinds=['inference'])
        
        # Collect all claims
        all_claims = fact_claims + law_claims + inference_claims
        
        # Verify
        chunk_dict = {h.chunk.chunk_id: h.chunk for h in all_hits}
        verification_report = self.verifier.verify(all_claims, chunk_dict)
        
        verified_claims = [c for c in verification_report.claims if c.status == 'supported']
        
        # Rule: Inference claim without supported dependencies must be dropped
        supported_claim_ids = {c.claim_id for c in verified_claims}
        final_claims = []
        for c in verified_claims:
            if c.kind == 'inference':
                if not all(dep in supported_claim_ids for dep in c.depends_on):
                    continue # Drop unsupported inferences
            final_claims.append(c)

        # Missing check (Rule: No judgment in provided corpus addresses issue)
        missing = []
        if not judgment_hits:
            missing.append(MissingItem(
                slot="Relevant precedents",
                why_needed=f"No judgment in the provided corpus addresses {req.query}",
                queries_tried=[precedent_query],
                status="not_found"
            ))

        # Render
        return self.renderer.render(
            self.workflow,
            final_claims,
            chunk_dict,
            missing=missing,
            contradictions=[]
        )