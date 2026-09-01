# Professor Report and Manuscript Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a presentation-ready Chinese professor report and a compilable, evidence-bound English LaTeX manuscript draft.

**Architecture:** Both documents draw only on immutable version 1.0 manifests, metrics, plots, and independent review records. The briefing optimizes for oral reporting; the manuscript separates verified results from future-work TODOs and reuses frozen figures by relative path.

**Tech Stack:** XeLaTeX, latexmk, BibTeX, existing PNG artifacts, pytest.

## Global Constraints

- Do not modify or reuse any frozen run path.
- Do not open the ablation held-out test or inspect/score real data.
- Do not invent results or references.
- Preserve all existing user files and changes.

---

### Task 1: Evidence ledger and briefing

**Files:**
- Create: `docs/reports/professor-update-2026-08-12/report.tex`

**Interfaces:**
- Consumes: frozen baseline/training/ablation manifests, Task 8D report and review, roadmap.
- Produces: standalone Chinese XeLaTeX report.

- [ ] Write the report with exact traceable metrics, protocol language, limitations, and next steps.
- [ ] Include only existing frozen plots and label all figures as MC-only.
- [ ] Compile with `latexmk -xelatex -interaction=nonstopmode -halt-on-error report.tex`.

### Task 2: Manuscript draft

**Files:**
- Create: `paper/main.tex`
- Create: `paper/references.bib`

**Interfaces:**
- Consumes: the same evidence ledger and frozen figures.
- Produces: a conventional English manuscript whose Methods and Results are substantially complete.

- [ ] Write evidence-supported Methods and Results.
- [ ] Add bounded Introduction, Discussion, and Conclusion text; mark missing literature/systematics with explicit TODOs.
- [ ] Add verified bibliographic records only and compile with latexmk/XeLaTeX.

### Task 3: Validation and handoff

**Files:**
- Verify: `docs/reports/professor-update-2026-08-12/build/report.pdf`
- Verify: `paper/build/main.pdf`

**Interfaces:**
- Consumes: both LaTeX trees and the unchanged source repository.
- Produces: build logs, PDFs, and a concise remaining-TODO list.

- [ ] Scan LaTeX logs for undefined references, missing files, and fatal errors.
- [ ] Run `.venv/bin/python -m pytest -q` and record the fresh result.
- [ ] Confirm frozen run checksums/inventories were not changed by document generation.

