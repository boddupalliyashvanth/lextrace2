#!/usr/bin/env python3
"""TASK 4 — Independent fabrication audit script.

Usage:
    python scripts/audit_fabrication.py OUTPUTS.jsonl [--corpus CORPUS_DIR] [--registry REGISTRY.jsonl]

This script is INDEPENDENT of the pipeline code paths.  It re-implements
normalisation and checking from scratch so it can serve as ground-truth
for P4 scoring.

For every output in OUTPUTS.jsonl:
  1. Quote audit: search the ENTIRE normalised corpus for every quote.
  2. Citation audit: resolve every citation-like string in the registry.
  3. Fact audit: verify numbers, dates, and names against cited evidence.

Prints counts of fabricated quotes, citations, and facts.
Exits non-zero if any fabrication is found.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
)
logger = logging.getLogger("audit_fabrication")


# ========================================================================
# INDEPENDENT normalisation — does NOT import from lextrace.grounding
# ========================================================================

_QUOTE_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u00ab": '"', "\u00bb": '"', "\u2039": "'", "\u203a": "'",
})
_DASH_MAP = str.maketrans({
    "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2012": "-",
    "\u2010": "-", "\u2011": "-", "\ufe58": "-", "\ufe63": "-",
    "\uff0d": "-",
})


def _norm(text: str) -> str:
    """Full normalisation pipeline (independent copy)."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTE_MAP)
    text = text.translate(_DASH_MAP)
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_number(s: str) -> str:
    return s.replace(",", "")


def _extract_numbers(text: str) -> set[str]:
    return {
        _norm_number(m.group())
        for m in re.finditer(r"\b[\d,]+(?:\.\d+)?\b", text)
        if any(c.isdigit() for c in m.group())
    }


_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09", "sept": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

_DATE_DMY = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_DATE_NAMED = re.compile(
    r"\b(?:(\d{1,2})\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\.?\s+(\d{1,2})?[,\s]*(\d{4})\b",
    re.IGNORECASE,
)


def _extract_dates(text: str) -> set[str]:
    results: set[str] = set()
    for m in _DATE_DMY.finditer(text):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        results.add(f"{int(d):02d}-{int(mo):02d}-{y}")
    for m in _DATE_NAMED.finditer(text):
        day = m.group(1) or m.group(3)
        month_name = m.group(2).lower().rstrip(".")
        year = m.group(4)
        if day and month_name in _MONTH_MAP:
            results.add(f"{int(day):02d}-{_MONTH_MAP[month_name]}-{year}")
    return results


_CAP_NAME_RE = re.compile(r"\b([A-Z][a-zA-Z0-9_]*(?:\s+(?:of|the|v\.|vs\.?|versus|and)\s+[A-Z][a-zA-Z0-9_]*|\s+[A-Z][a-zA-Z0-9_]*)+)\b")


def _extract_names(text: str) -> set[str]:
    return {m.group(0) for m in _CAP_NAME_RE.finditer(text)}


def _split_ellipsis(text: str) -> list[str]:
    parts = re.split(r"\.{3}|\u2026", text)
    return [p.strip() for p in parts if p.strip()]


# ========================================================================
# Corpus loading
# ========================================================================


