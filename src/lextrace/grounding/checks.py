"""TASK 2 — Deterministic grounding checks.

Four checks run on every claim:
  a. chunk_exists      - evidence chunk_ids are valid
  b. quote_verbatim    - quotes are substrings of source (with snap)
  c. atoms             - numbers, dates, money, names, sections match evidence
  d. injection_heuristics - flag prompt-injection attempts in chunk text
"""

from __future__ import annotations

import logging
import re

from rapidfuzz.fuzz import ratio as fuzz_ratio

from lextrace.grounding.models import (
    CheckResult,
    Claim,
    Violation,
    ViolationType,
)
from lextrace.grounding.normalise import (
    extract_bare_numbers,
    extract_capitalised_names,
    extract_dates,
    extract_money,
    extract_section_numbers,
    normalise_text,
    split_on_ellipsis,
)

logger = logging.getLogger(__name__)

_SNAP_THRESHOLD = 92.0  # minimum fuzzy ratio to snap


# ---------------------------------------------------------------------------
# 2a. chunk_exists
# ---------------------------------------------------------------------------


def check_chunk_exists(
    claim: Claim,
    chunks: dict[str, str],
) -> list[Violation]:
    """Verify every evidence chunk_id exists in the chunk map."""
    violations: list[Violation] = []
    for ev in claim.evidence:
        if ev.chunk_id not in chunks:
            violations.append(
                Violation(
                    type=ViolationType.CHUNK_NOT_FOUND,
                    claim_text=claim.text,
                    chunk_id=ev.chunk_id,
                    detail=f"chunk_id '{ev.chunk_id}' not found in provided chunks",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# 2b. quote_verbatim
# ---------------------------------------------------------------------------


def _find_best_fuzzy_span(needle: str, haystack: str) -> tuple[float, str]:
    """Find the best fuzzy match of *needle* in *haystack*.

    Returns (ratio, matched_span).
    """
    n_len = len(needle)
    if n_len == 0 or len(haystack) == 0:
        return 0.0, ""

    best_ratio = 0.0
    best_span = ""
    # Slide a window of roughly needle-length across haystack
    for window_delta in range(-max(5, n_len // 4), max(5, n_len // 4) + 1):
        w = n_len + window_delta
        if w <= 0 or w > len(haystack):
            continue
        for start in range(len(haystack) - w + 1):
            candidate = haystack[start : start + w]
            r = fuzz_ratio(needle, candidate)
            if r > best_ratio:
                best_ratio = r
                best_span = candidate
                if r == 100.0:
                    return r, best_span
    return best_ratio, best_span


def check_quote_verbatim(
    claim: Claim,
    chunks: dict[str, str],
) -> tuple[list[Violation], dict[str, str]]:
    """Verify quotes are verbatim substrings of the source chunk.

    Returns (violations, snapped_quotes) where snapped_quotes maps
    original quote → exact source span when snap was applied.
    """
    violations: list[Violation] = []
    snapped: dict[str, str] = {}

    for ev in claim.evidence:
        if ev.chunk_id not in chunks:
            # Already caught by chunk_exists; skip here
            continue

        norm_chunk = normalise_text(chunks[ev.chunk_id])
        norm_quote = normalise_text(ev.quote)

        # Split on ellipsis
        segments = split_on_ellipsis(norm_quote)
        if not segments:
            continue

        all_exact = True
        last_end = 0

        for seg in segments:
            idx = norm_chunk.find(seg, last_end)
            if idx == -1:
                # Try from the beginning (in case ordering is still valid
                # but segments overlap)
                idx = norm_chunk.find(seg)
            if idx == -1:
                all_exact = False
                break
            last_end = idx + len(seg)

        if all_exact:
            continue  # Perfect match

        # Not an exact match — try fuzzy on the full normalised quote
        best_ratio, best_span = _find_best_fuzzy_span(norm_quote, norm_chunk)

        if best_ratio >= _SNAP_THRESHOLD:
            snapped[ev.quote] = best_span
            logger.info(
                "Quote snapped (ratio=%.1f): '%s' → '%s'",
                best_ratio,
                ev.quote[:80],
                best_span[:80],
            )
        else:
            violations.append(
                Violation(
                    type=ViolationType.QUOTE_NOT_VERBATIM,
                    claim_text=claim.text,
                    chunk_id=ev.chunk_id,
                    detail=(
                        f"Quote not found in chunk (best fuzzy ratio={best_ratio:.1f}). "
                        f"Quote: '{ev.quote[:100]}...'"
                    ),
                )
            )

    return violations, snapped


# ---------------------------------------------------------------------------
# 2c. atoms — numbers, dates, money, names, section numbers
# ---------------------------------------------------------------------------


def check_atoms(
    claim: Claim,
    chunks: dict[str, str],
) -> list[Violation]:
    """Check that every atom in claim.text appears in the evidence quotes."""
    violations: list[Violation] = []

    # Combine all evidence quotes
    combined_quotes = " ".join(ev.quote for ev in claim.evidence)
    # Also include chunk text for the evidence chunks
    combined_chunks = " ".join(
        chunks.get(ev.chunk_id, "") for ev in claim.evidence
    )
    combined = combined_quotes + " " + combined_chunks
    norm_combined = normalise_text(combined)

    claim_text = claim.text

    # Numbers
    claim_nums = extract_bare_numbers(claim_text)
    evidence_nums = extract_bare_numbers(norm_combined)
    for num in claim_nums:
        if num not in evidence_nums:
            violations.append(
                Violation(
                    type=ViolationType.NUMBER_MISMATCH,
                    claim_text=claim.text,
                    detail=f"Number '{num}' in claim not found in evidence",
                )
            )

    # Dates
    claim_dates = extract_dates(claim_text)
    evidence_dates = extract_dates(norm_combined)
    for d in claim_dates:
        if d not in evidence_dates:
            violations.append(
                Violation(
                    type=ViolationType.NUMBER_MISMATCH,
                    claim_text=claim.text,
                    detail=f"Date '{d}' in claim not found in evidence",
                )
            )

    # Money
    claim_money = extract_money(claim_text)
    evidence_money = extract_money(norm_combined)
    for m in claim_money:
        if m not in evidence_money:
            violations.append(
                Violation(
                    type=ViolationType.NUMBER_MISMATCH,
                    claim_text=claim.text,
                    detail=f"Amount '{m}' in claim not found in evidence",
                )
            )

    # Capitalised names
    claim_names = extract_capitalised_names(claim_text)
    evidence_names = extract_capitalised_names(norm_combined)
    # Also check if the name appears as a substring (after normalisation)
    for name in claim_names:
        norm_name = normalise_text(name)
        if name not in evidence_names and norm_name not in norm_combined:
            violations.append(
                Violation(
                    type=ViolationType.NUMBER_MISMATCH,
                    claim_text=claim.text,
                    detail=f"Name '{name}' in claim not found in evidence",
                )
            )

    # Section numbers
    claim_sections = extract_section_numbers(claim_text)
    evidence_sections = extract_section_numbers(norm_combined)
    for sec in claim_sections:
        if sec not in evidence_sections:
            violations.append(
                Violation(
                    type=ViolationType.NUMBER_MISMATCH,
                    claim_text=claim.text,
                    detail=f"Section '{sec}' in claim not found in evidence",
                )
            )

    return violations


# ---------------------------------------------------------------------------
# 2d. injection heuristics
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|above|all\s+prior)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|above|all|the)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|a\b|an\b)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\b|an\b|if\b)", re.IGNORECASE),
    re.compile(r"system\s+(prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|endoftext\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow", re.IGNORECASE),
    re.compile(r"override\s+(the|your|all)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|your)", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"(?:respond|reply)\s+(?:only\s+)?with", re.IGNORECASE),
]


