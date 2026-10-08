import inspect

from contracts.interfaces import (
    LLM,
    ClaimGenerator,
    Renderer,
    Retriever,
    Verifier,
)
from tests.fakes import (
    FakeClaimGenerator,
    FakeLLM,
    FakeRenderer,
    FakeRetriever,
    FakeVerifier,
)


def check_protocol(impl, protocol):
    for name, method in inspect.getmembers(protocol, predicate=inspect.isfunction):
        if not hasattr(impl, name):
            raise AssertionError(f"{impl.__name__} missing method {name}")
        impl_method = getattr(impl, name)
        assert callable(impl_method)

def test_fakes_conform_to_interfaces():
    check_protocol(FakeRetriever, Retriever)
    check_protocol(FakeLLM, LLM)
    check_protocol(FakeClaimGenerator, ClaimGenerator)
    check_protocol(FakeVerifier, Verifier)
    check_protocol(FakeRenderer, Renderer)
