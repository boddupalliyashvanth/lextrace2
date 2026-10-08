"""TASK 4 — Renderer.

Composes the final markdown response from supported claims.
"""

from __future__ import annotations

from pathlib import Path

from lextrace.grounding.citation_registry import CitationRegistry
from lextrace.grounding.models import ClaimKind, Verdict, VerifiedClaim

_WHITELIST_PATH = Path(__file__).resolve().parents[3] / "prompts" / "grounding" / "template_text.md"


class Renderer:
    def __init__(self, registry: CitationRegistry | None = None):
        self.registry = registry
        if _WHITELIST_PATH.exists():
            self.whitelist = {line.strip() for line in _WHITELIST_PATH.read_text(encoding="utf-8").splitlines() if line.strip()}
        else:
            self.whitelist = set()

    def _is_whitelisted(self, text: str) -> bool:
        # Check exact matches or generic regex for placeholders like [MISSING: <slot>]
        for w in self.whitelist:
            if text == w:
                return True
            if "[MISSING:" in w and text.startswith("[MISSING:") and text.endswith("]"):
                return True
        return False

    def render(self, claims: list[VerifiedClaim]) -> str:
        """Render the final response from supported claims."""
        output_parts = []
        sources = []
        source_idx = 1

        for claim in claims:
            if claim.verdict != Verdict.SUPPORTED:
                continue

            text = claim.text

            if claim.kind == ClaimKind.TEMPLATE_TEXT:
                if self._is_whitelisted(text):
                    if self.registry:
                        _, violations = self.registry.scan(text)
                        if violations:
                            continue # Template text failed registry scan
                    output_parts.append(text)
                continue

            if claim.supported_by_user:
                output_parts.append(f"> **Provided by user:** {text}")
                continue

            # Standard claim
            output_parts.append(f"{text} [{source_idx}]")

            # Format sources
            for ev in claim.evidence:
                # Naive source formatting; in reality, we'd lookup the doc canonical name
                sources.append(f"[{source_idx}] {ev.chunk_id} - \"{ev.quote}\"")
            source_idx += 1

        if not output_parts:
            return "I could not find sufficient evidence in the provided documents to answer the question."

        body = " ".join(output_parts)
        if sources:
            body += "\n\n### Sources\n" + "\n".join(sources)

        return body
