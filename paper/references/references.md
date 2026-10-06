# Citation verification notes

Edited: 2026-10-06. These notes cover the 13 references used by the current
[LaTeX manuscript](../latex/main.tex). Maintain bibliographic details and citation
keys in [references.bib](../latex/references.bib); this file records their intended
use, verification depth, and limits. Current test05 results and scientific
qualifications are documented in the [evidence index](../result-evidence.md).

## Verification scope

The verification statements below retain the historical checks recorded on
2026-09-14 and supplemented on 2026-09-21. This edit did not repeat external
checks or review full texts. Bibliographic or abstract checks do not establish
the validity of a theorem, an implementation, or its applicability to this study.

- **A:** Bibliographic metadata cross-checked against Crossref or INSPIRE; content
  checked at abstract level where stated. Full-text review remains incomplete.
- **D:** Official dataset or version-specific software documentation. The entry
  states whether the external source was checked or only the repository binding.
- Source-specific limits below take precedence over these general labels.
  Before submission, match each substantive claim to the original text, including
  assumptions, equations, and numerical comparisons.

## References used in the manuscript

### Avery2013 — Four-lepton matrix-element motivation

- **Use:** Introduction and kinematic representation: matrix-element studies
  motivate the discriminating information in four-lepton decay kinematics.
- **Verification:** A; SciSpace abstract and Crossref journal metadata.
- **Limit:** MEKD and MELA are different software packages. This citation does not
  validate this project's angle reconstruction, probability normalization, or
  backend, and does not establish a neural-network advantage over matrix elements.

### CMS2017 — Experimental motivation

- **Use:** Introduction: the four-lepton channel motivates studying signal
  strength and expected interval width.
- **Verification:** A; SciSpace abstract and Crossref metadata. Exact category and
  matrix-element definitions still require full-text review.
- **Limit:** The CMS data analysis is distinct from this ATLAS 2020 MC study,
  its 2e2mu selection, and its normalization. Do not transfer experimental
  yields, systematic uncertainties, or precision to this workflow.

### ATLAS2020 — Controlled MC collection

- **Use:** Dataset source: the 2020 collection, CERN Open Data record 15005.
  The two simulated members are fixed by the
  [dataset contract](../../config/datasets/atlas2020_4lep.json).
- **Verification:** D; official record metadata checked on 2026-09-14 for title,
  DOI, and release year; that check did not read event files.
- **Limit:** The collection does not replace member-specific generator,
  cross-section, or filter-efficiency provenance. The `llll` filename alone does
  not establish a pure qqbar-to-ZZ sample. Keep the 2020 and 2025 releases separate
  and process only the contracted MC members.

### INFERNO2019 — Classification and inference objectives

- **Use:** Introduction: classification loss and parameter-uncertainty objectives
  differ, motivating W68 as the evaluation metric and AUC as a diagnostic.
- **Verification:** A; SciSpace and INSPIRE abstracts, journal, and DOI. Use the
  checked 2019 journal version rather than an inconsistent search-index year.
- **Limit:** This project uses BCE training followed by inference evaluation;
  it does not implement INFERNO or demonstrate superiority to it.

### Cowan2011 — Profile likelihood and Asimov intervals

- **Use:** Profile-likelihood and Asimov definitions; pseudodata experiments
  separately evaluate finite-sample coverage.
- **Verification:** A; Crossref and INSPIRE metadata, abstract, and erratum record.
- **Limit:** Asymptotic formulae do not guarantee coverage at the mu >= 0 boundary,
  in sparse bins, or under signed finite-MC approximations. Asimov widths quantify
  expected precision; they are not measured uncertainties.

### Barlow1993 — Finite-MC template uncertainty

- **Use:** Statistical model: estimated MC templates carry sampling uncertainty.
- **Verification:** A for bibliography; Crossref title, authors, and pages.
  The derivation still requires full-text review.
- **Limit:** The original construction is not identical to this project's signed
  effective-count `shapesys` approximation. Event-group correlations and weight
  cancellation require separate applicability checks.

