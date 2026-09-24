# Results and limitations

## Active off-only study

The retained `h4l-off-test01` analysis evaluates all 15 nonempty A/B/C/D subsets for five training seeds with explicit `m4l` omitted from the classifier and retained in the likelihood. Five deterministic `M0off` identities provide the empty set. The nominal five-seed result is complete; uncertainty and qualification are incomplete.

## Evidence summary

The paper explicitly selects the archived report `var/runs-test-01/h4l-off-test01-old1/evaluation/report`, artifact `3fe3e15ffe27f8480719deaa2a84a201d6a5062ca2611b0c5f67d62f54d23e05`, executed at `3819547357354aa04fa2dd85e1da3afeeaeb8ffb`. On **2026-09-23**, all 14 original aggregate sources and enclosing manifest hashes matched the supplied archive. Asimov/freeze execution is separately `65a9d24f1f6ef0478669f3f0969fed0837938f61`. Publication is complete, aggregate status is incomplete and primary claim eligibility is false. The [version matrix](../paper/result-evidence.md) separates this result from the superseded Chinese recovery report and unfinished active test03 computation.

The run supports an exploratory conclusion about the fixed controlled-MC procedure. It does not support a publication-ready physics result, reliable total uncertainty, external generalization, or an ATLAS/CMS measurement. The default core protocol still declares `synthetic_software_defaults_not_physics_validation`; the actual run adds bound controlled-MC evidence without silently changing that protocol scope.

## `h4l-off-test01` controlled-MC result

`W68` is the nominal T1 Asimov 68% interval width at injected `mu=1`; smaller is better. The table reports medians over seeds 42–46. The range is the observed five-seed range, and the improvement is computed against the same-seed deterministic `M0off` before taking the median.

| Subset | Median `W68` | Five-seed range | Median improvement vs `M0off` | Median validation AUC |
|---|---:|---:|---:|---:|
| `M0off` | 1.66372 | fixed | 0 | unavailable |
| **BC** | **1.51162** | 1.51060–1.51960 | **9.14%** | 0.81314 |
| **AC** | **1.51524** | 1.49720–1.51785 | **8.92%** | **0.87754** |
| ABC | 1.52116 | 1.51531–1.53042 | 8.57% | 0.86172 |
| BCD | 1.52446 | 1.51020–1.52838 | 8.37% | 0.82831 |
| ABCD | 1.53593 | 1.52947–1.54805 | 7.68% | 0.84635 |
| B | 1.56019 | 1.55510–1.56718 | 6.22% | 0.75781 |

BC improves on ABCD in all five same-seed comparisons, with a median relative improvement of 1.299%. AC also wins all five, with a median improvement of 1.425%. AC versus BC is unresolved: AC wins 2/5 seeds and has a median width 0.00188 larger than BC. Per-seed winners are AC for seeds 42 and 46, BC for 43 and 44, and BCD for 45. “BC is best” therefore refers only to the median ranking.

The AUC ordering differs from the inference ordering. AC has the highest median AUC, BC the narrowest median `W68`, and ABCD has higher AUC than BC but a wider interval. AUC is a validation ranking diagnostic and cannot substitute for the final likelihood metric.

### Feature attribution and interactions

Shapley values use `v(S)=-W68(S)` and have interval-width units. The quoted 95% ranges enumerate the five observed training seeds; they are stability ranges, not confidence intervals.

| Group | Features | Median Shapley | Five-seed 95% stability range |
|---|---|---:|---:|
| B | `mZ1`, `mZ2`, `deltaR_Z1`, `deltaR_Z2` | **+0.06222** | [0.04852, 0.06894] |
| C | `pt4l`, `deltaPhi_ZZ` | **+0.06094** | [0.05421, 0.06368] |
| A | four lepton `pt` and `eta` values | +0.01502 | [0.01024, 0.01902] |
| D | Angular5 | **−0.01110** | [−0.01600, −0.00180] |

