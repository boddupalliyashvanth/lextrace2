"""Demo script to run the drafting workflow on 3 bundles and verify output."""
import json
import subprocess
from pathlib import Path
from lextrace.workflows.draft import Workflow

def mock_llm(prompt: str, role: str) -> str:
    # A simple mock that finds some info
    if "Applicant Name" in prompt:
        if "doc1" in prompt: return "Alice Smith"
        if "doc2" in prompt: return "Bob Jones"
        if "doc3" in prompt: return "Charlie Brown"
        return "Unknown"
    if "FIR Number" in prompt:
        return "FIR 42/2023"
    if "Arrest Date" in prompt:
        return "NOT_FOUND" # Let's see the placeholder
    return "mock"

def main():
    wf = Workflow(name="draft", llm_call=mock_llm)
    
    bundles = [
        {"id": "doc1", "chunks": {"c1": "Alice Smith was arrested on doc1.", "c2": "FIR 42/2023"}},
        {"id": "doc2", "chunks": {"c1": "Bob Jones was arrested on doc2.", "c2": "FIR 42/2023"}},
        {"id": "doc3", "chunks": {"c1": "Charlie Brown was arrested on doc3.", "c2": "FIR 42/2023"}},
    ]
    
    for i, bundle in enumerate(bundles):
        print(f"\\n--- Drafting for Bundle {i+1} ({bundle['id']}) ---")
        
        # Override llm mock behavior slightly by injecting doc_id context
        def bundle_llm(p, r):
            return mock_llm(p + " " + bundle['id'], r)
            
        wf.llm_call = bundle_llm
        wf.slot_filler.llm_call = bundle_llm
        
        output = wf.run({"doc_type": "bail_regular"}, bundle["chunks"])
        print(output)
        
        # Run audit fabrication
        # In a real setup, output would be saved to a file and audited.
        # Here we just save the final output
        out_file = Path(f"draft_output_{i+1}.md")
        out_file.write_text(output, encoding="utf-8")
        
        result = subprocess.run(["python", "scripts/audit_fabrication.py", str(out_file)], capture_output=True, text=True)
        print(f"Audit Result for Bundle {i+1}: Exit Code {result.returncode}")
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
        
if __name__ == "__main__":
    main()
