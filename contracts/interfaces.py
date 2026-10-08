from typing import Protocol

from pydantic import BaseModel

from .schemas import (
    Chunk,
    Claim,
    ClaimKind,
    Contradiction,
    DocType,
    GroundedOutput,
    Hit,
    MissingItem,
    RegistryEntry,
    SlotSpec,
    VerificationReport,
    Violation,
    WorkflowName,
    WorkflowRequest,
)


class Retriever(Protocol):
    def search(self, query: str, k: int = 8, doc_types: list[DocType] | None = None, doc_ids: list[str] | None = None) -> list[Hit]:
        ...

class LLM(Protocol):
    def complete(self, prompt: str, *, system: str | None = None, model_role: str = 'generator', json_schema: type[BaseModel] | None = None, temperature: float = 0.0) -> str | BaseModel:
        ...

class ClaimGenerator(Protocol):
    def generate(self, task: str, hits: list[Hit], *, kinds: list[ClaimKind]) -> list[Claim]:
        ...

class Verifier(Protocol):
    def verify(self, claims: list[Claim], chunks: dict[str, Chunk]) -> VerificationReport:
        ...

class CitationRegistry(Protocol):
    def resolve(self, citation_text: str) -> RegistryEntry | None:
        ...
    def scan(self, text: str) -> list[Violation]:
        ...

class Renderer(Protocol):
    def render(self, workflow: WorkflowName, claims: list[Claim], chunks: dict[str, Chunk], *, missing: list[MissingItem], contradictions: list[Contradiction]) -> GroundedOutput:
        ...

class SlotFiller(Protocol):
    def fill(self, slots: list[SlotSpec], retriever: Retriever, case_doc_ids: list[str]) -> tuple[dict[str, Claim], list[MissingItem]]:
        ...

class ContradictionDetector(Protocol):
    def detect(self, claims: list[Claim]) -> list[Contradiction]:
        ...

class Workflow(Protocol):
    workflow: WorkflowName
    def run(self, req: WorkflowRequest) -> GroundedOutput:
        ...
