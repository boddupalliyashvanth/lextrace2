def compute_groundedness(claims: list[dict], corpus: dict) -> dict:
    """
    Computes groundedness for a set of extracted claims.
    STRICT: Must carry a valid citation that exists and entails.
    LENIENT: Allowed to search the corpus post-hoc for support.
    """
    total = len(claims)
    if not total:
        return {"strict": 0.0, "lenient": 0.0}
        
    strict_supported = 0
    lenient_supported = 0
    
    for c in claims:
        citations = c.get("citations", [])
        
        # Simulate check: if citations exist, strict passes
        # In reality, this uses an NLI model against the cited chunk
        if citations:
            strict_supported += 1
            lenient_supported += 1
        else:
            # Simulate lenient check: maybe the corpus supports it implicitly
            # In reality, this runs retrieval on the claim against the corpus
            lenient_supported += 1
            
    return {
        "strict": strict_supported / total,
        "lenient": lenient_supported / total
    }
