"""B1: Standard RAG baseline."""
import json
from pathlib import Path

class FakeRetriever:
    def retrieve(self, query: str, top_k: int = 5):
        # Return mock chunks
        return [{"id": f"chunk_{i}", "text": f"Mock retrieved text for {query} ({i})"} for i in range(top_k)]

def run_b1(query: str, case_doc_ids: list[str]) -> str:
    retriever = FakeRetriever()
    chunks = retriever.retrieve(query, top_k=5)
    
    # Log retrieved chunk ids
    retrieved_ids = [c["id"] for c in chunks]
    
    # Simulate LLM generating an answer with citations
    output = f"This is the baseline answer for '{query}'. It relies on standard retrieval [chunk_0]."
    
    return {
        "output": output,
        "retrieved_ids": retrieved_ids
    }