The procedure-specific ordering is `B ≈ C >> A > D`. D is negative in every seed. The unconditional AC second difference has median +0.04246 and is positive in all seeds; AB has median −0.05344 and is negative in all seeds. These quantities describe complementarity in this learner/template metric. They are not mutual information, causal synergy, or intrinsic physical information.

### Coverage diagnostics and incomplete uncertainty

All 15 assessment cells completed: 500 Toys × 16 candidates × 15 cells produced 120,000 completed fits with no recorded fit failures. All five T2 cells completed: 20 outer replicas × 100 inner Toys × 16 candidates × 5 seeds produced 160,000 completed fits with no recorded fit failures.

| Subset | Assessment coverage 68% / 95% | T2 coverage 68% / 95% |
|---|---:|---:|
| BC | 0.668 / 0.960 | 0.666 / 0.9535 |
| AC | 0.634 / 0.966 | 0.648 / 0.9645 |
| ABCD | 0.634 / 0.970 | 0.650 / 0.9650 |

These are conditional diagnostics under `marginal_common_total_monotone_crn`, with `physical_event_pairing=false`. The 68% values suggest mild undercoverage for the displayed candidates, while the 95% values are near or slightly above nominal. At `mu=0`, the physical `mu >= 0` boundary makes coverage conservative. None of these statements qualifies unconditional or externally validated coverage.

The event-MC bootstrap completed only 161/200 replicas. Thirty-nine replicas failed with `insufficient_statistics`, so the report correctly leaves every formal bootstrap percentile interval empty. Forty-nine candidate failures occurred across those replicas: D-only seed 42 accounts for 37, D-only seeds 43 and 44 for five and four, and seed-46 AC/ACD for the remaining three. This makes D's finite-MC support particularly fragile.

All 15 model-self cells in the selected archived report are valid. The earlier recovery report recorded three budget-blocked cells; that different report is preserved in the historical evidence index. Independent-allocation sensitivity is pending. The access receipt is a `single_researcher_self_review` with `independent=false`; independent P0 physical definitions, a signed-MC T1 applicability reference, and assessment-history review remain missing. These gaps determine the report's `incomplete` status.

## Historical exploratory observations

The earlier sample-efficiency proposal recorded a five-seed subset report in which AB had median W68 approximately 1.49184 and ABCD approximately 1.50080, with a median paired reduction near 0.60%. These numbers are retained only as an attributed historical observation from the superseded proposal, not as a newly verified result. The documentation did not identify a sufficient immutable run/receipt reference for independently replaying them here; they are excluded from the conclusions and must not set a tolerance or candidate automatically.

That report was described as `scientific_results_obtained=false`, with a synthetic-software-default protocol scope. AB was selected after examining the same fifteen-combination family, the ranking was primarily relative to M0c rather than a frozen AB/ABCD noninferiority test, and complete selection/event/calibration uncertainty and a training-size experiment were absent. Independent confirmation and authority evidence were not completed.

| Research question | Evidence status | Supported interpretation |
|---|---|---|
| Do engineered inputs improve M5/M4 precision? | Method and reporting available; qualified full-MC primary comparison not documented | An executable hypothesis, not a confirmed gain |
| How do off-only subsets compare? | Complete five-seed nominal controlled-MC vectors; assessment/T2 diagnostics complete; bootstrap and independent qualification incomplete | BC/AC advantages and `B ≈ C >> A > D` are exploratory findings for this fixed procedure |
| How much does explicit `m4l` add within each feature subset? | Paired training, mass-slice diagnostics, T1 comparison, and exports implemented | The active result is off-only; it does not by itself quantify the on/off mass increment |
| Is a compact subset noninferior? | Historical exploratory candidate observation | Motivation for a registered independent test |
| Does compactness reduce training-MC requirements? | Workflow exists; formal registered experiment pending | No established sample-saving factor |
| Are intervals reliable under signed MC and variations? | Software/synthetic checks exist; independent and full-MC scope incomplete | No general coverage or physical-systematics conclusion |
| Is a matrix-element baseline validated? | Interface and internal transformations tested | No independent M1/M1c physics result |

## Software and validation status

