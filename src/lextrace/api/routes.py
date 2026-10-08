from fastapi import APIRouter

from contracts.schemas import GroundedOutput, WorkflowRequest
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
