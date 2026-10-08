import json
from pathlib import Path

def generate_dev_set():
    out_file = Path("eval/datasets/dev/dev_set.jsonl")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    queries = []
    workflows = ["review", "draft", "research", "summarize"]
    
    # 4 workflows * 12 = 48 queries.
    # Includes 8 UNANSWERABLE and 6 planted.
    
    # Generate 48 queries
    for i in range(48):
        wf = workflows[i % 4]
        doc_id = f"doc{(i % 8) + 1}"
        
        # 8 unanswerable
        if i < 8:
            q = {
                "qid": f"q_unans_{i}",
                "workflow": wf,
                "query": "What is the completely made up fact?",
                "case_doc_ids": [doc_id],
                "gold_sources": [],
                "gold_points": ["I could not find sufficient evidence in the provided documents to answer the question."],
                "must_not": [],
                "split": "dev",
                "author": "p4"
            }
        # 6 planted
        elif i >= 8 and i < 14:
            q = {
                "qid": f"q_planted_{i}",
                "workflow": wf,
                "query": "What is the planted contradiction?",
                "case_doc_ids": [doc_id],
                "gold_sources": [{"doc_id": doc_id, "locator": "planted", "quote": "Planted contradiction"}],
                "gold_points": ["Contradiction found"],
                "must_not": [],
                "split": "dev",
                "author": "p4"
            }
        else:
            q = {
                "qid": f"q_std_{i}",
                "workflow": wf,
                "query": f"Standard query {i}?",
                "case_doc_ids": [doc_id],
                "gold_sources": [{"doc_id": doc_id, "locator": f"para {i}", "quote": f"test {i}"}],
                "gold_points": [f"Standard point {i}"],
                "must_not": [],
                "split": "dev",
                "author": "p4"
            }
        queries.append(q)
        
    with open(out_file, "w") as f:
        for q in queries:
            f.write(json.dumps(q) + "\n")
            
    print(f"Generated {len(queries)} queries in {out_file}")

if __name__ == "__main__":
    generate_dev_set()
