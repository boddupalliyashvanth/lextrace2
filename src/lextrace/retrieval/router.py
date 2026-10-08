from pathlib import Path

import yaml

from contracts.schemas import Chunk, DocType, Hit

from .bm25 import LegalBM25
from .dense import DenseRetriever
from .expansion import QueryExpander
from .fusion import reciprocal_rank_fusion
from .rerank import Reranker


class HybridRetriever:
    def __init__(self, index_dir: str = ".index", config_path: str = "config/retrieval.yaml"):
        self.index_dir = Path(index_dir)
        self.config = self._load_config(config_path)
        
        self.chunk_store: dict[str, Chunk] = {} # chunk_id -> Chunk
        
        self.expander = QueryExpander()
        self.bm25_engines: dict[str, LegalBM25] = {} # doc_type -> LegalBM25
        self.dense = DenseRetriever(index_dir=str(self.index_dir / "dense"), batch_size=self.config.get("dense", {}).get("batch_size", 32))
        self.reranker = Reranker()

    def _load_config(self, config_path: str) -> dict:
        p = Path(config_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("retrieval", {})
        return {}

    def load(self, scheme: str = "structure"):
        # Load Dense
        self.dense.load_index(scheme)
        
        # Build BM25 and Chunk Store from dense mapping
        # Since dense mappings store the chunks, we can use them
        for dtype, chunks in self.dense.doc_mappings.items():
            bm25 = LegalBM25()
            bm25.fit(chunks)
            self.bm25_engines[dtype] = bm25
            
            for c in chunks:
                self.chunk_store[c.chunk_id] = c
                
    def _apply_quota(self, hits: list[Hit], k: int) -> list[Hit]:
        # Guarantee legal quota (2 statute / 2 judgment) if possible
        statutes = [h for h in hits if h.chunk.meta.get('doc_type') == 'statute']
        judgments = [h for h in hits if h.chunk.meta.get('doc_type') == 'judgment']
        others = [h for h in hits if h.chunk.meta.get('doc_type') not in ('statute', 'judgment')]
        
        final_hits = []
        
        # Add up to 2 statutes
        for _ in range(min(2, len(statutes))):
            final_hits.append(statutes.pop(0))
            
        # Add up to 2 judgments
        for _ in range(min(2, len(judgments))):
            final_hits.append(judgments.pop(0))
            
        # Pool the rest and sort by score
        remaining = statutes + judgments + others
        remaining.sort(key=lambda x: x.score, reverse=True)
        
        # Fill the rest of the quota
        while len(final_hits) < k and remaining:
            final_hits.append(remaining.pop(0))
            
        # Re-sort final hits by score
        final_hits.sort(key=lambda x: x.score, reverse=True)
        return final_hits

    def search(self, query: str, k: int = 8, doc_types: list[DocType] | None = None, doc_ids: list[str] | None = None) -> list[Hit]:
        if not self.chunk_store:
            return []
            
        stages = self.config.get("stages", {})
        use_expansion = stages.get("expansion", True)
        use_dense = stages.get("dense", True)
        use_bm25 = stages.get("bm25", True)
        use_fusion = stages.get("fusion", True)
        use_rerank = stages.get("rerank", True)
        
        if use_expansion:
            query = self.expander.expand(query)
            
        target_dtypes = doc_types if doc_types else ['statute', 'judgment', 'case_file']
        
        lists_of_hits = []
        
        # 1. BM25
        if use_bm25:
            bm25_hits = []
            for dtype in target_dtypes:
                if dtype in self.bm25_engines:
                    dt_hits = self.bm25_engines[dtype].search(query, top_k=50)
                    bm25_hits.extend(dt_hits)
            
            if doc_ids:
                bm25_hits = [(c, s) for c, s in bm25_hits if c.doc_id in doc_ids]
            
            lists_of_hits.append(bm25_hits)
            
        # 2. Dense
        if use_dense:
            dense_hits = self.dense.search(query, target_dtypes, top_k=50)
            if doc_ids:
                dense_hits = [(c, s) for c, s in dense_hits if c.doc_id in doc_ids]
                
            lists_of_hits.append(dense_hits)
            
        # 3. Fusion (or just fallback if only one list)
        fused = []
        if use_fusion and len(lists_of_hits) > 1:
            rrf_k = self.config.get("fusion", {}).get("rrf_k", 60)
            fused = reciprocal_rank_fusion(lists_of_hits, k=rrf_k, top_k=50)
        elif lists_of_hits:
            fused = lists_of_hits[0]
            
        # 4. Rerank
        if use_rerank and fused:
            rerank_k = self.config.get("rerank", {}).get("top_k", 30)
            fused = self.reranker.rerank(query, fused, top_k=rerank_k)
            
        # Map to Hit objects
        final_hits = []
        for chunk, score in fused:
            source_tag = 'fused' if (use_fusion and len(lists_of_hits) > 1) else ('rerank' if use_rerank else 'bm25')
            if not use_fusion and not use_rerank and not use_bm25 and use_dense:
                source_tag = 'dense'
            final_hits.append(Hit(chunk=chunk, score=score, source=source_tag))
            
        # Apply Legal Quota
        return self._apply_quota(final_hits, k)
