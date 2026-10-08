def compute_retrieval(retrieved_ids: list[str], gold_sources: list[dict]) -> dict:
    """
    Imports P2's metrics and applies them to retrieved sets.
    Computes recall, precision, etc.
    """
    gold_ids = {g["doc_id"] for g in gold_sources}
    if not gold_ids:
        return {"recall": 1.0, "precision": 1.0}
        
    retrieved_set = set(retrieved_ids)
    hits = retrieved_set.intersection(gold_ids)
    
    recall = len(hits) / len(gold_ids)
    precision = len(hits) / len(retrieved_set) if retrieved_set else 0.0
    
    return {
        "recall": recall,
        "precision": precision
    }
