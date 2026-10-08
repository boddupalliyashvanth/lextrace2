from contracts.schemas import Chunk


class Reranker:
    def __init__(self):
        self.model = None
        
    def _get_model(self):
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
                self.model = CrossEncoder('BAAI/bge-reranker-v2-m3')
            except ImportError:
                self.model = None
        return self.model

    def rerank(self, query: str, hits: list[tuple[Chunk, float]], top_k: int = 30) -> list[tuple[Chunk, float]]:
        model = self._get_model()
        if not model or not hits:
            return hits[:top_k]
            
        pairs = [[query, chunk.text] for chunk, _ in hits]
        scores = model.predict(pairs)
        
        rescored = [(hits[i][0], float(scores[i])) for i in range(len(hits))]
        rescored.sort(key=lambda x: x[1], reverse=True)
        return rescored[:top_k]
