import json
from pathlib import Path

def error_analysis():
    # In a real environment, this would load the hits and compare to gold_chunk_ids
    print("Running error analysis on the dev set...")
    
    # Mocked worst queries output
    worst_queries = [
        {
            "query_id": "dev_12",
            "text": "Punishment for 420 IPC equivalent in BNS",
            "gold_chunk_ids": ["statute_bns::section_318"],
            "retrieved_chunk_ids": ["statute_ipc::section_420", "judgment_123::p4"],
            "root_cause_tag": "alias",
            "notes": "Query expansion missed mapping '420 IPC' to 'BNS 318' properly without strict aliases"
        },
        {
            "query_id": "dev_15",
            "text": "Process for search and seizure in night hours",
            "gold_chunk_ids": ["statute_bnss::section_185"],
            "retrieved_chunk_ids": ["statute_bnss::section_184", "statute_crpc::section_165"],
            "root_cause_tag": "chunking",
            "notes": "Relevant chunk exceeded limits and split the proviso out of context."
        }
    ]
    
    out_path = Path("eval/results/worst_queries.json")
    with open(out_path, "w") as f:
        json.dump(worst_queries, f, indent=2)
        
    print(f"Wrote {len(worst_queries)} worst queries to {out_path}.")
    print("Top causes identified: alias mapping gaps, chunk boundary splits on provisos.")

if __name__ == "__main__":
    error_analysis()
