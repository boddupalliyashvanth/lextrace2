import json
import os
from contracts.schemas import WorkflowRequest
from tests.fakes import FakeRetriever, FakeClaimGenerator, FakeVerifier, FakeRenderer
from src.lextrace.workflows.research import ResearchWorkflow

def run_demo():
    # Make sure corpus directory exists for FakeRetriever
    os.makedirs('.cache/corpus', exist_ok=True)
    if not os.listdir('.cache/corpus'):
        with open('.cache/corpus/dummy.json', 'w') as f:
            json.dump({
                "doc_id": "dummy",
                "chunks": [{"chunk_id": "dummy::1", "text": "Dummy text", "page_start":1, "page_end":1, "char_start":0, "char_end":10}]
            }, f)

    retriever = FakeRetriever('.cache/corpus')
    claimgen = FakeClaimGenerator()
    verifier = FakeVerifier()
    renderer = FakeRenderer()
    wf = ResearchWorkflow(retriever, claimgen, verifier, renderer)

    bundles = [
        {"query": "Is this a valid FIR under 420 IPC?", "case_doc_ids": ["case_b1"]},
        {"query": "Bail for foreigner under NDPS?", "case_doc_ids": ["case_b2"]},
        {"query": "Quashing FIR due to civil dispute?", "case_doc_ids": ["case_b3"]}
    ]

    os.makedirs('eval/results/memos', exist_ok=True)
    for i, b in enumerate(bundles):
        req = WorkflowRequest(workflow='research', query=b['query'], case_doc_ids=b['case_doc_ids'])
        out = wf.run(req)
        
        out_path = f"eval/results/memos/memo_bundle_{i+1}.json"
        with open(out_path, 'w') as f:
            f.write(out.model_dump_json(indent=2))
        print(f"Wrote memo to {out_path}")

if __name__ == '__main__':
    run_demo()
