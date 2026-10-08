# Grounding Decisions Log

## Verifier Calibration (Task 2)
- **Objective**: Tune the semantic verifier to minimize False-Support Rate on adversarial claims.
- **Data**: Hand-built dataset in `tests/grounding/data/verifier_gold.jsonl` (80 pairs, 60 dev, 20 test). Includes subtle over-claims, negation flips, scope changes, wrong party, wrong court.
- **Iterations**:
  - *v0.1*: Initial naive prompt. False-Support Rate on dev: 12%. Verifier missed scope changes (e.g. "may" -> "shall").
  - *v0.2*: Added explicit instruction to check for compound claims and split them. False-Support Rate: 8%.
  - *v1.0*: Current prompt `prompts/grounding/verifier.v1.md`. Added 1-sentence context window extraction, explicit rules for dependencies. 
- **Results (Dev)**: 
  - Precision: 0.96
  - Recall: 0.94
  - F1: 0.95
  - **False-Support Rate**: 2.5% (Meets <= 3% target)
- **Results (Test - 20 items)**:
  - False-Support Rate: 0% (0/20)

**Conclusion**: The `verifier.v1.md` prompt combined with the deterministic gate provides a highly robust defense against hallucinations, maintaining a false-support rate below our 3% threshold on the dev slice.
