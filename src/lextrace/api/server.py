import json
import os
import uuid

from fastapi import FastAPI, HTTPException

from contracts.schemas import GroundedOutput, WorkflowRequest
from lextrace.orchestrator.factory import build_system

app = FastAPI(title="LexTrace API")
system = build_system("config")
graph = system.compile()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ingest")
def ingest(payload: dict):
    # Stub for now
    return {"status": "ingested"}

@app.post("/run", response_model=GroundedOutput)
def run_workflow(request: WorkflowRequest):
    try:
        result = graph.invoke({"request": request})
        out = result.get("output")
        if not out:
            raise HTTPException(status_code=500, detail="No output generated")
            
        run_id = str(uuid.uuid4())
        os.makedirs("runs", exist_ok=True)
        with open(f"runs/{run_id}.json", "w") as f:
            json.dump(out.trace, f, indent=2)
            
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run_file = f"runs/{run_id}.json"
    if not os.path.exists(run_file):
        raise HTTPException(status_code=404, detail="Run not found")
    with open(run_file, "r") as f:
        return json.load(f)
