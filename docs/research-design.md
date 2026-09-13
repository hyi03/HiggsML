# Research design

## Physical motivation and scope

The `H -> ZZ* -> 4l` channel connects a reconstructible four-lepton final state to a resonant signal and a continuum background. At a Higgs mass near 125 GeV, at least one Z is off shell. Dilepton masses and angles describe the decay geometry; transverse momentum, rapidity, and individual-lepton observables also reflect production, acceptance, and reconstruction.

The four-lepton invariant mass, `m4l`, already has strong discriminating power. Better classification may reflect mass information, a more convenient representation, or a broader set of observables. The research separates these possibilities before interpreting an inference improvement.

> Within the specified MC population and a fixed mass-conditioned analysis, can additional kinematics improve the expected precision of signal-strength inference, and does the improvement survive finite-MC uncertainty and validated model variations?

Signal strength, `mu`, scales the bound ggH125 signal template. This is an MC-only educational and technical workflow, not an ATLAS/CMS result, a Higgs discovery, or a physics measurement. The initial `mu s + b` model is an on-shell approximation whose interference and background assumptions require an applicability audit. Negative MC weights alone do not establish interference; subtraction and matching can also produce them.

Only the H4l package is maintained. Real data, off-shell width inference, CP/EFT fits, unrestricted architecture searches, legacy15 training, and XGBoost workflows are outside scope. Historical implementations are not active alternatives.

## Questions and primary comparison

| Question | Controlled comparison | Interpretation after validation |
|---|---|---|
| Q1: What is captured by decay coordinates? | Validated matrix elements and an MLP with matched inputs and post-processing | Differences conditional on the physical approximation and learner |
| Q2: Do laboratory variables help? | `decay7` versus `engineered19` with common mass conditioning and physical CDF; a `lab-extension` control | Predictive increment and representation dependence |
| Q3: How does mass treatment affect inference? | Raw, physical/absolute CDF, adversarial training, and matched zero-strength control | Effects of target measure, optimization, calibration, and binning |
| Q4: Are groups complementary or replaceable? | All 15 nonempty A/B/C/D subsets and a matching empty-set baseline | Marginal contributions within the fixed procedure |
| Q5: Does an improvement generalize? | Independent events and documented generator, composition, or detector variations | Robustness within the variations actually tested |