def load_corpus(corpus_path: Path) -> dict[str, str]:
    """Load the entire corpus as chunk_id → normalised text.

    Supports either:
      - A directory of .txt/.json files
      - A single JSONL file with {chunk_id, text} per line
    """
    corpus: dict[str, str] = {}

    if corpus_path.is_file() and corpus_path.suffix == ".jsonl":
        with open(corpus_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                cid = obj.get("chunk_id", obj.get("id", ""))
                text = obj.get("text", "")
                corpus[cid] = _norm(text)
    elif corpus_path.is_dir():
        for p in sorted(corpus_path.rglob("*")):
            if p.suffix in (".txt", ".md"):
                corpus[p.stem] = _norm(p.read_text(encoding="utf-8"))
            elif p.suffix == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cid = data.get("chunk_id", data.get("id", p.stem))
                    corpus[cid] = _norm(data.get("text", ""))
    else:
        logger.error("Corpus path %s is not a file or directory", corpus_path)

    logger.info("Loaded %d corpus chunks", len(corpus))
    return corpus


# ========================================================================
# Registry loading (independent)
# ========================================================================

def _norm_alias(alias: str) -> str:
    text = alias.lower().strip()
    text = re.sub(r"\bsec\.", "section", text)
    text = re.sub(r"\bsec\b", "section", text)
    text = re.sub(r"\bs\.", "section", text)
    text = re.sub(r"\bu/s\b", "under section", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_registry(registry_path: Path) -> dict[str, dict]:
    """Load the registry as normalised_alias → entry dict."""
    index: dict[str, dict] = {}
    if not registry_path.exists():
        logger.warning("Registry not found: %s", registry_path)
        return index

    with open(registry_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = _norm_alias(entry.get("canonical_name", ""))
            index[key] = entry
            for alias in entry.get("aliases", []):
                index[_norm_alias(alias)] = entry
    logger.info("Loaded %d registry aliases", len(index))
    return index


# ========================================================================
# Citation scanning (independent)
# ========================================================================

_CASE_PAT = re.compile(
    r"(?i:(?:(?:In|Relying on|The case of|The|See)\s+)?)([A-Z][A-Za-z.\s]+?)\s+(?i:v\.|vs\.?|versus)\s+([A-Z][A-Za-z.\s]+?)(?=[,;.\)\]\d]|\s*$|\s+(?i:and)\s+)"
)
_SECTION_PAT = re.compile(
    r"(?:Section|Sec\.|s\.|u/s|Article)\s*(\d+[A-Za-z]?)",
    re.IGNORECASE,
)


def scan_citations(text: str, registry: dict[str, dict], corpus_docs: set[str]) -> list[str]:
    """Return list of unresolved citation-like strings."""
    unresolved: list[str] = []

    for m in _CASE_PAT.finditer(text):
        case_text = f"{m.group(1).strip()} v. {m.group(2).strip()}"
        key = _norm_alias(case_text)
        entry = registry.get(key)
        if not entry or entry.get("document") not in corpus_docs:
            unresolved.append(m.group(0).strip().rstrip(",;."))

    for m in _SECTION_PAT.finditer(text):
        sec_text = m.group(0).strip()
        key = _norm_alias(sec_text)
        entry = registry.get(key)
        if not entry or entry.get("document") not in corpus_docs:
            unresolved.append(sec_text)

    return unresolved


# ========================================================================
# Audit logic
# ========================================================================


def audit_output(
    output: dict,
    full_corpus: dict[str, str],
    registry: dict[str, dict],
    corpus_docs: set[str],
) -> tuple[int, int, int]:
    """Audit a single output entry.

    Returns (fabricated_quotes, fabricated_citations, fabricated_facts).
    """
    fab_quotes = 0
    fab_citations = 0
    fab_facts = 0

    claims = output.get("claims", [])
    full_text = " ".join(full_corpus.values())

    for claim in claims:
        claim_text = claim.get("text", "")
        evidence_list = claim.get("evidence", [])

        # Combine evidence quotes
        combined_ev = ""
        for ev in evidence_list:
            quote = ev.get("quote", "")
            norm_quote = _norm(quote)

            # 1. Quote audit — search ENTIRE corpus
            segments = _split_ellipsis(norm_quote)
            found = True
            if segments:
                search_pos = 0
                for seg in segments:
                    idx = full_text.find(seg, search_pos)
                    if idx == -1:
                        # Try from beginning
                        idx = full_text.find(seg)
                    if idx == -1:
                        found = False
                        break
                    search_pos = idx + len(seg)

            if not found:
                fab_quotes += 1
                logger.warning("FABRICATED QUOTE: '%s...'", quote[:80])

            combined_ev += " " + quote

        norm_ev = _norm(combined_ev)

        # 2. Citation audit
        unresolved = scan_citations(claim_text, registry, corpus_docs)
        fab_citations += len(unresolved)
        for u in unresolved:
            logger.warning("FABRICATED CITATION: '%s'", u)

        # 3. Fact audit — numbers, dates, names
        claim_nums = _extract_numbers(claim_text)
        ev_nums = _extract_numbers(norm_ev)
        for n in claim_nums:
            if n not in ev_nums:
                fab_facts += 1
                logger.warning("FABRICATED FACT (number): '%s' in '%s'", n, claim_text[:80])

        claim_dates = _extract_dates(claim_text)
        ev_dates = _extract_dates(norm_ev)
        for d in claim_dates:
            if d not in ev_dates:
                fab_facts += 1
                logger.warning("FABRICATED FACT (date): '%s' in '%s'", d, claim_text[:80])

        claim_names = _extract_names(claim_text)
        ev_names = _extract_names(norm_ev)
        for name in claim_names:
            if name not in ev_names and _norm(name) not in norm_ev:
                fab_facts += 1
                logger.warning("FABRICATED FACT (name): '%s' in '%s'", name, claim_text[:80])

    return fab_quotes, fab_citations, fab_facts


# ========================================================================
# Main
# ========================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit OUTPUTS.jsonl for fabricated quotes, citations, and facts."
    )
    parser.add_argument("outputs", type=Path, help="Path to OUTPUTS.jsonl")
    parser.add_argument("--corpus", type=Path, default=None, help="Corpus directory or JSONL")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "processed" / "registry.jsonl",
        help="Path to registry.jsonl",
    )
    args = parser.parse_args(argv)

    if not args.outputs.exists():
        logger.error("OUTPUTS file not found: %s", args.outputs)
        return 1

    # Load corpus
    full_corpus: dict[str, str] = {}
    if args.corpus:
        full_corpus = load_corpus(args.corpus)
    else:
        logger.warning("No --corpus specified; quote audit will be limited")

    # Load registry
    registry = load_registry(args.registry)
    corpus_docs = {e.get("document", "") for e in registry.values()}

    # Process outputs
    total_quotes = 0
    total_citations = 0
    total_facts = 0

    with open(args.outputs, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                output = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.error("Line %d: invalid JSON: %s", line_no, exc)
                continue

            fq, fc, ff = audit_output(output, full_corpus, registry, corpus_docs)
            total_quotes += fq
            total_citations += fc
            total_facts += ff

    # Report
    print()
    print("=" * 60)
    print("FABRICATION AUDIT REPORT")
    print("=" * 60)
    print(f"  Fabricated quotes:    {total_quotes}")
    print(f"  Fabricated citations: {total_citations}")
    print(f"  Fabricated facts:     {total_facts}")
    total = total_quotes + total_citations + total_facts
    print(f"  TOTAL fabrications:   {total}")
    print("=" * 60)

    if total > 0:
        print("\nRESULT: FAIL — fabrications detected")
        return 1
    else:
        print("\nRESULT: PASS — no fabrications")
        return 0


if __name__ == "__main__":
    sys.exit(main())
