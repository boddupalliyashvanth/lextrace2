import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock

from lextrace.workflows.draft import Workflow

def test_draft_golden(tmp_path):
    # Setup mock LLM that always returns NOT_FOUND for dates and values for others
    def fake_llm(prompt: str, role: str) -> str:
        if "Arrest Date" in prompt:
            return "NOT_FOUND"
        if "Applicant Name" in prompt:
            return "John Doe"
        if "FIR Number" in prompt:
            return "FIR 123/2023"
        return "mock"

    workflow = Workflow(name="draft", llm_call=fake_llm)
    
    chunks = {"chunk1": "John Doe was arrested under FIR 123/2023."}
    
    # Run pre-drafting report
    report = workflow.generate_report(["doc1"], chunks, "bail_regular")
    
    assert len(report["slots_filled_with_confidence"]) > 0
    assert any(s["spec"]["name"] == "Arrest Date" for s in report["slots_not_found"])
    
    # Run draft with user facts
    params = {
        "doc_type": "bail_regular",
        "user_facts": {
            # User overrides Arrest Date to not trigger placeholder
            "Arrest Date": "1st Jan 2023"
        }
    }
    
    output = workflow.run(params, chunks)
    
    assert "John Doe" in output
    assert "FIR 123/2023" in output
    assert "1st Jan 2023" in output
    assert "Provided by user" in output  # from USER_INPUT
    assert "Not legal advice" in output
    
def test_draft_adversarial_placeholder():
    def fake_llm(prompt: str, role: str) -> str:
        return "NOT_FOUND"
        
    workflow = Workflow(name="draft", llm_call=fake_llm)
    
    chunks = {"chunk1": "Some text."}
    
    # User doesn't provide anything. System refuses and leaves placeholder
    params = {"doc_type": "bail_regular"}
    output = workflow.run(params, chunks)
    
    assert "[MISSING: Applicant Name: not found in the provided documents]" in output
    assert "[MISSING: Arrest Date: not found in the provided documents]" in output

def test_boilerplate_statute_stripped(tmp_path):
    # A boilerplate containing an absent statute reference
    template_dir = Path("templates/boilerplate")
    template_dir.mkdir(parents=True, exist_ok=True)
    poisoned_file = template_dir / "poisoned_header.md"
    poisoned_file.write_text("IN THE COURT. Application under Section 999 of the Fake Act.")
    
    template_yaml = Path("templates/bail_poisoned.yaml")
    template_yaml.write_text('''
sections:
  - type: boilerplate
    name: "Header"
    file: "templates/boilerplate/poisoned_header.md"
''')

    workflow = Workflow(name="draft", llm_call=lambda p, r: "mock")
    chunks = {"chunk1": "Mock"}
    
    output = workflow.run({"doc_type": "bail_poisoned"}, chunks)
    
    # The gate should strip "Application under Section 999 of the Fake Act." 
    # Actually wait! The gate drops the sentence!
    assert "Section 999" not in output
    
    # Clean up
    poisoned_file.unlink()
    template_yaml.unlink()
