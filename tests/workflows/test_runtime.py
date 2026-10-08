
from contracts.schemas import WorkflowRequest
from lextrace.orchestrator.factory import build_system


def test_runtime_spine_happy_path():
    system = build_system("config")
    graph = system.compile()
    
    req = WorkflowRequest(workflow="chat", query="Tuesday incident")
    res = graph.invoke({"request": req})
    
    assert res is not None
    assert "output" in res
    assert res["output"].workflow == "chat"
    
def test_runtime_spine_abstention():
    system = build_system("config")
    graph = system.compile()
    
    req = WorkflowRequest(workflow="chat", query="UnmatchableQueryThatForcesAbstention xyz123")
    res = graph.invoke({"request": req})
    
    output = res["output"]
    assert output.abstained == True
    assert "not contain enough information" in output.rendered_markdown