The following consolidates the inherited status document. It is a dated record, not a promise that all tests pass on every subsequent checkout.

| Capability | Recorded software state | Remaining evidence boundary |
|---|---|---|
| Controlled acquisition and dataset contracts | Implemented and bound in the retained prepared artifact | Release equivalence and independent source authority are not established |
| Selection, reconstruction, Angular5, features, and weights | Non-assessment role counts recorded in the selected prepared audit | Independent physical-definition and source-access audits remain incomplete |
| Five-role physical-group isolation | Bound population and role counts recorded; G0 passed | Does not replace history audit or ROOT interpretation validation |
| Mass-only, decay7, engineered19, lab-extension | Implemented | Interpretation depends on shared mass/input scope |
| Grouped M3 off-only attribution | Five-seed nominal controlled-MC result, exact attribution and pair tables recorded | Bootstrap incomplete; independent qualification pending; off models can retain implicit mass information |
| Ordinary/adversarial training and history | Implemented | Diagnostics do not prove convergence or generalization |
| MELA export/import and adapter | Implemented interface | Actual backend and independent physical reference pending |
| CDF, common templates, pyhf inference | Implemented | Signed-MC T1 approximation requires independent evidence |
| G0/G1, freeze, assessment, report | Implemented | No documented publication-ready frozen full-MC result |
| Enhanced exports | Recorded synthetic and existing-MC-artifact replay checks | AUC remains selected-checkpoint validation AUC |
| Registered evaluation orchestration | Controlled-MC assessment and T2 cells completed | Bootstrap incomplete; model-self 15/15 numerically valid; sensitivity pending |
| Current within-seed marginal CRN evaluation | 36-unit controlled-MC report published | Artificial CRN is not physical-event pairing; independent P0/T1/history review remains missing |
| Independent evidence import | Receipt/type guards implemented | Missing materials remain `external_pending` |
| Sample-efficiency subsets, batch, report, controls, confirmation | Implemented with synthetic tests | Registration values and independent/full-MC evidence pending |
| Cross-platform compatibility | Not comprehensively run in the recorded change | The recorded platform only establishes behavior on that environment |

### Dated software checks

| Record | Reported result | Interpretation |
|---|---|---|
| 2026-09-23 F4/F11/F12 final verification | Windows Python 3.12.13: 596 passed, 5 skipped, 511 deprecation warnings, 922.92 s; short temporary root | Final software/synthetic suite for this working-tree change; not independent numerical or scientific validation. [Record](changes/evidence-alignment-20260923.md) |
| 2026-09-13 enhanced-report/status update | Focused 39 passed; Windows full suite 416 passed / 34 failed | The source record attributes failures to existing scientific-resource seals and training-history contract inconsistency; no resources were re-signed. This rewrite has not independently reproduced the diagnosis. |
| 2026-09-11 performance implementation | Windows 532 passed, 60 warnings, 332.74 s; dependency check and diff check passed | A historical checkout/test inventory, not the latest suite result |

