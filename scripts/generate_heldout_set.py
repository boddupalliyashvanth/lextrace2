import json
from pathlib import Path

def generate_heldout_set():
    out_file = Path("eval/datasets/heldout/heldout_set.jsonl")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    queries = []
    
    # Teammate -> target component they DON'T own
    # P1 (retrieval) -> tests P3 (grounding)
    # P2 (synthesis) -> tests P4 (eval)
    # P3 (grounding) -> tests P1 (retrieval)
    # P4 (eval) -> tests P2 (synthesis)
    
    authors = ["P1", "P2", "P3", "P4"]
    for i, author in enumerate(authors):
        for j in range(5):
            q = {
                "qid": f"heldout_{author}_{j}",
                "workflow": "review",
                "query": f"Heldout query {j} from {author}",
                "case_doc_ids": ["doc1"],
                "gold_sources": [{"doc_id": "doc1", "locator": "para 1", "quote": "mock"}],
                "gold_points": ["mock point"],
                "must_not": [],
                "split": "heldout",
                "author": author
            }
            queries.append(q)
            
    with open(out_file, "w") as f:
        for q in queries:
            f.write(json.dumps(q) + "\n")
            
    print(f"Generated {len(queries)} heldout queries in {out_file}")

if __name__ == "__main__":
    generate_heldout_set()
