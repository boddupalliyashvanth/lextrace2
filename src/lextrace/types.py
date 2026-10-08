"""Shared types for the LexTrace pipeline."""

from __future__ import annotations

from pydantic import BaseModel


class Hit(BaseModel):
    """A retrieved chunk from the corpus."""

    chunk_id: str
    doc: str
    page: int | str | None = None
    text: str
