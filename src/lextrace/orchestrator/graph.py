from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from contracts.interfaces import ClaimGenerator, Renderer, Retriever, Verifier
from contracts.schemas import (
    Chunk,
    Claim,
    GroundedOutput,
    Hit,
    VerificationReport,
    WorkflowRequest,
)
from lextrace.orchestrator.workflows import get_workflow


class GraphState(BaseModel):
    request: WorkflowRequest
    query_history: list[str] = Field(default_factory=list)
    retrieval_loops: int = 0
    repair_loops: int = 0
    hits: list[Hit] = Field(default_factory=list)
    chunks: dict[str, Chunk] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    verification: VerificationReport | None = None
    output: GroundedOutput | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    repair_reasons: list[str] = Field(default_factory=list)

class LexTraceGraph:
    def __init__(
        self,
        retriever: Retriever,
        claim_generator: ClaimGenerator,
        verifier: Verifier,
        renderer: Renderer
    ):
        self.retriever = retriever
        self.claim_generator = claim_generator
        self.verifier = verifier
        self.renderer = renderer
        self.llm = getattr(claim_generator, "llm", getattr(verifier, "llm", None))

    def route(self, state: GraphState):
        state.trace.append({"event": "route", "workflow": state.request.workflow})
        return state

    def plan(self, state: GraphState):
        state.trace.append({"event": "plan"})
        workflow_cls = get_workflow(state.request.workflow)
        try:
            workflow_inst = workflow_cls(self.renderer, self.llm)
        except TypeError:
            workflow_inst = workflow_cls(self.renderer)
        if hasattr(workflow_inst, "plan"):
            state = workflow_inst.plan(state)
        else:
            state.query_history.append(state.request.query)
        return state

    def retrieve(self, state: GraphState):
        current_query = state.query_history[-1]
        state.trace.append({"event": "retrieve", "query": current_query})
        hits = self.retriever.search(current_query)
        state.hits.extend(hits)
        for h in hits:
            state.chunks[h.chunk.chunk_id] = h.chunk
        state.retrieval_loops += 1
        return state

    def sufficiency_check(self, state: GraphState):
        state.trace.append({"event": "sufficiency_check"})
        return state

    def generate_claims(self, state: GraphState):
        state.trace.append({"event": "generate_claims"})
        task = state.request.query
        if state.repair_reasons:
            task += f"\nFix these issues: {state.repair_reasons}"
            
        claims = self.claim_generator.generate(task=task, hits=state.hits, kinds=["fact"])
        state.claims = claims
        return state

    def verify(self, state: GraphState):
        state.trace.append({"event": "verify"})
        verification = self.verifier.verify(state.claims, state.chunks)
        state.verification = verification
        return state

    def gate(self, state: GraphState):
        state.trace.append({"event": "gate"})
        return state

    def repair(self, state: GraphState):
        state.trace.append({"event": "repair"})
        state.repair_loops += 1
        state.repair_reasons = [v.detail for v in state.verification.violations]
        for c in state.claims:
            if c.status == 'unsupported':
                state.trace.append({"event": "dropped_unverified", "claim_id": c.claim_id})
        return state

    def render(self, state: GraphState):
        state.trace.append({"event": "render"})
        
        supported = [c for c in state.verification.claims if c.status == 'supported'] if state.verification else []
        # If we generated claims but none supported, or if we generated no claims at all (due to no hits)
        if not supported:
            state.output = GroundedOutput(
                workflow=state.request.workflow,
                rendered_markdown="The provided documents do not contain enough information.",
                claims=[],
                citations=[],
                confidence=0.0,
                abstained=True,
                trace=state.trace
            )
            return state

        workflow_cls = get_workflow(state.request.workflow)
        try:
            workflow_inst = workflow_cls(self.renderer, self.llm)
        except TypeError:
            workflow_inst = workflow_cls(self.renderer)
        if hasattr(workflow_inst, "render_output"):
            output = workflow_inst.render_output(state)
        else:
            output = self.renderer.render(
                workflow=state.request.workflow,
                claims=supported,
                chunks=state.chunks,
                missing=[],
                contradictions=[]
            )
        output.trace = state.trace
        state.output = output
        return state

    def compile(self):
        workflow = StateGraph(GraphState)
        
        workflow.add_node("route", self.route)
        workflow.add_node("plan", self.plan)
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("sufficiency_check", self.sufficiency_check)
        workflow.add_node("generate_claims", self.generate_claims)
        workflow.add_node("verify", self.verify)
        workflow.add_node("repair", self.repair)
        workflow.add_node("gate", self.gate)
        workflow.add_node("render", self.render)

        workflow.add_edge(START, "route")
        workflow.add_edge("route", "plan")
        workflow.add_edge("plan", "retrieve")
        workflow.add_edge("retrieve", "sufficiency_check")
        
        def sufficiency_edges(state: GraphState):
            if len(state.hits) < 2 and state.retrieval_loops < 2:
                state.query_history.append(state.request.query + " more info")
                return "retrieve"
            return "generate_claims"
            
        workflow.add_conditional_edges("sufficiency_check", sufficiency_edges)
        
        workflow.add_edge("generate_claims", "verify")
        workflow.add_edge("verify", "gate")
        
        def gate_edges(state: GraphState):
            if not state.verification.passed:
                if state.repair_loops < 2:
                    return "repair"
                else:
                    return "render"
            return "render"

        workflow.add_conditional_edges("gate", gate_edges)
        workflow.add_edge("repair", "generate_claims")
        workflow.add_edge("render", END)
        
        return workflow.compile()
