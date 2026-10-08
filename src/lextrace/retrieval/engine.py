import json
import pickle
from pathlib import Path

from contracts.schemas import Chunk, DocType, Hit


class HybridRetriever:
    def __init__(self, index_dir: str = ".index"):
        self.index_dir = Path(index_dir)
        self.chunks: list[Chunk] = []
        self.chunk_ids: list[str] = []
        self.bm25 = None
        self.faiss_index = None
        self.model = None
        self._load()

    def _load(self):
        if not self.index_dir.exists():
            return
        
        chunks_path = self.index_dir / "chunks.json"
        if chunks_path.exists():
            with open(chunks_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.chunks = [Chunk(**c) for c in data.values()]
                self.chunk_ids = [c.chunk_id for c in self.chunks]
                
        bm25_path = self.index_dir / "bm25.pkl"
        if bm25_path.exists():
            with open(bm25_path, "rb") as f:
                self.bm25 = pickle.load(f)
                
        faiss_path = self.index_dir / "faiss.index"
        if faiss_path.exists():
            import faiss
            from sentence_transformers import SentenceTransformer
            self.faiss_index = faiss.read_index(str(faiss_path))
            self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def search(self, query: str, k: int = 8, doc_types: list[DocType] | None = None, doc_ids: list[str] | None = None) -> list[Hit]:
        if not self.chunks:
            return []
            
        # BM25 scores
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query) if self.bm25 else [0] * len(self.chunks)
        
        # FAISS scores
        faiss_scores = [0] * len(self.chunks)
        if self.faiss_index and self.model:
            import numpy as np
            emb = self.model.encode([query])
            distances, indices = self.faiss_index.search(np.array(emb).astype('float32'), k * 2)
            for dist, idx in zip(distances[0], indices[0]):
                if idx != -1:
                    # In FAISS L2, smaller distance is better. Convert to similarity score.
                    faiss_scores[idx] = 1.0 / (1.0 + float(dist))

        # Combine scores and filter
        hits = []
        for i, chunk in enumerate(self.chunks):
            if doc_types and chunk.doc_type not in doc_types:
                continue
            if doc_ids and chunk.doc_id not in doc_ids:
                continue
            
            score = (bm25_scores[i] * 0.5) + (faiss_scores[i] * 5.0)  # simple weighting
            if score > 0:
                hits.append(Hit(chunk=chunk, score=score))
                
        # Sort and take top k
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
