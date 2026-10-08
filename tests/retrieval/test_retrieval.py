import tempfile
from pathlib import Path

from contracts.schemas import Chunk
from src.lextrace.retrieval.bm25 import LegalBM25
from src.lextrace.retrieval.expansion import QueryExpander
from src.lextrace.retrieval.fusion import reciprocal_rank_fusion
from src.lextrace.retrieval.router import HybridRetriever


def test_bm25_tokenization():
    bm25 = LegalBM25()
    tokens = bm25.tokenize("Section 482 of the Cr.P.C. is used here.")
    assert "section" in tokens
    assert "482" in tokens
    assert "crpc" in tokens
    assert "cr" not in tokens
    print("test_bm25_tokenization passed")

def test_bm25_search():
    bm25 = LegalBM25()
    c1 = Chunk(chunk_id="c1", doc_id="d1", meta={"doc_type": "statute"}, text="Section 482 of Cr.P.C.", page_start=1, page_end=1, char_start=0, char_end=10)
    c2 = Chunk(chunk_id="c2", doc_id="d2", meta={"doc_type": "statute"}, text="Nothing to do with CrPC", page_start=1, page_end=1, char_start=0, char_end=10)
    c3 = Chunk(chunk_id="c3", doc_id="d3", meta={"doc_type": "statute"}, text="Dummy padding to make idf work", page_start=1, page_end=1, char_start=0, char_end=10)
    bm25.fit([c1, c2, c3])
    
    hits = bm25.search("section 482", top_k=5)
    assert len(hits) == 1
    assert hits[0][0].chunk_id == "c1"
    print("test_bm25_search passed")

def test_query_expander():
    with tempfile.TemporaryDirectory() as tmpdir:
        map_file = Path(tmpdir) / "statute_map.yaml"
        map_file.write_text("""
mappings:
  - canonical: "Bharatiya Nyaya Sanhita"
    aliases:
      - "BNS"
    provenance: "Test"
  - canonical: "Bharatiya Nagarik Suraksha Sanhita"
    aliases:
      - "BNSS"
    # No provenance, should be ignored
""")
        
        expander = QueryExpander(str(map_file))
        q = expander.expand("Under BNS")
        assert "Bharatiya Nyaya Sanhita" in q
        
        q2 = expander.expand("Under BNSS")
        assert "Bharatiya Nagarik Suraksha Sanhita" not in q2
        print("test_query_expander passed")

def test_rrf():
    c1 = Chunk(chunk_id="c1", doc_id="d1", meta={"doc_type": "statute"}, text="A", page_start=1, page_end=1, char_start=0, char_end=1)
    c2 = Chunk(chunk_id="c2", doc_id="d1", meta={"doc_type": "statute"}, text="B", page_start=1, page_end=1, char_start=0, char_end=1)
    
    list1 = [(c1, 10.0), (c2, 5.0)]
    list2 = [(c2, 20.0), (c1, 5.0)]
    
    list3 = [(c1, 5.0)] # breaks tie
    
    fused = reciprocal_rank_fusion([list1, list2, list3], k=60)
    assert fused[0][0].chunk_id == "c1"
    print("test_rrf passed")
    
def test_hybrid_router():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "retrieval.yaml"
        config_file.write_text("""
retrieval:
  top_k: 2
  stages:
    expansion: false
    dense: false
    bm25: true
    fusion: false
    rerank: false
""")
        
        router = HybridRetriever(index_dir=str(Path(tmpdir) / "index"), config_path=str(config_file))
        c1 = Chunk(chunk_id="c1", doc_id="d1", meta={"doc_type": "statute"}, text="Section 482 of Cr.P.C.", page_start=1, page_end=1, char_start=0, char_end=10)
        c2 = Chunk(chunk_id="c2", doc_id="d2", meta={"doc_type": "judgment"}, text="BNS Section 482", page_start=1, page_end=1, char_start=0, char_end=10)
        c3 = Chunk(chunk_id="c3", doc_id="d3", meta={"doc_type": "case_file"}, text="482 case file", page_start=1, page_end=1, char_start=0, char_end=10)
        
        d1 = Chunk(chunk_id="d1", doc_id="d1", meta={"doc_type": "statute"}, text="Dummy text for statute", page_start=1, page_end=1, char_start=0, char_end=10)
        d2 = Chunk(chunk_id="d2", doc_id="d1", meta={"doc_type": "judgment"}, text="Dummy text for judgment", page_start=1, page_end=1, char_start=0, char_end=10)
        d3 = Chunk(chunk_id="d3", doc_id="d1", meta={"doc_type": "case_file"}, text="Dummy text for case_file", page_start=1, page_end=1, char_start=0, char_end=10)
        
        bm25_statute = LegalBM25()
        bm25_statute.fit([c1, d1, d2])
        bm25_judgment = LegalBM25()
        bm25_judgment.fit([c2, d2, d3])
        bm25_case_file = LegalBM25()
        bm25_case_file.fit([c3, d3, d1])
        
        router.bm25_engines['statute'] = bm25_statute
        router.bm25_engines['judgment'] = bm25_judgment
        router.bm25_engines['case_file'] = bm25_case_file
        router.chunk_store = {c.chunk_id: c for c in [c1, c2, c3]}
        
        hits = router.search("482", k=2, doc_types=['statute', 'judgment', 'case_file'])
        
        assert len(hits) == 2
        types = [h.chunk.meta.get('doc_type') for h in hits]
        assert "statute" in types
        assert "judgment" in types
        assert "case_file" not in types
        print("test_hybrid_router passed")

if __name__ == "__main__":
    test_bm25_tokenization()
    test_bm25_search()
    test_query_expander()
    test_rrf()
    test_hybrid_router()
