
from contracts.interfaces import Workflow
from contracts.schemas import GroundedOutput, WorkflowName, WorkflowRequest

_WORKFLOWS: dict[str, type[Workflow]] = {}

def register_workflow(name: str):
    def decorator(cls: type[Workflow]):
        _WORKFLOWS[name] = cls
        return cls
    return decorator

def get_workflow(name: str) -> type[Workflow]:
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
