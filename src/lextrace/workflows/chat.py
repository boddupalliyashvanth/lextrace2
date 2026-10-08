
from pydantic import BaseModel, Field

from contracts.interfaces import LLM, Renderer
from contracts.schemas import Claim, GroundedOutput, WorkflowName, WorkflowRequest
from lextrace.orchestrator.graph import GraphState
from lextrace.orchestrator.workflows import register_workflow


class ChatSession(BaseModel):
    session_id: str
    history: list[dict[str, str]] = Field(default_factory=list)
    case_doc_ids: list[str] = Field(default_factory=list)
    verified_claims: list[Claim] = Field(default_factory=list)

_MEMORY: dict[str, ChatSession] = {}

@register_workflow("chat")
class ChatWorkflow:
    workflow: WorkflowName = "chat"
    
    def __init__(self, renderer: Renderer, llm: LLM | None = None):
        self.renderer = renderer
        self.llm = llm

    def run(self, req: WorkflowRequest) -> GroundedOutput:
        pass # The orchestrator handles graph invocation

    def plan(self, state: GraphState) -> GraphState:
        req = state.request
        session_id = req.session_id or "default"
        if session_id not in _MEMORY:
            _MEMORY[session_id] = ChatSession(session_id=session_id)
        
        session = _MEMORY[session_id]
        if req.case_doc_ids:
            session.case_doc_ids = list(set(session.case_doc_ids + req.case_doc_ids))
            
        if not session.history:
            rewritten_query = req.query
        else:
            if "show me the source" in req.query.lower():
                rewritten_query = req.query
            else:
                prompt = f"Given history: {session.history[-5:]}\nRewrite this query into a standalone query resolving coreferences: '{req.query}'. DO NOT add facts."
                if self.llm:
                    res = self.llm.complete(prompt, model_role="generator")
                    if hasattr(res, "text"):
                        rewritten_query = res.text
                    else:
                        rewritten_query = str(res)
                else:
                    rewritten_query = req.query
                    
        state.query_history.append(rewritten_query)
        session.history.append({"role": "user", "content": req.query})
        
        return state

    def render_output(self, state: GraphState) -> GroundedOutput:
        req = state.request
        session_id = req.session_id or "default"
        session = _MEMORY.get(session_id)
        
        supported = [c for c in state.verification.claims if c.status == 'supported'] if state.verification else []
        
        if session:
            session.verified_claims.extend(supported)
            
        query = req.query.lower()
        if "show me the source" in query and session and session.verified_claims:
            md = "## Sources\n"
            for c in session.verified_claims:
                for ev in c.evidence:
                    md += f"- Document: {ev.chunk_id}, Quote: {ev.quote}\n"
            return GroundedOutput(
                workflow=self.workflow,
                rendered_markdown=md,
                claims=session.verified_claims,
                citations=[],
                confidence=1.0,
                abstained=False,
                trace=state.trace
            )
            
        if not supported:
            msg = f"The provided documents do not contain enough information to answer: '{req.query}'. Searched for: '{state.query_history[-1]}'"
            if session:
                session.history.append({"role": "assistant", "content": msg})
            return GroundedOutput(
                workflow=self.workflow,
                rendered_markdown=msg,
                claims=[],
                citations=[],
                confidence=0.0,
                abstained=True,
                trace=state.trace
            )
            
        output = self.renderer.render(
            workflow=self.workflow,
            claims=supported,
            chunks=state.chunks,
            missing=[],
            contradictions=[]
        )
        if session:
            session.history.append({"role": "assistant", "content": output.rendered_markdown})
            
        return output