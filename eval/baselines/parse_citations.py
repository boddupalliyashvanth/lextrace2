import re

def parse_citations(text: str) -> list[dict]:
    """
    Independent extractor model + deterministic post-checks.
    Extracts claims and their associated citations from free text.
    """
    # Simple regex mock: splits by sentence, finds bracketed citations
    sentences = re.split(r"(?<=[.!?])\s+", text)
    claims = []
    
    for s in sentences:
        s = s.strip()
        if not s:
            continue
            
        citations = re.findall(r"\[(.*?)\]", s)
        clean_text = re.sub(r"\[.*?\]", "", s).strip()
        
        if citations:
            claims.append({
                "text": clean_text,
                "citations": citations
            })
            
    return claims
