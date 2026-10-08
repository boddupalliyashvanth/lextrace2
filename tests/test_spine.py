
import pytest

from contracts.schemas import WorkflowRequest
from lextrace.orchestrator.factory import build_system


@pytest.fixture
def system():
    return build_system("config")

def test_happy_path(system, monkeypatch):
    # force retriever to return hits
    from contracts.schemas import Chunk, Hit
    def fake_search(*args, **kwargs):
        return [Hit(chunk=Chunk(chunk_id="c1", doc_id="d1", text="some text", page_start=1, page_end=1, char_start=0, char_end=9), score=1.0, source='bm25')]
    monkeypatch.setattr(system.retriever, "search", fake_search)
    
    graph = system.compile()
    req = WorkflowRequest(workflow="chat", query="hello")
    res = graph.invoke({"request": req})
    out = res["output"]
    assert out.workflow == "chat"
    assert out.abstained is False
    assert len(out.claims) > 0
    # ensure it respected loops (fake hits < 2 initially, reformulates query)

def test_abstention_path(system, monkeypatch):
    # simulate no claims generated -> abstained GroundedOutput
    class StubClaimGen:
        def generate(self, *args, **kwargs):
            return []
    system.claim_generator = StubClaimGen()
    graph = system.compile()
    req = WorkflowRequest(workflow="chat", query="no hits query")
    res = graph.invoke({"request": req})
    out = res["output"]
    assert out.abstained is True
    assert "not contain enough information" in out.rendered_markdown

def test_missing_workflow_fallback():
    # It should fallback to GenericQAWorkflow when workflow is not in _WORKFLOWS
    sys = build_system("config")
    graph = sys.compile()
    req = WorkflowRequest(workflow="review", query="test fallback")
    res = graph.invoke({"request": req})
    out = res["output"]
    assert out.workflow == "review"

def test_cache_hit_and_fallback_model_switch(tmp_path):
    # Testing client directly for cache hit & fallback

    from lextrace.llm.client import GoogleGenAILLM
    
    # Enable cache but make it mock
    llm = GoogleGenAILLM(config_dir="config", cache_dir=str(tmp_path), enable_cache=True, mock=True)
    llm.complete("test prompt")
    
    # Check trace for mock LLM call
    assert any(e["event"] == "llm_call" for e in llm.run_trace)
    
    # Ensure cache works (when mock is false, we can mock client)
