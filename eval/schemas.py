import json
from enum import Enum
from pydantic import BaseModel, Field

class SplitType(str, Enum):
    DEV = "dev"
    HELDOUT = "heldout"

class GoldSource(BaseModel):
    doc_id: str
    locator: str
    quote: str | None = None

class QuerySchema(BaseModel):
    qid: str
    workflow: str
    query: str
    case_doc_ids: list[str]
    gold_sources: list[GoldSource] = Field(default_factory=list)
    gold_points: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)
    split: SplitType
    author: str
