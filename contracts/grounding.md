# P3 Grounding Contract

## Inputs

| Input | Source | Type |
|-------|--------|------|
| `task` | P2 Synthesis | `str` — the user's question |
| `hits` | P1 Retrieval | `list[Hit]` — retrieved chunks with metadata |
| `corpus` | P1 Retrieval | Normalised full-text corpus for audit |
| `registry` | P1 Retrieval | `data/processed/registry.jsonl` — citation registry |

## Outputs

| Output | Consumer | Type |
|--------|----------|------|
| `claims` | P2 Synthesis | `list[Claim]` — atomic, evidence-backed propositions |
| `violations` | P4 Evaluation | `list[Violation]` — any grounding failures |
| `audit_report` | P4 Evaluation | Exit code + counts from `audit_fabrication.py` |

## Invariants

1. Every `Claim` has at least one `Evidence` with a valid `chunk_id` and verbatim `quote`.
2. Every quote is a substring of the source chunk (after normalisation) or is snapped with logged provenance.
3. Every number, date, money amount, name, and section number in `claim.text` appears in the combined evidence quotes.
4. Every citation-like string resolves to a corpus-backed registry entry.
5. Injection attempts are flagged, never followed.
6. If chunks lack evidence for a claim, return an empty list — never fabricate.

## Acceptance

- 100% of adversarial fixtures are blocked.
- 0% of clean fixtures are blocked.
- `make lint test` exits green.