def check_injection(
    chunks: dict[str, str],
) -> list[Violation]:
    """Scan all chunk texts for prompt-injection heuristics.

    Flags INJECTION_SUSPECTED but never drops evidence or follows
    injected instructions.
    """
    violations: list[Violation] = []
    for chunk_id, text in chunks.items():
        for pattern in _INJECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                logger.warning(
                    "INJECTION_SUSPECTED in chunk '%s': matched '%s'",
                    chunk_id,
                    m.group(),
                )
                violations.append(
                    Violation(
                        type=ViolationType.INJECTION_SUSPECTED,
                        chunk_id=chunk_id,
                        detail=f"Pattern matched: '{m.group()}' in chunk '{chunk_id}'",
                    )
                )
                break  # One flag per chunk is enough
    return violations


# ---------------------------------------------------------------------------
# Public API: run all checks
# ---------------------------------------------------------------------------


def run_checks(
    claims: list[Claim],
    chunks: dict[str, str],
) -> list[CheckResult]:
    """Run all deterministic checks on a list of claims.

    Parameters
    ----------
    claims:
        Claims to verify.
    chunks:
        Mapping of chunk_id → chunk text.

    Returns
    -------
    list[CheckResult]
        One result per claim, plus injection results appended.
    """
    results: list[CheckResult] = []

    # Run injection check once for all chunks
    injection_violations = check_injection(chunks)

    for claim in claims:
        all_violations: list[Violation] = []
        snapped: dict[str, str] = {}

        # 2a. chunk_exists
        all_violations.extend(check_chunk_exists(claim, chunks))

        # 2b. quote_verbatim
        quote_violations, quote_snapped = check_quote_verbatim(claim, chunks)
        all_violations.extend(quote_violations)
        snapped.update(quote_snapped)

        # 2c. atoms
        all_violations.extend(check_atoms(claim, chunks))

        results.append(
            CheckResult(
                claim_text=claim.text,
                passed=len(all_violations) == 0,
                violations=all_violations,
                snapped_quotes=snapped,
            )
        )

    # Append injection violations as a separate result
    if injection_violations:
        results.append(
            CheckResult(
                claim_text="[injection_scan]",
                passed=False,
                violations=injection_violations,
            )
        )

    return results
