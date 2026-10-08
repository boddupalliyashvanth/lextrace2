import os
import pickle
from pathlib import Path

import faiss
import numpy as np

from contracts.schemas import Chunk


class DenseRetriever:
    def __init__(self, index_dir: str = ".index/dense", batch_size: int = 32):
        self.index_dir = Path(index_dir)
        self.batch_size = batch_size
        self.indices = {}  # doc_type -> faiss index
        self.doc_mappings = {} # doc_type -> list of chunks
        self.model = None

    def _get_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer('BAAI/bge-m3')
            except ImportError:
                self.model = None
        return self.model

    def build_index(self, scheme: str, chunks: list[Chunk]):
        # scheme is 'structure' or 'fixed1000'
        # partition by doc_type
        by_type = {}
        for c in chunks:
            by_type.setdefault(c.doc_type, []).append(c)
            
        model = self._get_model()
        if not model:
            print("Warning: sentence_transformers not installed, skipping dense index build.")
            return

        scheme_dir = self.index_dir / scheme
        os.makedirs(scheme_dir, exist_ok=True)
        
        for dtype, c_list in by_type.items():
            texts = [c.text for c in c_list]
            embeddings = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                emb = model.encode(batch, normalize_embeddings=True)
                embeddings.extend(emb)
            
            embeddings_np = np.array(embeddings).astype('float32')
            dimension = embeddings_np.shape[1]
            
            # FAISS inner product for normalized vectors gives cosine similarity
            index = faiss.IndexFlatIP(dimension)
            index.add(embeddings_np)
            
            faiss.write_index(index, str(scheme_dir / f"{dtype}.faiss"))
            with open(scheme_dir / f"{dtype}_mapping.pkl", "wb") as f:
                pickle.dump(c_list, f)
                
            self.indices[dtype] = index
            self.doc_mappings[dtype] = c_list

    def load_index(self, scheme: str):
        scheme_dir = self.index_dir / scheme
        if not scheme_dir.exists():
            return
            
        for f in os.listdir(scheme_dir):
            if f.endswith(".faiss"):
                dtype = f.replace(".faiss", "")
                self.indices[dtype] = faiss.read_index(str(scheme_dir / f))
                with open(scheme_dir / f"{dtype}_mapping.pkl", "rb") as mf:
                    self.doc_mappings[dtype] = pickle.load(mf)

    def search(self, query: str, doc_types: list[str], top_k: int = 100) -> list[tuple]:
        model = self._get_model()
        if not model or not self.indices:
            return []
            
        emb = model.encode([query], normalize_embeddings=True)
        emb_np = np.array(emb).astype('float32')
        
        all_hits = []
        for dtype in doc_types:
            if dtype in self.indices:
                idx = self.indices[dtype]
                mapping = self.doc_mappings[dtype]
                k = min(top_k, len(mapping))
                if k == 0: continue
                distances, indices = idx.search(emb_np, k)
                for dist, i in zip(distances[0], indices[0]):
                    if i != -1:
                        all_hits.append((mapping[i], float(dist)))
                        
        all_hits.sort(key=lambda x: x[1], reverse=True)
        return all_hits[:top_k]
