# LexTrace Demo Script (6 Minutes)

## Setup (0:00 - 1:00)
**Speaker:** "Welcome to the LexTrace demonstration. Today, we're going to draft a regular bail application. Our overarching rule is absolute zero-fabrication. If the system doesn't know it, it cannot invent it."
**Action:** Open the terminal. Run the baseline A0 system and the LexTrace A6 system side-by-side using the `bail_regular` template.

## The Baseline Failure (1:00 - 2:30)
**Input Query:** 
`Draft a regular bail application for John Doe. Ensure the arrest date is explicitly stated.`

**Action:** Show the A0 Baseline output.
**Baseline Expected Output:**
> "...Applicant John Doe was arrested on October 1st, 2023. The FIR 42/2023 was registered under Section 439 of the BNS..."

**Speaker:** "Notice how the baseline cheerfully provided an arrest date of October 1st, 2023. Let's look at the actual source documents. The arrest date is *nowhere* in the bundle. The baseline hallucinated a plausible date to fulfill the prompt."

## LexTrace Intervention (2:30 - 4:00)
**Action:** Run the exact same query through the LexTrace (A6) drafting workflow via `scripts/demo_drafting.py`.

**LexTrace Expected Output:**
> "...Applicant Name: John Doe [1]. FIR Number: FIR 42/2023 [2]. > **Provided by user:** [MISSING: Arrest Date: not found in the provided documents]..."

**Speaker:** "LexTrace’s P3 Zero-Fabrication Gate steps in. Because the claim generator couldn't extract an exact, verbatim quote for the Arrest Date, the verifier blocks the slot. Instead of hallucinating, the Drafting Workflow inserts an explicit `[MISSING: Arrest Date]` placeholder and drops the unverified connective tissue."

## The Adversarial Statute (4:00 - 5:30)
**Action:** We demonstrate the `CitationRegistry` capabilities. We deliberately load a boilerplate template containing a fake, ungrounded statute: `APPLICATION UNDER SECTION 999 OF THE FAKE ACT.`

**Speaker:** "Even our boilerplate templates are subjected to the strict citation registry. If a lawyer accidentally leaves a reference to a statute that isn't in our verified corpus, LexTrace will strip it."

**Action:** Show the LexTrace output. The header sentence `APPLICATION UNDER SECTION 999 OF THE FAKE ACT.` is entirely missing.
**Speaker:** "The CitationRegistry scanned the sentence, realized the statute wasn't in our active jurisdiction or corpus, and the gate deleted the sentence to protect the user."

## Conclusion & Audit (5:30 - 6:00)
**Action:** Run `python scripts/audit_fabrication.py draft_output.md`.
**Expected Output:** `Exit Code 0`

**Speaker:** "Finally, we run our independent audit script against LexTrace's generated output. It returns Exit Code 0, confirming every single citation maps perfectly to an unaltered verbatim quote. Thank you."
