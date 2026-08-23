# Professor Report and Manuscript Design

**Goal:** Produce an evidence-bound Chinese briefing for the 2026-08-12 professor meeting and a compilable English LaTeX manuscript draft from the frozen MC-only version 1.0 artifacts.

## Deliverables

1. `docs/reports/professor-update-2026-08-12/report.tex`: a concise, presentation-ready Chinese report whose first page states the question, result, scientific interpretation, and requested next decision.
2. `paper/main.tex` and `paper/references.bib`: an English paper draft with evidence-supported Methods and Results, plus clearly bounded Introduction, Discussion, and Conclusion sections.
3. PDFs built into local `build/` subdirectories, leaving all frozen run directories unchanged.

## Evidence policy

- Numerical claims must trace to the three immutable run directories, their manifests, the Task 8D report, or the independent Task 8D review.
- The reference model's one-shot independent-test result is distinct from the later feature-ablation gate. The ablation held-out test remained unopened because no profile passed the OOF criteria.
- Real collision data are out of scope. No observed signal claim, significance, measurement, or ATLAS-official result may be stated.
- Unsupported future work is labelled `TODO` in the manuscript and “建议/待验证” in the briefing.
- Existing plots are included by relative path; frozen artifacts are never copied back into or modified within a run directory.

## Structure

The briefing uses an executive-summary-first structure followed by research question, dataset and selection, method, validation/blinding, results, physical interpretation, limitations, and a staged next-step proposal. The manuscript uses conventional Introduction, Data and Event Selection, Method, Validation Protocol, Results, Discussion, and Conclusion sections. Tables distinguish verified facts from proposed work.

## Validation

Compile both documents with XeLaTeX/latexmk, check logs for undefined references and missing files, verify generated PDFs, and run the complete pytest suite to confirm documentation work did not disturb the analysis implementation.

