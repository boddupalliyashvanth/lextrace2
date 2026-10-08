import math

def calculate_recall(retrieved: list[str], gold: list[str], k: int) -> float:
    retrieved_k = retrieved[:k]
    hits = sum(1 for g in gold if g in retrieved_k)
    return hits / len(gold) if gold else 0.0

def calculate_mrr(retrieved: list[str], gold: list[str], k: int) -> float:
    for i, r in enumerate(retrieved[:k]):
        if r in gold:
            return 1.0 / (i + 1)
    return 0.0

def calculate_ndcg(retrieved: list[str], gold: list[str], k: int) -> float:
    dcg = 0.0
    for i, r in enumerate(retrieved[:k]):
        if r in gold:
            dcg += 1.0 / math.log2(i + 2)
            
    idcg = 0.0
    for i in range(min(len(gold), k)):
        idcg += 1.0 / math.log2(i + 2)
        
    return dcg / idcg if idcg > 0 else 0.0