The performance record attributed warnings to pyhf/jsonschema deprecations and a TestOpeningResult collection warning and reported eighteen new parameterized performance cases. Different dates and inventories cannot be combined into one current passing count. Current verification commands and paths are in the [runbook](implementation-and-reproduction.md#verification-commands-and-evidence-levels).

The adapter record reports twenty synthetic angular round-trip, mass-shell, and total-momentum tests and fake-module call checks. They establish internal transformation/API consistency only; no actual MELA execution, independent probability reference, or production-process equivalence follows from them.

## Historical performance evidence

The retained performance campaign is dated **2026-09-11**, against Git baseline `66784d3af0a4b73c6001acc94404da3540040866`. Its original raw record is [performance-synthetic-results.json](performance-synthetic-results.json), retained byte-for-byte. The record contains platform/Python/package versions, implementation file hashes, resource settings, repetitions, RSS samples, and equality checks. Historical module names in that record are evidence metadata, not current import instructions.

| Synthetic workload | Approximate median baseline / optimized time | Reported consistency |
|---|---:|---|
| 1,000-entry scalar/jagged ROOT reader | 5.2x | Event contents and order matched |
| 200,000-event CDF interpolation | 12.5x | Within declared tolerance |
| 14,000-row calibration fit | 1.27x | Complete payload digest matched |
| Two-candidate common mass grid | 2.7x | Payload digest and merge history matched |
| Three single-bin Asimov cases | 1.16x | Payload matched; unconditional MLE calls 6 to 3 |
| 72-row M6, full 200 epochs | 1.20x | Model, history, checkpoint, and selected epoch matched |

Three repetitions were compared using medians; scientific comparisons used predeclared `rtol=atol=1e-12`, with exact discrete decisions. Repetition was within a process and did not flush the OS cache. Initial import/allocation can affect the first run. RSS sampled every 10 ms includes retained allocations and is not an isolated operation's exact peak. Small fitting gains may be comparable to timing variation. ROOT throughput excluded the complete physics-selection/feature pipeline. These numbers are not production end-to-end speedups.

The optimization sequence covered instrumentation, legal ROOT spans, calibration/training caching, grouped statistics and incremental merging, shared MLE, bounded inference parallelism, and streaming/local identity caches. Current mechanisms and non-enabled proposals are consolidated in [Performance implementation](implementation-and-reproduction.md#performance-implementation).

### Source-access limitation

The historical uproot 5.7.5 review inspected `AsDtype.basket_array`, `Numerical.final_array`, and `AsJagged`, and ran a synthetic mixed-basket probe. A request returning one entry could involve a basket-wide numerical view during interpretation; final slicing occurred later. Jagged offsets and header-bearing buffers also require inspection.

Consequently, an application request that excludes held-out entry indices is insufficient evidence that every bound branch satisfies a strict no-held-out-interpretation contract. The issue also applied to the earlier per-entry baseline. Neither version is certified by this throughput result. Controlled-MC stage-B access acceptance remained incomplete and requires a separate bound-source interpretation audit before production performance experiments. This finding does not authorize reading restricted payload to investigate it.

### Acceptance criteria for future performance work

Preserve event order, identities, participant order, role assignment, random inputs, merge histories, and states exactly. Compare numerical values at predeclared tolerances, especially cancellation, thresholds, and interval boundaries. Compare payload digests separately from approximate numerical agreement; new software/environment metadata can change a full manifest without implying identical artifacts.

Record wall/CPU time, RSS, input scale, ROOT request counts/span distribution, statistical reconstruction counts, MLE/root-search calls, workers/threads, and software versions. Separate prepare identity/payload/selection/feature/write timings. Use a fixed independent oracle or baseline and tests for alternating/no/all eligible entries, repeated groups, zero occupancy versus cancellation, cross-bin covariance, failed intervals, out-of-order workers, exceptions, and receipt mismatches. Representative end-to-end gains must exceed noise and respect memory/access limits before default adoption. Record each tested operating system and CPU architecture without assigning authority to one platform.

## Evidence required for conclusions

| Evidence level | What it can establish | What it cannot replace |
|---|---|---|
| Code review and software tests | Contracts, guards, algorithm implementation, determinism | Full-MC physical applicability |
| Synthetic numerical validation | Closure and failure semantics on known constructions | Actual sample support and systematics |
| Controlled-MC G0/G1 | Bound source, support, calibration, and template gates | Frozen assessment or external generalization |
| Frozen MC inference/assessment | Registered-population precision, bias, and coverage | Independent MELA, cross-release equivalence, or platform replay |
| Independent reference/variation | Numerical or physical robustness in declared scope | Other missing scientific evidence |
| Cross-platform compatibility check | Reproduction on the explicitly recorded environment | Physical validity or universal portability |

| Proposed claim | Minimum required evidence |
|---|---|
| Event/role independence | Source audit, prepared receipts, group non-overlap, historical-use review |
| Additional discriminating power | Complete paired planned models on common inputs/populations, validation and mass-slice diagnostics |
| Explicit-mass contribution | All 15 independently trained on/off pairs for all five seeds, valid local slice support, common-grid T1 widths, retained failures, and bound lineage |
| Off-only subset precision ordering | Complete five-seed nominal vectors, formal finite-MC uncertainty, qualified T1 model, independent access/history review, and acceptable coverage diagnostics |
| Controlled mass sculpting | Independent mapping, acceptance diagnostics, common templates, frozen criteria |
| Expected mu-precision improvement | Valid T1 primary M5/M4 comparison across five paired seeds, W68 and failures |
| Reliable intervals | Registered injections/budgets, bias and coverage with binomial/paired uncertainty, boundary/failure accounting |
| Compact noninferiority/sample efficiency | Frozen candidate/tolerance, complete batch and controls, independent confirmation; actual size curves for efficiency claims |
| Physical robustness | Sourced variations, process/response/correlation definitions, independent references |

Formal result provenance includes dataset, prepared population, protocol digest, code/dirty state/environment, representation, feature subset, explicit-mass flag and ordered inputs, seed/checkpoint/model ID, mapping ID, common mass edges, template/workspace ID, inference layer, injected mu, interval, failures, comparison-family/cohort IDs, and all direct receipts. Toys additionally need freeze/claim, parent source, pairing ID, seed, budget, auxiliary-generation rule, and coverage/boundary/failure counts. Sample efficiency adds fraction/draw/full, actual train groups, subset/cell identities, multiplicity plan, and paired-bootstrap provenance.

## Interpretation limits and completion order

An observed narrower Asimov interval alone does not establish reliable coverage. AUC gains do not prove improved inference; subset gains do not prove new independent physical information or a sufficient statistic. Five seeds do not capture all MC uncertainty. Artificial stress is not a measured detector or theory systematic. More Toys or bootstrap replicas cannot create unsupported tails or recover independent information from inspected events.

When there is no significant gain, report the difference interval and the gain range that can be excluded, not information saturation. Missing MELA, insufficient templates, unvalidated statistical models, and fit failures are legitimate recorded limitations, not completed physics arguments.

The prepared population, G0/G1, off-only freeze, nominal five-seed vectors,
assessment cells and T2 cells already exist and must remain immutable. Complete
the outstanding scientific work in this order:

1. Obtain independent process, reconstruction, normalization, source-access and historical-use review for the bound population.
2. Obtain an independent signed-MC T1 applicability reference; keep MELA separate unless a matrix-element claim is made.
3. Resolve the failed event-MC bootstrap support through a prospectively registered analysis or population change, without tuning from the observed failures or filling missing replicas.
4. Run the registered independent-allocation sensitivity and any sourced robustness studies required by the intended claim.
5. Repeat the frozen assessment on a genuinely eligible independent source if a primary claim is sought; the existing self-review cannot be upgraded retrospectively.
6. Complete compact discovery/controls and independent confirmation; execute size curves before claiming sample efficiency.
7. Generate manuscript figures and tables with evidence labels that distinguish the current exploratory result from any later qualified result.

Expected figures include the role/analysis flow, epoch diagnostics and matched control, raw/CDF acceptance versus mass, paired T1 widths, injection-wise bias/coverage/failures, and qualified sample-efficiency curves. Schematic figures must be labelled as such. Missing experiments cannot be replaced with illustrative numerical results.

## Documentation consolidation record

The English rewrite merged the former topic documents as follows. These are historical source names, not active paths.

| Former document / content | Maintained destination |
|---|---|
| research-project: motivation, Q1--Q5, candidates, stages, references | [Research design](research-design.md) |
| research-project: source roles, input information, physical normalization | [Data and processing](data-and-processing.md) |
| research-project: training, CDF, inference, attribution, variations | [Methods and evaluation](methods-and-evaluation.md) |
| research-project: implementation, risks, delivery/evidence boundaries | [Implementation](implementation-and-reproduction.md) and this document |
| mu-inference-objective | Research rationale plus methods/metrics |
| data-preparation | Data and processing; operational/receipt details in implementation |
| mass-decorrelation | Methods and evaluation |
| architecture, software-design, software-requirements | Tools/architecture, preserved requirement IDs, artifact contracts |
| sample-efficiency | [Sample efficiency](sample-efficiency.md), with observations moved here |
| runbook, artifact-schema, mela-adapter | Implementation and reproduction; study-specific contracts in sample efficiency |
| current-status, evidence-and-completion | Dated status, claim requirements, and completion boundaries here |
| performance-design, performance-implementation | Current mechanism/contract description in implementation; dated measurements and limitations here |
| performance-synthetic-results.json | Unmodified raw evidence at the document root |

Superseded development intentions are not presented as current missing implementations. Obsolete legacy compatibility plans are omitted because that code is outside the active repository scope; source-history and feedback constraints remain. Unbound illustrative event-count arithmetic is omitted from scientific results. The rewrite preserves scientific meaning rather than preserving contradictory historical wording.

## Off-only applicability and evidence checklist

| Item | Available basis | Current limit |
|---|---|---|
| Kinematic attribution | Existing representations and exact Shapley/second-difference definitions; the Datta–Larkoski representation study is related motivation | Applying Shapley alone does not establish methodological novelty; no claim of a sufficient statistic or causal information decomposition |
| Signal-strength likelihood | Existing Cowan likelihood reference and pinned pyhf shapesys model | Signed-weight cancellation, low counts and group covariance require independent numerical/applicability review |
| Finite training variability | Five fixed checkpoints and complete joint seed-vector enumeration | Conditional on the current MC; no retraining uncertainty beyond these seeds |
| Event-MC and calibration variability | `h4l-off-test01` attempted all 200 bootstrap replicas and completed all five 20-by-100 T2 cells | Bootstrap has only 161 valid replicas; T2 is conditional on artificial CRN and non-independent access |
| MELA and sample efficiency | Existing optional repository studies | Neither is required for the six off-only outputs; no superiority-to-ME or training-sample-saving claim |
| Historical access | Prepared audit metadata and original-root claim inspection | Absence of a local claim is not proof of independent historical use; reviewed access evidence remains required |

These comparisons use the already documented literature references and do not represent a new literature search. Parameter choices (mass window, luminosity, minimum effective count, cancellation threshold, learner and pilot budgets) remain the bound core protocol defaults; no claim of optimization or independent physical validation is made. Current code-development verification is recorded separately from historical test counts in the Sprint review evidence.

On 2026-09-14, the isolated implementation first completed a controlled-MC A/B replay using 75 existing off checkpoints and five deterministic M0off identities. That historical `runs/m4l-off-003/report-B` artifact stopped before C–E evaluation; its delivery and replay receipts remain in [delivery evidence](4-Reviews/sprint-m4-01-delivery.md) and [MC replay receipts](4-Reviews/sprint-m4-01-mc-stage-b.md).

The later retained `h4l-off-test01` run continued the scientific matrix under the current marginal CRN contract. It completed the assessment and T2 cells, attempted the event-MC bootstrap, and published the result summarized above. This later execution supersedes the older replay's “not run” status, while retaining the older artifact as historical evidence. It does not repair missing independence or the incomplete bootstrap.

The active workflow uses pre-freeze J0/J1 support gates, claim-aware terminal publication, and a 37-unit report sequence. Historical v1/v2/v3 fields remain for artifact identity and compatibility; the current command-line workflow does not expose them as scientific alternatives. Software/synthetic checks, the older A/B replay, and the current controlled-MC execution remain distinct evidence records.

### Default marginal CRN evidence boundary

The default workflow uses marginal common-total CRN coupling. Its paired errors are
conditional diagnostics, not physical-event covariance. Independent-allocation
sensitivity remains pending unless the report contains completed bound evidence.
Template-only J0/J1 engineering qualification, assessment execution and
independent scientific validation are distinct gates. `h4l-off-test01` completed
assessment under a non-independent self-review, so its diagnostics remain
exploratory. Changing the workflow or run name does not reset source usage history.

See [F4/F11/F12 verification](changes/evidence-alignment-20260923.md) for current software checks, archive restoration and build boundaries. The unfinished computation under `runs/` is separate from the selected archived test01.
