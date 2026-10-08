from contracts.schemas import Chunk


def reciprocal_rank_fusion(lists_of_hits: list[list[tuple[Chunk, float]]], k: int = 60, top_k: int = 100) -> list[tuple[Chunk, float]]:
    """
    Fuses multiple ranked lists of hits using Reciprocal Rank Fusion (RRF).
    lists_of_hits is a list of ranked lists. Each ranked list is a list of (Chunk, original_score) tuples.
    """
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}
    
    for hits in lists_of_hits:
        for rank, (chunk, _) in enumerate(hits):
            chunk_id = chunk.chunk_id
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk
            
            rrf_score = 1.0 / (k + rank + 1)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_score
            
    # Sort by RRF score
    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunk_map[chunk_id], score) for chunk_id, score in fused[:top_k]]
