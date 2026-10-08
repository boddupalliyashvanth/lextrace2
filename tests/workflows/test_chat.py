import pytest

from contracts.schemas import WorkflowRequest
from lextrace.orchestrator.factory import build_system


@pytest.fixture
def system():
    return build_system("config")

def test_chat_workflow_memory_and_rewrite(system, monkeypatch):
    from contracts.schemas import Chunk, Hit
    def fake_search(query, *args, **kwargs):
        if "standalone" in query.lower():
            return [Hit(chunk=Chunk(chunk_id="c2", doc_id="d1", text="standalone text", page_start=1, page_end=1, char_start=0, char_end=9), score=1.0, source='bm25')]
        return [Hit(chunk=Chunk(chunk_id="c1", doc_id="d1", text="initial text", page_start=1, page_end=1, char_start=0, char_end=9), score=1.0, source='bm25')]
    monkeypatch.setattr(system.retriever, "search", fake_search)
    
    # fake llm rewriting
    class FakeRewriteLLM:
        def complete(self, prompt, **kwargs):
            return "STANDALONE QUERY"
    system.llm = FakeRewriteLLM()
    
    graph = system.compile()
    
    # Turn 1
    req1 = WorkflowRequest(workflow="chat", query="first question", session_id="s1")
    res1 = graph.invoke({"request": req1})
    assert not res1["output"].abstained
    
    # Turn 2
    req2 = WorkflowRequest(workflow="chat", query="follow up", session_id="s1")
    res2 = graph.invoke({"request": req2})
    res2["request"] # Wait, GraphState is returned but invoke returns the final state dict
    assert "STANDALONE QUERY" in res2["query_history"]
    
    # Turn 3
    req3 = WorkflowRequest(workflow="chat", query="show me the source", session_id="s1")
    res3 = graph.invoke({"request": req3})
    assert "## Sources" in res3["output"].rendered_markdown
    assert "c1" in res3["output"].rendered_markdown or "c2" in res3["output"].rendered_markdown
