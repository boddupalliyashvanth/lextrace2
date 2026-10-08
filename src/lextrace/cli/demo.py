import os
from typing import TypedDict

import typer
from langgraph.graph import END, START, StateGraph

from lextrace.contracts.schemas import (
    Chunk,
    Claim,
    GroundedOutput,
    Hit,
    VerificationReport,
)
from tests.fakes import FakeClaimGenerator, FakeRenderer, FakeRetriever, FakeVerifier

app = typer.Typer()

class State(TypedDict):
    query: str
    hits: list[Hit]
    claims: list[Claim]
    chunks: dict[str, Chunk]
    verification: VerificationReport | None
    output: GroundedOutput | None

def retrieve(state: State):
    retriever = FakeRetriever(os.path.join("tests", "fixtures", "mini_corpus"))
    hits = retriever.search(state["query"])
    return {"hits": hits, "chunks": {h.chunk.chunk_id: h.chunk for h in hits}}

def generate(state: State):
    generator = FakeClaimGenerator()
    claims = generator.generate(task=state["query"], hits=state["hits"], kinds=["fact"])
    return {"claims": claims}

def verify(state: State):
    verifier = FakeVerifier()
    verification = verifier.verify(state["claims"], state["chunks"])
    return {"verification": verification}

def render(state: State):
    renderer = FakeRenderer()
    output = renderer.render(workflow="chat", claims=state["verification"].claims, chunks=state["chunks"], missing=[], contradictions=[])
    return {"output": output}

@app.command()
def demo(fake: bool = False):
    if not fake:
        print("Only --fake is supported currently.")
        return
    
    workflow = StateGraph(State)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)
    workflow.add_node("verify", verify)
    workflow.add_node("render", render)
    
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "verify")
    workflow.add_edge("verify", "render")
    workflow.add_edge("render", END)
    
    _app = workflow.compile()
    result = _app.invoke({"query": "Tuesday incident sky hat"})
    if result.get("output"):
        print(result["output"].model_dump_json(indent=2))

if __name__ == "__main__":
    app()
