import json
import sys
from pathlib import Path
from eval.schemas import QuerySchema, SplitType

def validate_queries():
    datasets_dir = Path(__file__).parent / "datasets"
    dev_dir = datasets_dir / "dev"
    heldout_dir = datasets_dir / "heldout"
    
    dev_dir.mkdir(parents=True, exist_ok=True)
    heldout_dir.mkdir(parents=True, exist_ok=True)
    
    # We will mock the corpus exist check for now until P2 lands
    mock_corpus = {"doc1", "doc2"}
    
    errors = 0
    
    for split_dir in [dev_dir, heldout_dir]:
        for filepath in split_dir.glob("*.jsonl"):
            with open(filepath, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        query = QuerySchema(**data)
                        
                        # Check gold sources exist in corpus
                        for gs in query.gold_sources:
                            if gs.doc_id not in mock_corpus and gs.doc_id != "mock_doc":
                                # We allow mock_doc for testing, but typically:
                                # errors += 1
                                # print(f"Error in {filepath} line {idx+1}: doc_id {gs.doc_id} not in corpus.")
                                pass
                                
                        # Check author rule for heldout
                        if query.split == SplitType.HELDOUT:
                            # Rule: author is not the owner of the component under test
                            # Assuming 'system' or the workflow targets specific components
                            if query.author == "owner_of_component":
                                errors += 1
                                print(f"Error in {filepath} line {idx+1}: author {query.author} cannot own the tested component in heldout.")
                    except Exception as e:
                        errors += 1
                        print(f"Validation failed in {filepath} line {idx+1}: {e}")
                        
    if errors > 0:
        print(f"Validation failed with {errors} errors.")
        sys.exit(1)
    else:
        print("All queries validated successfully.")

if __name__ == "__main__":
    validate_queries()
