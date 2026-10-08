import os
import stat

files = {}

files["src/lextrace/llm/client.py"] = """\
import hashlib
import json
import os
import time
from typing import Optional, Type, Any
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
import yaml
from google import genai
from google.genai import types
from google.genai.errors import APIError

from contracts.interfaces import LLM

class GoogleGenAILLM:
    def __init__(self, config_dir: str, cache_dir: str = ".cache/llm", enable_cache: bool = True, mock: bool = False, run_trace: list = None):
        models_file = os.path.join(config_dir, "models.yaml")
        if os.path.exists(models_file):
            with open(models_file) as f:
                self.models = yaml.safe_load(f)
        else:
            self.models = {}
        self.cache_dir = cache_dir
        self.enable_cache = enable_cache
        self.mock = mock
        self.run_trace = run_trace if run_trace is not None else []
        if not self.mock:
            self.client = genai.Client() # Uses GEMINI_API_KEY from environment
        else:
            self.client = None
        if self.enable_cache:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_key(self, model: str, system: str, prompt: str, schema: Any) -> str:
        s = f"{model}|{system}|{prompt}|{schema}"
        return hashlib.sha256(s.encode()).hexdigest()

    def complete(self, prompt: str, *, system: Optional[str] = None, model_role: str = 'generator', json_schema: Optional[Type[BaseModel]] = None, temperature: float = 0.0) -> str | BaseModel:
        if self.mock:
            return self._mock_complete(prompt, system, model_role, json_schema)
            
        role_cfg = self.models.get(model_role, self.models.get("generator", {}))
        primary_model = role_cfg.get("primary", "gemini-1.5-pro")
        fallback_model = role_cfg.get("fallback", "gemini-1.5-flash")

        try:
            return self._complete_with_retries(primary_model, prompt, system, json_schema, temperature)
        except Exception as e:
            self.run_trace.append({"event": "fallback_triggered", "reason": str(e), "fallback": fallback_model})
            return self._complete_with_retries(fallback_model, prompt, system, json_schema, temperature)

    def _complete_with_retries(self, model: str, prompt: str, system: Optional[str], json_schema: Optional[Type[BaseModel]], temperature: float) -> str | BaseModel:
        schema_str = json_schema.model_json_schema() if json_schema else None
        cache_key = self._get_cache_key(model, system or "", prompt, schema_str)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if self.enable_cache and os.path.exists(cache_file):
            with open(cache_file) as f:
                data = json.load(f)
                if json_schema:
                    return json_schema.model_validate(data["response"])
                return data["response"]

        @retry(
            retry=retry_if_exception_type(APIError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10)
        )
        def call_api(current_prompt: str, is_retry: bool = False):
            start_t = time.time()
            config = types.GenerateContentConfig(
                temperature=temperature,
            )
            if system:
                config.system_instruction = system
            if json_schema:
                config.response_mime_type = "application/json"
                config.response_schema = json_schema

            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=current_prompt,
                    config=config,
                )
            except APIError as e:
                if e.code in [429] or (e.code >= 500):
                    raise
                else:
                    raise RuntimeError(f"Non-retriable API error: {e}") from e

            latency = time.time() - start_t
            usage = response.usage_metadata
            tokens = usage.total_token_count if usage else 0

            self.run_trace.append({
                "event": "llm_call",
                "model": model,
                "latency": latency,
                "tokens": tokens,
                "is_repair_retry": is_retry
            })

            text = response.text
            if json_schema:
                try:
                    return json_schema.model_validate_json(text), text
                except ValidationError as ve:
                    return None, text
            return text, text

        res, raw_text = call_api(prompt, False)
        if json_schema and res is None:
            repair_prompt = f"The previous response failed schema validation. Please fix it. Original prompt: {prompt}\\n\\nInvalid response:\\n{raw_text}"
            res, raw_text = call_api(repair_prompt, True)
            if res is None:
                raise ValueError("Failed to produce valid JSON after repair.")

        if self.enable_cache:
            with open(cache_file, "w") as f:
                json.dump({"response": res.model_dump() if json_schema else res}, f)

        return res

    def _mock_complete(self, prompt: str, system: Optional[str], model_role: str, json_schema: Optional[Type[BaseModel]]) -> str | BaseModel:
        self.run_trace.append({
            "event": "llm_call",
            "model": "mock",
            "latency": 0.01,
            "tokens": 10,
            "is_repair_retry": False
        })
        if json_schema:
            try:
                return json_schema()
            except Exception:
                return json_schema.construct()
        return "Mock Response"
"""

files["src/lextrace/orchestrator/workflows.py"] = """\
from typing import Dict, Type
from contracts.interfaces import Workflow
from contracts.schemas import WorkflowName, GroundedOutput, WorkflowRequest, Claim

_WORKFLOWS: Dict[str, Type[Workflow]] = {}

def register_workflow(name: str):
    def decorator(cls: Type[Workflow]):
        _WORKFLOWS[name] = cls
        return cls
    return decorator

def get_workflow(name: str) -> Type[Workflow]:
    return _WORKFLOWS.get(name, GenericQAWorkflow)

class GenericQAWorkflow:
    workflow: WorkflowName = "chat"
    
    def __init__(self, renderer):
        self.renderer = renderer
        
    def run(self, req: WorkflowRequest) -> GroundedOutput:
        return self.renderer.render(
            workflow=self.workflow,
            claims=[],
            chunks={},
            missing=[],
            contradictions=[]
        )
"""