### pyhf2021 — Statistical software

- **Use:** Implementation and reproduction: pyhf supplies the HistFactory model
  implementation; cite together with the version-specific documentation.
- **Verification:** A; Crossref authors, title, year, volume, and article number.
- **Limit:** The software paper does not validate this model choice, convergence,
  effective-count mapping, or interval coverage.

### pyhf076 — Version-specific likelihood specification

- **Use:** T1 model: `shapesys` Poisson auxiliary constraints and the bound version.
- **Verification:** D for repository binding; the historical review checked the
  link and version against project documentation, but did not reread the external
  page. External specification review remains pending.
- **Limit:** `shapesys`, `staterror`, and `histosys` are distinct modifiers. Input
  applicability and the recorded runtime version require their own evidence.

### Gluesenkamp2018 — Weighted finite-MC uncertainty

- **Use:** Statistical limitations: weighted simulation uncertainty must be
  consistent with the assumed probability model.
- **Verification:** A; SciSpace abstract and Crossref journal metadata.
  Algorithmic applicability still requires full-text review.
- **Limit:** Do not assume all constructions permit arbitrary negative weights or
  correlated event groups. The project's group covariance needs its own
  derivation and validation.

### Mandrik2017 — Negative-weight finite-MC modeling

- **Use:** Weight and T1 limitations: negative weights complicate template
  statistical modeling and effective-count approximations.
- **Verification:** A; SciSpace abstract and Crossref authors, volume, and article.
- **Limit:** Finite-MC uncertainty is distinct from physical generator or detector
  systematic uncertainty. The citation does not validate independent-bin modeling.

### Shapley1953 — Coalition attribution

- **Use:** Shapley weighting of marginal contributions and the efficiency identity.
- **Verification:** A for bibliography; Crossref author, book, year, and pages.
  Formal mathematical statements still require original-text review.
- **Limit:** A/B/C/D, `v(S)=-W68(S)`, retraining, and the constant `M0off`
  inclusive-count empty-coalition reference are this study's definitions.
  Attribution does not establish physical causality or an optimal feature subset.

### Fryer2021 — Attribution and feature selection

- **Use:** Introduction and discussion: Shapley rankings need not identify an
  optimal subset; direct subset comparisons and independent confirmation differ
  from attribution under a fixed value function.
- **Verification:** A; SciSpace abstract and Crossref authors and pages.
- **Limit:** Criticism of Shapley-based selection does not invalidate reporting
  attribution, and the citation does not confirm the selected compact candidates.

### Cawley2010 — Selection bias

- **Use:** Discussion: optimizing a noisy selection criterion can bias subsequent
  performance evaluation.
- **Verification:** A; SciSpace abstract and the official JMLR bibliographic page.
- **Limit:** Renaming or repartitioning previously inspected MC does not restore
  independence. Five training seeds do not provide five independent MC populations.

## Remaining work before submission

1. Audit the two actual DSIDs for generator, shower, parton distribution functions,
   cross-sections, filter efficiencies, and negative-weight provenance before
   selecting generator citations.
2. Match reconstruction conventions and all cited formulas, assumptions, and
   numerical statements to exact full-text locations. Review the signed-MC,
   event-group, and low-support conditions separately from bibliographic checks.
3. Verify the external pyhf 0.7.6 specification and its correspondence to the
   frozen runtime and model. Independent numerical and physical applicability
   validation remain separate requirements.
4. Update literature for the final manuscript claims and check publication
   versions before submission. The historical search was targeted rather than
   exhaustive and cannot establish a first-of-its-kind claim.

MELA, CDF/adversarial comparisons, and sample efficiency remain separate supporting
studies. If added to a future manuscript, they require their own citations,
definitions, and validation. Fewer inputs alone do not establish MC sample savings.
The present manuscript reports exploratory controlled-MC results; citations do not
confer independent scientific qualification or make them an ATLAS/CMS measurement.
