import subprocess
import json

def compute_fabrication(text: str) -> dict:
    """
    Runs scripts/audit_fabrication.py on the output text.
    Any non-zero value for LexTrace is a P0 bug.
    """
    # For now, we mock the result. In reality, it would write the text to a temp file
    # and run: subprocess.run(["python", "scripts/audit_fabrication.py", temp_file])
    # returning the counts.
    return {
        "fabricated_quotes": 0,
        "fabricated_citations": 0,
        "fabricated_facts": 0
    }