files["src/lextrace/orchestrator/graph.py"] = """\
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

from contracts.schemas import (
    Hit, Chunk, Claim, VerificationReport, GroundedOutput, 
    WorkflowRequest, ClaimKind, ClaimStatus
)
from contracts.interfaces import (
    Retriever, LLM, ClaimGenerator, Verifier, CitationRegistry, Renderer
)
from lextrace.orchestrator.workflows import get_workflow

class GraphState(BaseModel):
    request: WorkflowRequest
    query_history: List[str] = Field(default_factory=list)
    retrieval_loops: int = 0
    repair_loops: int = 0
    hits: List[Hit] = Field(default_factory=list)
    chunks: Dict[str, Chunk] = Field(default_factory=dict)
    claims: List[Claim] = Field(default_factory=list)
    verification: Optional[VerificationReport] = None
    output: Optional[GroundedOutput] = None
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    repair_reasons: List[str] = Field(default_factory=list)

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

    def route(self, state: GraphState):
        state.trace.append({"event": "route", "workflow": state.request.workflow})
        return state

    def plan(self, state: GraphState):
        state.trace.append({"event": "plan"})
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
            task += f"\\nFix these issues: {state.repair_reasons}"
            
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
        
        supported = [c for c in state.verification.claims if c.status == 'supported']
        if not supported and state.claims:
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
        workflow_inst = workflow_cls(self.renderer)
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
"""

files["src/lextrace/orchestrator/factory.py"] = """\
import yaml
import os
from lextrace.orchestrator.graph import LexTraceGraph
from tests.fakes import FakeRetriever, FakeClaimGenerator, FakeVerifier, FakeRenderer

def build_system(config_dir: str):
    with open(os.path.join(config_dir, "features.yaml")) as f:
        features = yaml.safe_load(f)

    if features.get("retriever") == "fake":
        retriever = FakeRetriever("tests/fixtures/mini_corpus")
    else:
        retriever = FakeRetriever("tests/fixtures/mini_corpus")

    if features.get("claimgen") == "fake":
        claimgen = FakeClaimGenerator()
    else:
        claimgen = FakeClaimGenerator()

    if features.get("verifier") == "fake":
        verifier = FakeVerifier()
    else:
        verifier = FakeVerifier()
        
    renderer = FakeRenderer()

    return LexTraceGraph(
        retriever=retriever,
        claim_generator=claimgen,
        verifier=verifier,
        renderer=renderer
    )
"""

files["src/lextrace/cli/__main__.py"] = """\
from lextrace.cli.app import app

if __name__ == "__main__":
    app()
"""

files["src/lextrace/cli/app.py"] = """\
import typer
import json
import os
import uuid
from lextrace.orchestrator.factory import build_system
from contracts.schemas import WorkflowRequest

app = typer.Typer()

@app.command()
def demo(fake: bool = False):
    if not fake:
        print("Only --fake is supported.")
        return
        
    system = build_system("config")
    graph = system.compile()
    
    req = WorkflowRequest(workflow="chat", query="Tuesday incident sky hat")
    
    result = graph.invoke({"request": req})
    out = result.get("output")
    
    run_id = str(uuid.uuid4())
    os.makedirs("runs", exist_ok=True)
    with open(f"runs/{run_id}.json", "w") as f:
        json.dump(out.trace if out else [], f, indent=2)
        
    if out:
        print(out.model_dump_json(indent=2))

@app.command()
def ingest(dir: str):
    pass

@app.command()
def ask(query: str):
    pass

@app.command()
def review():
    pass

@app.command()
def draft():
    pass

@app.command()
def research():
    pass

@app.command()
def chat():
    pass

@app.command()
def judge(docs: str, queries: str, out: str):
    pass
"""

files["src/lextrace/api/app.py"] = """\
from fastapi import FastAPI
from lextrace.api.routes import router

app = FastAPI(title="LexTrace API")
app.include_router(router)
"""

files["src/lextrace/api/routes.py"] = """\
from fastapi import APIRouter
from pydantic import BaseModel
from contracts.schemas import WorkflowRequest, GroundedOutput
from lextrace.orchestrator.factory import build_system

router = APIRouter()
system = build_system("config")
graph = system.compile()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/run", response_model=GroundedOutput)
def run_workflow(req: WorkflowRequest):
    result = graph.invoke({"request": req})
    return result.get("output")

@router.post("/ingest")
def ingest():
    return {"status": "ingested"}

@router.get("/runs/{id}")
def get_run(id: str):
    return {"run_id": id, "status": "mock"}
"""

files["tests/workflows/test_runtime.py"] = """\
from contracts.schemas import WorkflowRequest
from lextrace.orchestrator.factory import build_system
import os

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
"""


# Create directories and write files
directories = [
    "src/lextrace/llm",
    "src/lextrace/orchestrator",
    "src/lextrace/api",
    "src/lextrace/cli",
    "tests/workflows",
    "runs"
]

for d in directories:
    os.makedirs(d, exist_ok=True)
    if d.startswith("src/lextrace") or d.startswith("tests"):
        init_file = os.path.join(d, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write("")

for path, content in files.items():
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Runtime spine generated.")
