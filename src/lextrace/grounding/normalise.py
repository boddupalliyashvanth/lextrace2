"""Shared normalisation utilities for the grounding subsystem.

All text normalisation used by checks, citation registry, and the audit script
is defined here so behaviour is consistent, but the audit script re-implements
its own copy for independence.
"""

from __future__ import annotations

# ruff: noqa: RUF003
import re
import unicodedata

# ---------------------------------------------------------------------------
# Core text normalisation
# ---------------------------------------------------------------------------

# Quotes → ASCII equivalents
_QUOTE_MAP = str.maketrans({
    "\u2018": "'",   # '
    "\u2019": "'",   # '
    "\u201a": "'",   # ‚
    "\u201b": "'",   # ‛
    "\u201c": '"',   # "
    "\u201d": '"',   # "
    "\u201e": '"',   # „
    "\u201f": '"',   # ‟
    "\u00ab": '"',   # «
    "\u00bb": '"',   # »
    "\u2039": "'",   # ‹
    "\u203a": "'",   # ›
})

# Dashes → ASCII hyphen
_DASH_MAP = str.maketrans({
    "\u2013": "-",   # –  en-dash
    "\u2014": "-",   # —  em-dash
    "\u2015": "-",   # ―  horizontal bar
    "\u2012": "-",   # ‒  figure dash
    "\u2010": "-",   # ‐  hyphen
    "\u2011": "-",   # ‑  non-breaking hyphen
    "\ufe58": "-",   # ﹘ small em dash
    "\ufe63": "-",   # ﹣ small hyphen-minus
    "\uff0d": "-",   # － fullwidth hyphen-minus
})


def normalise_text(text: str) -> str:
    """Apply the full normalisation pipeline to *text*.

    Steps:
    1. Unicode NFKC
    2. Unify quote characters
    3. Unify dash characters
    4. Remove soft hyphens (U+00AD)
    5. Remove line-break hyphenation (hyphen + newline → join)
    6. Collapse whitespace
    """
    # 1. NFKC
    text = unicodedata.normalize("NFKC", text)
    # 2. Quotes
    text = text.translate(_QUOTE_MAP)
    # 3. Dashes
    text = text.translate(_DASH_MAP)
    # 4. Soft hyphens
    text = text.replace("\u00ad", "")
    # 5. Line-break hyphenation: hyphen at end of line followed by newline
    text = re.sub(r"-\s*\n\s*", "", text)
    # 6. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Number normalisation (including Indian notation)
# ---------------------------------------------------------------------------

# Indian comma notation: 1,00,000 → 100000
_INDIAN_NUM_RE = re.compile(
    r"\b(\d{1,2}(?:,\d{2})*,\d{3})\b"
)
# Western comma notation: 1,000,000
_WESTERN_NUM_RE = re.compile(
    r"\b(\d{1,3}(?:,\d{3})+)\b"
)


def normalise_number(s: str) -> str:
    """Strip commas from a numeric string.  '1,00,000' → '100000'."""
    return s.replace(",", "")


def extract_bare_numbers(text: str) -> set[str]:
    """Extract all plain numbers (digits with optional commas and decimals)
    from *text*, returning their normalised (comma-stripped) forms."""
    results: set[str] = set()
    for m in re.finditer(r"\b[\d,]+(?:\.\d+)?\b", text):
        token = m.group()
        # Must contain at least one digit
        if not any(c.isdigit() for c in token):
            continue
        results.add(normalise_number(token))
    return results


# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------

_MONTH_NAMES: dict[str, str] = {
    "january": "01", "february": "02", "march": "03",
    "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "sept": "09", "oct": "10", "nov": "11", "dec": "12",
}

# dd/mm/yyyy or dd-mm-yyyy or dd.mm.yyyy
_DATE_DMY = re.compile(
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"
)

# Month dd, yyyy  or  dd Month yyyy
_DATE_NAMED = re.compile(
    r"\b(?:(\d{1,2})\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\.?\s+(\d{1,2})?[,\s]*(\d{4})\b",
    re.IGNORECASE,
)


def _canon_date(day: str, month: str, year: str) -> str:
    """Return canonical dd-mm-yyyy."""
    return f"{int(day):02d}-{int(month):02d}-{year}"


def extract_dates(text: str) -> set[str]:
    """Extract dates from *text* and return them in canonical dd-mm-yyyy form."""
    results: set[str] = set()
    for m in _DATE_DMY.finditer(text):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        results.add(_canon_date(d, mo, y))
    for m in _DATE_NAMED.finditer(text):
        pre_day = m.group(1)
        month_name = m.group(2).lower().rstrip(".")
        post_day = m.group(3)
        year = m.group(4)
        day = pre_day or post_day
        if day and month_name in _MONTH_NAMES:
            results.add(_canon_date(day, _MONTH_NAMES[month_name], year))
    return results


# ---------------------------------------------------------------------------
# Money amount extraction
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(
    r"(?:Rs\.?|INR|₹|\$|USD|EUR|€|£|GBP)\s*([\d,]+(?:\.\d+)?)"
    r"|"
    r"([\d,]+(?:\.\d+)?)\s*(?:rupees|dollars|euros|pounds)",
    re.IGNORECASE,
)


def extract_money(text: str) -> set[str]:
    """Extract money amounts as normalised numeric strings."""
    results: set[str] = set()
    for m in _MONEY_RE.finditer(text):
        raw = m.group(1) or m.group(2)
        if raw:
            results.add(normalise_number(raw))
    return results


# ---------------------------------------------------------------------------
# Capitalised names
# ---------------------------------------------------------------------------

_CAP_NAME_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9_]*(?:\s+(?:of|the|v\.|vs\.?|versus|and)\s+[A-Z][a-zA-Z0-9_]*|\s+[A-Z][a-zA-Z0-9_]*)+)\b"
)


def extract_capitalised_names(text: str) -> set[str]:
    """Extract sequences of two or more capitalised words."""
    return {m.group(0) for m in _CAP_NAME_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Section numbers
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"(?:Section|Sec\.|s\.|u/s|Article)\s*(\d+[A-Za-z]?)",
    re.IGNORECASE,
)


def extract_section_numbers(text: str) -> set[str]:
    """Extract section/article numbers from legal text."""
    return {m.group(1) for m in _SECTION_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Ellipsis splitting for quote verification
# ---------------------------------------------------------------------------

def split_on_ellipsis(text: str) -> list[str]:
    """Split a quote on ellipsis markers (… or ...) and strip each segment."""
    parts = re.split(r"\.{3}|\u2026", text)
    return [p.strip() for p in parts if p.strip()]