The pilot has one primary comparison: **M5 (`engineered19` with physical CDF) versus M4 (`decay7` with physical CDF), under the same T1 template-statistical model at injected `mu=1`.** Compare the expected 68% Asimov interval width across paired network seeds 42--46. Retain all values and failures. Definitions are in [Methods and evaluation](methods-and-evaluation.md#primary-and-supporting-metrics).

AUC measures ranking on the declared nonnegative evaluation measure and remains useful for training and diagnostics. It does not incorporate the final mass templates, yields, nuisance model, or coverage. Narrower intervals are useful only when bias, coverage, and assumptions are also acceptable.

## Selection rationale

| Choice | Reason and alternative | Cost or limitation |
|---|---|---|
| Controlled MC pilot | Explicit identity and closure studies before broader claims | No demonstration of agreement with real data |
| One primary comparison | Separates hypothesis testing from selecting the best of many results | Auxiliary winners cannot replace it |
| Common `m4l` input | Compares kinematics under the same available mass condition | The classifier is not automatically a conditional likelihood ratio |
| Shared roles, seeds, and templates | Supports fair, paired comparisons | Equal seeds alone do not guarantee event pairing |
| Fixed small MLP | Controlled learner with manageable cost | Input dimension still changes parameter count |
| Physical CDF for the primary pair | Equal post-processing opportunity | Signed calibration and finite statistics need validation |
| T1 interval width | Connects representation quality to signal extraction and finite-template error | The signed-MC approximation requires independent evidence |
| Gates before expansion | Checks support before spending the full budget | Insufficient statistics can stop the study |

These are methodological motivations, not proof of optimality. Exact windows, role fractions, training budgets, and binning are registered defaults. Their original numerical optimization rationale is not established by the existing documentation. Full-MC applicability must be audited without choosing values from assessment outcomes.

## Candidate matrix

| ID | Model or transformation | Input and purpose |
|---|---|---|
| M0 | Mass-only fit | `m4l`, no score category |
| M0c | Mass-only classifier | `m4l`; diagnoses within-bin mass refinement |
| M1 / M1c | Matrix-element score / physical CDF | Kinematic decay7 at fixed mass; independent backend reference required |
| M2 / M4 | Ordinary MLP / physical CDF of M2 | decay7 plus mass, eight inputs |
| M3 / M5 | Ordinary MLP / physical CDF of M3 | engineered19 plus mass, twenty inputs |
| M5-abs | Absolute-weight CDF of M3 | Calibration target changes; templates remain signed |
| M3-fixed200 | Fixed-duration zero-strength control | Matched final epoch, initialization, and data order for M6 |
| M6 | Adversarial MLP | Twenty inputs; strengths 0.05, 0.1, 0.2, 0.5 |
| L1 | lab-extension with physical CDF | decay7, `pt4l`, `y4l`, mass; ten inputs, pilot seed 42 |

M4/M5/M5-abs transform existing outputs without retraining. M1c reuses validated M1 scores. Early-stopped M3 cannot replace the fixed-epoch M6 control. These IDs denote scientific methods, not software milestones. The standard batch covers ordinary models and feature subsets; it does not execute every optional comparison or establish MELA validity.

## Stages and feedback boundaries

| Stage | Deliverable | Advancement condition |
|---|---|---|
| P0 | Process, normalization, historical access, and protocol audit | Provenance and permitted information use documented |
| P1 / G0 | Reconstructed events, group isolation, yields, effective counts | Prepared population passes registered support rules |
| Minimal P2--P4 / G1 | Seed-42 minimum models, calibrations, common templates, T1 evidence | Calibration/template support and statistical model usable |
| Expansion | Remaining seeds, controls, weight bridge, L1, and validated MELA | G1 passed; every new failure retained |
| Frozen evaluation | Bound models, mappings, grid, likelihood, claims, and budgets | No feedback to training, calibration, or design |
| Interpretation | Paired estimates, uncertainty, failures, and limitations | Every claim matches its evidence |
| Extended research | Attribution, sample efficiency, sourced variations | Separate budgets and independent confirmation |

G0 cannot establish two-dimensional template validity before scores exist. G1 uses permitted calibration/template information, not assessment fit results or method rankings. A changed common grid must be registered and rebuilt consistently before assessment. After assessment, revisions are exploratory and require new independent validation; a new protocol name cannot erase feedback.

Preserve historical development/test identity. Repartitioning inspected events or changing random seeds does not restore independence. Audit historical access through existing metadata and decisions without reopening held-out payload. An unused independent batch may suffice; one access marker does not prove that all training MC must be regenerated.

## Sample efficiency and deliverables

The [sample-efficiency study](sample-efficiency.md) narrows Q4 to whether a frozen compact input set retains precision, particularly with less training MC. Its discovery and confirmation are distinct from the pilot M5/M4 comparison. Representation convenience, extra information, and finite-sample learning must be distinguished.

Deliverables include a frozen design, input audits, model/mapping/template/inference lineage, complete paired results and failure tables, independent references, and a manuscript supported by the evidence. Negative and inconclusive results remain legitimate outcomes. No gain is assumed in advance.

## References

These references are retained from the original proposal, not newly reviewed literature. Verify the adopted algorithms, versions, and bibliographic scope before scientific registration or submission.

1. [Avery et al., MEKD](https://arxiv.org/abs/1210.0896).
2. [CMS, H to four-lepton measurements](https://arxiv.org/abs/1706.09936).
3. [Louppe, Kagan, and Cranmer, Learning to Pivot with Adversarial Networks](https://arxiv.org/abs/1611.01046).
4. [Kasieczka and Shih, DisCo](https://arxiv.org/abs/2001.05310).
5. [Windischhofer, Zgubic, and Bortoletto](https://arxiv.org/abs/1907.02098).
6. [Klein and Golling, conditional normalizing flows](https://arxiv.org/abs/2211.02486).
7. [Kitouni et al., MoDe](https://arxiv.org/abs/2010.09745).
8. [JHU generator framework](https://arxiv.org/abs/2002.09888).
9. [Cowan et al., asymptotic likelihood methods](https://arxiv.org/abs/1007.1727).
10. [Datta and Larkoski, How Much Information is in a Jet?](https://arxiv.org/abs/1704.08249).
11. [pyhf likelihood documentation](https://pyhf.readthedocs.io/en/v0.7.6/likelihood.html); the protocol binds the actual modifier and version.
