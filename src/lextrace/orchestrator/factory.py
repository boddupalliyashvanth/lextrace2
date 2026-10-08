import os

import yaml

from lextrace.orchestrator.graph import LexTraceGraph
from tests.fakes import FakeClaimGenerator, FakeRenderer, FakeRetriever, FakeVerifier


def build_system(config_dir: str):
    with open(os.path.join(config_dir, "features.yaml")) as f:
        features = yaml.safe_load(f)

    from lextrace.generation.claims import RealClaimGenerator, RealVerifier
    from lextrace.llm.client import GoogleGenAILLM
    from lextrace.retrieval.engine import HybridRetriever
    
    if features.get("retriever") == "fake":
        retriever = FakeRetriever("tests/fixtures/mini_corpus")
    else:
        retriever = HybridRetriever(".index")

    if features.get("claimgen") != "fake" or features.get("verifier") != "fake":
        llm = GoogleGenAILLM(config_dir=config_dir)
    else:
        llm = None

    if features.get("claimgen") == "fake":
        claimgen = FakeClaimGenerator()
    else:
        claimgen = RealClaimGenerator(llm)

    if features.get("verifier") == "fake":
        verifier = FakeVerifier()
    else:
        verifier = RealVerifier(llm)
        
    renderer = FakeRenderer()

    return LexTraceGraph(
        retriever=retriever,
        claim_generator=claimgen,
        verifier=verifier,
        renderer=renderer
    )
