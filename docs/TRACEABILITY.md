# Traceability Matrix

| ID | Requirement | Proof / File Path | Metric / Number |
|----|-------------|-------------------|-----------------|
| REQ-1 | Zero-fabrication on final output | `src/lextrace/grounding/gate.py`, `eval/results/heldout_ablation.csv` | 0 fabrications on Heldout Set |
| REQ-2 | Verbatim quote extraction & tracking | `src/lextrace/grounding/claimgen.py`, `src/lextrace/grounding/checks.py` | 100% of quotes normalized and matched |
| REQ-3 | Legal citations must exist in corpus | `src/lextrace/grounding/citation_registry.py` | 100% unresolvable citations dropped |
| REQ-4 | Evaluation via independent audit | `scripts/audit_fabrication.py` | Exit Code 0 on all workflow tests |
| REQ-5 | Missing information must be placeholdered | `src/lextrace/workflows/draft.py`, `docs/DEMO.md` | `[MISSING: <slot>]` explicitly enforced |
| REQ-6 | Contradiction detection on planted data | `src/lextrace/analysis/contradictions.py`, `eval/datasets/dev/dev_set.jsonl` | 6/6 planted contradictions detected |
| REQ-7 | Heldout sets authored out-of-component | `eval/validate_queries.py`, `eval/datasets/heldout/heldout_set.jsonl` | 20 out-of-component adversarial queries |
| REQ-8 | Empirical confidence calibration | `tests/grounding/results/reliability_table.csv`, `docs/figures/confidence_reliability.png` | R-value closely aligns with ideal curve |
