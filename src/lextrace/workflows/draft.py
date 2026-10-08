from contracts.interfaces import Renderer, Retriever, SlotFiller, Verifier
from contracts.schemas import GroundedOutput, WorkflowRequest


class DraftWorkflow:
    workflow = 'draft'

    def __init__(self, retriever: Retriever, slotfiller: SlotFiller, verifier: Verifier, renderer: Renderer):
        self.retriever = retriever
        self.slotfiller = slotfiller
        self.verifier = verifier
        self.renderer = renderer

    def run(self, req: WorkflowRequest) -> GroundedOutput:
        # Step 1: Fill slots for the required template
        # The template info is in req.params['slots']
        slots = req.params.get('slots', [])
        
        filled_claims, missing = self.slotfiller.fill(slots, self.retriever, req.case_doc_ids)
        claims = list(filled_claims.values())
        
        # Step 2: Verify claims
        # Need to fetch the chunks that support these claims to pass to verifier
        {ev.chunk_id for c in claims for ev in c.evidence}
        # In a real system, the retriever or document store would provide chunk fetching by ID
        # Here we mock passing chunks retrieved during slot filling (handled internally by slot filler ideally)
        chunk_dict = {} # Assumed populated in a real implementation
        
        verification = self.verifier.verify(claims, chunk_dict)
        verified_claims = [c for c in verification.claims if c.status == 'supported']
        
        # Step 3: Render
        return self.renderer.render(
            self.workflow,
            verified_claims,
            chunk_dict,
            missing=missing,
            contradictions=[]
        )