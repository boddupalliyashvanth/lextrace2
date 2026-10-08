"""B2: Long Context baseline."""
from eval.baselines.b1_standard_rag import FakeRetriever

def run_b2(query: str, case_doc_ids: list[str]) -> str:
    retriever = FakeRetriever()
    chunks = retriever.retrieve(query, top_k=5)
    
    # Log retrieved chunk ids
    retrieved_ids = [c["id"] for c in chunks]
    
    # Simulate LLM generating an answer using the full context plus chunks
    output = f"This is the long-context baseline answer for '{query}' using documents {case_doc_ids}. It refers to the full bundle [doc1]."
    
    return {
        "output": output,
        "retrieved_ids": retrieved_ids
    }
