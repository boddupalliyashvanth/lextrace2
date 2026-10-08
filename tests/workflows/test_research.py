from contracts.schemas import (
    Chunk,
    Claim,
    Evidence,
    GroundedOutput,
    Hit,
    VerificationReport,
    WorkflowRequest,
)
from src.lextrace.workflows.research import ResearchWorkflow


class MockRetriever:
    def __init__(self, case_hits=None, statute_hits=None, judgment_hits=None):
        self.case_hits = case_hits or []
        self.statute_hits = statute_hits or []
        self.judgment_hits = judgment_hits or []
        self.queries = []
    
    def search(self, query: str, k: int = 8, doc_types=None, doc_ids=None):
        self.queries.append((query, doc_types, doc_ids))
        if doc_types == ['case_file']: return self.case_hits
        if doc_types == ['statute']: return self.statute_hits
        if doc_types == ['judgment']: return self.judgment_hits
        return []

class MockClaimGen:
    def generate(self, task, hits, kinds):
        claims = []
        for i, k in enumerate(kinds):
            claims.append(Claim(
                claim_id=f"mock_{k}_{i}",
                text=f"Mock claim for {k}",
                kind=k,
                evidence=[Evidence(chunk_id=h.chunk.chunk_id, quote="abc") for h in hits],
                depends_on=[]
            ))
        return claims

class MockVerifier:
    def verify(self, claims, chunks):
        for c in claims:
            # We simulate that all claims are supported by default
            c.status = getattr(c, '_mock_status', 'supported')
        return VerificationReport(claims=claims, violations=[], passed=True)

class MockRenderer:
    def render(self, workflow, claims, chunks, missing, contradictions):
        return GroundedOutput(
            workflow=workflow,
            rendered_markdown="## Rendered",
            claims=claims,
            citations=[],
            missing_info=missing,
            contradictions=contradictions,
            confidence=0.9,
            abstained=False,
            trace=[]
        )

def test_research_workflow_golden():
    # Golden path
    req = WorkflowRequest(
        workflow='research',
        query="Can we quash the FIR?",
        case_doc_ids=["case_1"]
    )
    
    c1 = Chunk(chunk_id="case_1::p1::c1", doc_id="case_1", text="Facts here", page_start=1, page_end=1, char_start=0, char_end=10)
    c2 = Chunk(chunk_id="stat_1::p1::c1", doc_id="stat_1", text="Statute here", page_start=1, page_end=1, char_start=0, char_end=10)
    c3 = Chunk(chunk_id="judg_1::p1::c1", doc_id="judg_1", text="Judgment here", page_start=1, page_end=1, char_start=0, char_end=10)
    
    retriever = MockRetriever(
        case_hits=[Hit(chunk=c1, score=1.0, source='bm25')],
        statute_hits=[Hit(chunk=c2, score=1.0, source='bm25')],
        judgment_hits=[Hit(chunk=c3, score=1.0, source='bm25')]
    )
    wf = ResearchWorkflow(retriever, MockClaimGen(), MockVerifier(), MockRenderer())
    
    res = wf.run(req)
    assert len(res.missing_info) == 0
    # Fact, law, and inference claims should be present
    assert len(res.claims) >= 3

def test_research_workflow_red_team_famous_case_absent():
    # Red-team test: Query invites citing a famous but absent case
    req = WorkflowRequest(
        workflow='research',
        query="Apply the standard from State of Haryana v. Bhajan Lal",
    )
    
    # judgment_hits is empty
    retriever = MockRetriever()
    wf = ResearchWorkflow(retriever, MockClaimGen(), MockVerifier(), MockRenderer())
    
    res = wf.run(req)
    assert len(res.missing_info) == 1
    assert "No judgment in the provided corpus addresses" in res.missing_info[0].why_needed
    
def test_research_workflow_drops_unsupported_inferences():
    # An inference claim without supported dependencies must be dropped
    req = WorkflowRequest(workflow='research', query="Issue")
    
    class CustomClaimGen(MockClaimGen):
        def generate(self, task, hits, kinds):
            if 'inference' in kinds:
                c = super().generate(task, hits, kinds)[0]
                c.depends_on = ['mock_law_0', 'missing_fact']
                return [c]
            return super().generate(task, hits, kinds)
            
    wf = ResearchWorkflow(MockRetriever(), CustomClaimGen(), MockVerifier(), MockRenderer())
    res = wf.run(req)
    
    # Inference claim depends on 'missing_fact' which is not supported/doesn't exist
    for c in res.claims:
        assert c.kind != 'inference'

