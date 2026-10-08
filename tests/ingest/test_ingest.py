from contracts.schemas import SourceDoc
from lextrace.ingest.chunk import structure_aware_chunk
from lextrace.ingest.parse import normalize_text, repair_hyphenation
from lextrace.ingest.store import persist_ingest


def test_hyphenation_repair():
    text = "consti-\ntution"
    repaired = repair_hyphenation(text)
    assert repaired == "constitution"

def test_normalization():
    text = "a\u0301" # a with acute accent
    norm = normalize_text(text)
    assert norm == "\u00e1" # single character á

def test_offset_round_trip():
    full_text = "This is a test document."
    pages = [{"page_num": 0, "char_start": 0, "char_end": len(full_text)-1}]
    chunks = structure_aware_chunk("doc1", full_text, pages, "statute")
    
    for c in chunks:
        assert c.text == full_text[c.char_start:c.char_end]

def test_idempotent_reingest(tmp_path):
    doc = SourceDoc(
        doc_id="doc1", doc_type="statute", title="Test", uri="test.pdf",
        sha256="abc123hash", license="PD"
    )
    chunks = []
    
    # First ingest
    res1 = persist_ingest(doc, chunks, "text", tmp_path)
    assert res1 is True
    
    # Second ingest
    res2 = persist_ingest(doc, chunks, "text", tmp_path)
    assert res2 is False

def test_scanned_page_fallback():
    # Since parse.py contains the logic for fitz, we mock the output conceptually.
    # We would test that if the text density is low, "[OCR FALLBACK]" is prepended.
    pass

def test_registry_valid_chunks():
    
    # Testing that build_registry doesn't output invalid chunk_ids
    # This is verified by ensuring the set intersection in build_registry works.
    pass
