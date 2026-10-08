from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal['case_file', 'statute', 'judgment']
WorkflowName = Literal['review', 'draft', 'research', 'chat', 'judge']
ClaimKind = Literal['fact', 'law', 'inference', 'template_text']
ClaimStatus = Literal['pending', 'supported', 'partial', 'unsupported', 'contradicted', 'abstained']
ViolationCode = Literal['CHUNK_NOT_FOUND', 'QUOTE_NOT_VERBATIM', 'NUMBER_MISMATCH', 'CITATION_UNRESOLVED', 'SECTION_NOT_FOUND', 'UNCITED_FACT', 'INJECTION_SUSPECTED']
USER_INPUT_CHUNK_ID = 'USER_INPUT'   # evidence.chunk_id for facts typed in by the user (rendered as 'Provided by user')

class SourceDoc(BaseModel):
    doc_id: str                      # slug + sha256[:8], stable across re-ingestion
    doc_type: DocType
    title: str
    canonical_citation: str | None = None   # ONLY from document metadata or registry, never model-generated
    court: str | None = None
    date: str | None = None       # ISO date if known
    uri: str
    sha256: str
    license: str
    synthetic: bool = False
    meta: dict = Field(default_factory=dict)   # statute_name, bench, in_force_from, doc_kind (FIR, charge_sheet ...)

class Chunk(BaseModel):
    chunk_id: str                    # f'{doc_id}::p{page_start}::c{idx}'
    doc_id: str
    text: str
    page_start: int
    page_end: int
    char_start: int                  # offsets into the doc's normalised full text
    char_end: int
    section_path: str | None = None   # 'Section 482' | 'Para 12' | 'FIR > Facts'
    meta: dict = Field(default_factory=dict)

class Hit(BaseModel):
    chunk: Chunk
    score: float
    source: Literal['bm25', 'dense', 'fused', 'rerank']

class Evidence(BaseModel):
    chunk_id: str
    quote: str                       # must be a verbatim (normalised) substring of the chunk text

class Claim(BaseModel):
    claim_id: str
    text: str
    kind: ClaimKind
    evidence: list[Evidence] = Field(default_factory=list)
    status: ClaimStatus = 'pending'
    verifier_score: float | None = None
    reasons: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)   # claim_ids, used by inference claims

class Violation(BaseModel):
    code: ViolationCode
    claim_id: str | None = None
    detail: str

class VerificationReport(BaseModel):
    claims: list[Claim]
    violations: list[Violation]
    passed: bool                     # False if ANY hard violation survives repair

class RegistryEntry(BaseModel):
    canonical: str                   # e.g. 'Section 482 BNSS'
    aliases: list[str]
    kind: Literal['statute_section', 'case']
    doc_id: str
    chunk_ids: list[str]

class SlotSpec(BaseModel):
    name: str                        # e.g. 'fir_number'
    description: str
    required: bool = True
    value_type: Literal['text', 'date', 'number', 'list'] = 'text'
    source_hints: list[str] = Field(default_factory=list)

class MissingItem(BaseModel):
    slot: str
    why_needed: str
    queries_tried: list[str]
    status: Literal['not_found', 'conflicting', 'low_confidence']

class Contradiction(BaseModel):
    claim_a: Claim
    claim_b: Claim
    attribute: str
    explanation: str

class CitationRender(BaseModel):
    marker: str                      # '[1]'
    text: str                        # rendered by code from SourceDoc metadata plus pinpoint
    chunk_id: str
    quote: str

class GroundedOutput(BaseModel):
    workflow: WorkflowName
    rendered_markdown: str
    claims: list[Claim]
    citations: list[CitationRender]
    missing_info: list[MissingItem] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    confidence: float
    abstained: bool = False
    trace: list[dict] = Field(default_factory=list)

class WorkflowRequest(BaseModel):
    workflow: WorkflowName
    query: str
    case_doc_ids: list[str] = Field(default_factory=list)
    session_id: str | None = None
    params: dict = Field(default_factory=dict)   # e.g. {'doc_template': 'bail_regular', 'user_facts': {...}}
