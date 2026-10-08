"""TASK 3 — Citation registry over data/processed/registry.jsonl.

Provides:
  - CitationRegistry: loads registry, builds normalised alias index
  - resolve(): normalise and look up an alias
  - scan(): find citation-like strings in text and resolve them
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from lextrace.grounding.models import (
    CitationMatch,
    CitationViolation,
    RegistryEntry,
    ViolationType,
)

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "processed" / "registry.jsonl"
)


# ---------------------------------------------------------------------------
# Alias normalisation
# ---------------------------------------------------------------------------

def normalise_alias(alias: str) -> str:
    """Normalise a citation alias for lookup."""
    text = alias.lower().strip()
    text = re.sub(r"\bsec\.", "section", text)
    text = re.sub(r"\bsec\b", "section", text)
    text = re.sub(r"\bs\.", "section", text)
    text = re.sub(r"\bu/s\b", "under section", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Citation patterns
# ---------------------------------------------------------------------------


def _build_statute_section_pattern() -> re.Pattern[str]:
    """Pattern for statute section references."""
    return re.compile(
        r"(?:Section|Sec\.|s\.|u/s|Article)\s*(\d+[A-Za-z]?)"
        r"(?:\s+(?:of\s+(?:the\s+)?)?([A-Z][\w\s,]+?)(?=\s*[,;.\)\]]|\s+\d|\s*$))?",
        re.IGNORECASE,
    )


def _build_case_name_pattern() -> re.Pattern[str]:
    """Pattern for case names: X v. Y, X vs Y, X vs. Y."""
    return re.compile(
        r"(?i:(?:(?:In|Relying on|The case of|The|See)\s+)?)([A-Z][A-Za-z.\s]+?)\s+(?i:v\.|vs\.?|versus)\s+([A-Z][A-Za-z.\s]+?)(?=[,;.\)\]\d]|\s*$|\s+(?i:and)\s+)"
    )


def _build_docket_pattern() -> re.Pattern[str]:
    """Pattern for docket numbers: Appeal, Petition, SLP numbers."""
    return re.compile(
        r"(?:Criminal\s+|Civil\s+|Special\s+Leave\s+)?"
        r"(?:Appeal|Petition|SLP)"
        r"(?:\s+\(?\w+\)?)?\s*"
        r"(?:No\.?\s*)(\d+(?:\s*/\s*\d+)?(?:\s+of\s+\d{4})?)",
        re.IGNORECASE,
    )


def _build_neutral_citation_pattern(reporters: set[str]) -> re.Pattern[str]:
    """Pattern for neutral / reporter citations like (2024) 5 SCC 123.

    Only matches reporters that actually appear in the corpus.
    """
    if not reporters:
        # Fallback: common Indian reporters
        reporters = {"SCC", "AIR", "SCR", "Cr.LJ", "ALD"}
    escaped = [re.escape(r) for r in reporters]
    rpt_group = "|".join(escaped)
    return re.compile(
        r"\(?\s*(\d{4})\s*\)?\s*(\d+)?\s*(" + rpt_group + r")\s+(\d+)",
        re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# CitationRegistry
# ---------------------------------------------------------------------------


class CitationRegistry:
    """Registry of known citations backed by a JSONL file."""

    def __init__(
        self,
        registry_path: str | Path | None = None,
        corpus_docs: set[str] | None = None,
    ) -> None:
        self._path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY_PATH
        self._entries: list[RegistryEntry] = []
        self._alias_index: dict[str, RegistryEntry] = {}
        self._corpus_docs: set[str] = corpus_docs or set()
        self._reporters: set[str] = set()
        self._load()

    def _load(self) -> None:
        """Load the registry from JSONL and build indices."""
        if not self._path.exists():
            logger.warning("Registry file not found: %s", self._path)
            return

        with open(self._path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = RegistryEntry.model_validate(data)
                    self._entries.append(entry)
                except (json.JSONDecodeError, Exception) as exc:
                    logger.warning("Skipping registry line %d: %s", line_no, exc)
                    continue

        # Build alias index
        for entry in self._entries:
            # Index canonical name
            key = normalise_alias(entry.canonical_name)
            self._alias_index[key] = entry
            # Index all aliases
            for alias in entry.aliases:
                key = normalise_alias(alias)
                self._alias_index[key] = entry
            # Collect reporters for pattern building
            if entry.metadata.get("reporter"):
                self._reporters.add(entry.metadata["reporter"])

        # If no corpus_docs provided, derive from entries
        if not self._corpus_docs:
            self._corpus_docs = {e.document for e in self._entries}

        logger.info(
            "Loaded %d registry entries, %d aliases, %d reporters",
            len(self._entries),
            len(self._alias_index),
            len(self._reporters),
        )

    @property
    def entries(self) -> list[RegistryEntry]:
        return list(self._entries)

    @property
    def reporters(self) -> set[str]:
        return set(self._reporters)

    # ------------------------------------------------------------------
    # resolve
    # ------------------------------------------------------------------

    def resolve(self, alias: str) -> RegistryEntry | None:
        """Resolve a citation alias to a registry entry.

        Normalises the alias (case-insensitive, punctuation, section
        abbreviations) before lookup.
        """
        key = normalise_alias(alias)
        return self._alias_index.get(key)

    # ------------------------------------------------------------------
    # scan
    # ------------------------------------------------------------------

    def scan(self, text: str) -> tuple[list[CitationMatch], list[CitationViolation]]:
        """Scan *text* for citation-like strings and resolve them.

        Returns (matches, violations).  Every recognised citation must
        resolve to an entry whose document is in the corpus; otherwise
        a violation is returned.
        """
        matches: list[CitationMatch] = []
        violations: list[CitationViolation] = []

        # Track already-processed spans to avoid duplicates
        covered: set[tuple[int, int]] = set()

        def _is_covered(start: int, end: int) -> bool:
            return any(start < ce and end > cs for cs, ce in covered)

        # 1. Case names
        case_pat = _build_case_name_pattern()
        for m in case_pat.finditer(text):
            if _is_covered(m.start(), m.end()):
                continue
            full_match = m.group(0).strip().rstrip(",;.")
            case_text = f"{m.group(1).strip()} v. {m.group(2).strip()}"
            entry = self.resolve(case_text)
            if entry and entry.document in self._corpus_docs:
                matches.append(
                    CitationMatch(
                        text=full_match,
                        start=m.start(),
                        end=m.end(),
                        entry=entry,
                    )
                )
            else:
                violations.append(
                    CitationViolation(
                        type=ViolationType.CITATION_UNRESOLVED,
                        text=full_match,
                        start=m.start(),
                        end=m.end(),
                        detail=f"Case name '{case_text}' not resolved in registry",
                    )
                )
            covered.add((m.start(), m.end()))

        # 2. Neutral / reporter citations
        reporter_pat = _build_neutral_citation_pattern(self._reporters)
        for m in reporter_pat.finditer(text):
            if _is_covered(m.start(), m.end()):
                continue
            cite_text = m.group(0).strip()
            entry = self.resolve(cite_text)
            if entry and entry.document in self._corpus_docs:
                matches.append(
                    CitationMatch(
                        text=cite_text,
                        start=m.start(),
                        end=m.end(),
                        entry=entry,
                    )
                )
            else:
                violations.append(
                    CitationViolation(
                        type=ViolationType.CITATION_UNRESOLVED,
                        text=cite_text,
                        start=m.start(),
                        end=m.end(),
                        detail=f"Reporter citation '{cite_text}' not resolved",
                    )
                )
            covered.add((m.start(), m.end()))

        # 3. Statute sections
        section_pat = _build_statute_section_pattern()
        for m in section_pat.finditer(text):
            if _is_covered(m.start(), m.end()):
                continue
            sec_num = m.group(1)
            statute_name = m.group(2).strip() if m.group(2) else None

            # Try to resolve the section
            sec_alias = f"section {sec_num}"
            if statute_name:
                sec_alias += f" of {statute_name}"

            entry = self.resolve(sec_alias)

            if entry is None:
                # Try just the section number
                entry = self.resolve(f"section {sec_num}")

            if entry and entry.document in self._corpus_docs:
                # Check statute name matches if both are provided
                if statute_name and entry.statute:
                    norm_statute = normalise_alias(statute_name)
                    norm_entry_statute = normalise_alias(entry.statute)
                    if norm_statute != norm_entry_statute:
                        violations.append(
                            CitationViolation(
                                type=ViolationType.SECTION_NOT_FOUND,
                                text=m.group(0).strip(),
                                start=m.start(),
                                end=m.end(),
                                detail=(
                                    f"Section {sec_num} exists but belongs to "
                                    f"'{entry.statute}', not '{statute_name}'"
                                ),
                            )
                        )
                        covered.add((m.start(), m.end()))
                        continue
                matches.append(
                    CitationMatch(
                        text=m.group(0).strip(),
                        start=m.start(),
                        end=m.end(),
                        entry=entry,
                    )
                )
            else:
                violations.append(
                    CitationViolation(
                        type=ViolationType.SECTION_NOT_FOUND,
                        text=m.group(0).strip(),
                        start=m.start(),
                        end=m.end(),
                        detail=f"Section {sec_num} not found in registry",
                    )
                )
            covered.add((m.start(), m.end()))

        # 4. Docket numbers
        docket_pat = _build_docket_pattern()
        for m in docket_pat.finditer(text):
            if _is_covered(m.start(), m.end()):
                continue
            docket_text = m.group(0).strip()
            entry = self.resolve(docket_text)
            if entry and entry.document in self._corpus_docs:
                matches.append(
                    CitationMatch(
                        text=docket_text,
                        start=m.start(),
                        end=m.end(),
                        entry=entry,
                    )
                )
            else:
                violations.append(
                    CitationViolation(
                        type=ViolationType.CITATION_UNRESOLVED,
                        text=docket_text,
                        start=m.start(),
                        end=m.end(),
                        detail=f"Docket number '{docket_text}' not resolved",
                    )
                )
            covered.add((m.start(), m.end()))

        return matches, violations
