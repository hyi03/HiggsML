# Results and limitations

## Active off-only study

The active paper objective is to quantify the contribution, complementarity and training-seed stability of A/B/C/D kinematic groups when the classifier omits explicit `m4l`. The likelihood still uses the registered mass window and mass coordinate. The 15 nonempty combinations use seeds 42–46 and their existing checkpoints; five deterministic `M0off` identities supply the same-family empty set. No model is retrained for this analysis.

The six result areas are all off-only: paired W68; complete subset ranking/stability; exact Shapley and 24 conditional interactions; validation-checkpoint AUC versus W68; BC/AC versus ABCD as exploration-selected comparisons pending frozen validation; and all 105 direct subset pairs. AUC is descriptive, not an inference or coverage qualification. Older physical-CDF M5/M4, explicit-mass controls, MELA and sample-efficiency workflows remain compatible background/extension studies and are not required off-family candidates.

The versioned [definition](../config/protocols/feature_attribution_mass_off_v1.json) is not a completed scientific registration. A new immutable registration run binds the actual core protocol, prepared population and 75 audited model/calibration artifacts. The candidate family has its own 80-identity G1 and freeze; freezing does not grant assessment access. Automatic P0/T1 materials remain software evidence, with independent qualification pending. Actual uncertainty and coverage stages are separate evidence levels; no operating system or CPU architecture is an authority requirement.

## Evidence summary

The retained status record is dated **2026-09-13**. It describes an implemented MC-only educational and technical workflow, not a completed physics analysis. This English documentation rewrite did not run training, open assessment, execute full-MC validation, or repeat the historical test campaigns below.

There is currently no documented publication-ready frozen full-MC run establishing improved mu precision or reliable coverage. The default protocol scope is `synthetic_software_defaults_not_physics_validation`. Software implementation, synthetic closure, controlled-MC evidence, and independent matrix elements are separate accomplishments. Platform compatibility is useful engineering evidence, not scientific authority.

## Exploratory observations

The earlier sample-efficiency proposal recorded a five-seed subset report in which AB had median W68 approximately 1.49184 and ABCD approximately 1.50080, with a median paired reduction near 0.60%. These numbers are retained only as an attributed historical observation from the superseded proposal, not as a newly verified result. The documentation did not identify a sufficient immutable run/receipt reference for independently replaying them here; they are excluded from the conclusions and must not set a tolerance or candidate automatically.

That report was described as `scientific_results_obtained=false`, with a synthetic-software-default protocol scope. AB was selected after examining the same fifteen-combination family, the ranking was primarily relative to M0c rather than a frozen AB/ABCD noninferiority test, and complete selection/event/calibration uncertainty and a training-size experiment were absent. Independent confirmation and authority evidence were not completed.

| Research question | Evidence status | Supported interpretation |
|---|---|---|
| Do engineered inputs improve M5/M4 precision? | Method and reporting available; qualified full-MC primary comparison not documented | An executable hypothesis, not a confirmed gain |
| How much does explicit `m4l` add within each feature subset? | Paired training, mass-slice diagnostics, T1 comparison, and exports implemented; qualified five-seed full-MC run not documented | An executable control, not evidence that mass is absent from off models or that mass improves precision |
| Is a compact subset noninferior? | Historical exploratory candidate observation | Motivation for a registered independent test |
| Does compactness reduce training-MC requirements? | Workflow exists; formal registered experiment pending | No established sample-saving factor |
| Are intervals reliable under signed MC and variations? | Software/synthetic checks exist; independent and full-MC scope incomplete | No general coverage or physical-systematics conclusion |
| Is a matrix-element baseline validated? | Interface and internal transformations tested | No independent M1/M1c physics result |

## Software and validation status

The following consolidates the inherited status document. It is a dated record, not a promise that all tests pass on every subsequent checkout.

| Capability | Recorded software state | Remaining evidence boundary |
|---|---|---|
| Controlled acquisition and dataset contracts | Implemented | Release equivalence is not established |
| Selection, reconstruction, Angular5, features, and weights | Implemented | Bound full-MC physical/source audit required |
| Five-role physical-group isolation | Implemented with synthetic tests | Does not replace population/history audit or ROOT interpretation validation |
| Mass-only, decay7, engineered19, lab-extension | Implemented | Interpretation depends on shared mass/input scope |
| Grouped M3 explicit-`m4l` on/off pairs and fixed-mass AUC | Implemented with synthetic contract tests | No documented qualified five-seed full-MC comparison; off models can retain implicit mass information |
| Ordinary/adversarial training and history | Implemented | Diagnostics do not prove convergence or generalization |
| MELA export/import and adapter | Implemented interface | Actual backend and independent physical reference pending |
| CDF, common templates, pyhf inference | Implemented | Signed-MC T1 approximation requires independent evidence |
| G0/G1, freeze, assessment, report | Implemented | No documented publication-ready frozen full-MC result |
| Enhanced exports | Recorded synthetic and existing-MC-artifact replay checks | AUC remains selected-checkpoint validation AUC |
| Registered evaluation orchestration | Implemented with synthetic software tests | Formal MC bootstrap/Toy/T2/stress budgets not completed |
| Independent evidence import | Receipt/type guards implemented | Missing materials remain `external_pending` |
| Sample-efficiency subsets, batch, report, controls, confirmation | Implemented with synthetic tests | Registration values and independent/full-MC evidence pending |
| Cross-platform compatibility | Not comprehensively run in the recorded change | The recorded platform only establishes behavior on that environment |

### Dated software checks

| Record | Reported result | Interpretation |
|---|---|---|
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
| Controlled mass sculpting | Independent mapping, acceptance diagnostics, common templates, frozen criteria |
| Expected mu-precision improvement | Valid T1 primary M5/M4 comparison across five paired seeds, W68 and failures |
| Reliable intervals | Registered injections/budgets, bias and coverage with binomial/paired uncertainty, boundary/failure accounting |
| Compact noninferiority/sample efficiency | Frozen candidate/tolerance, complete batch and controls, independent confirmation; actual size curves for efficiency claims |
| Physical robustness | Sourced variations, process/response/correlation definitions, independent references |

Formal result provenance includes dataset, prepared population, protocol digest, code/dirty state/environment, representation, feature subset, explicit-mass flag and ordered inputs, seed/checkpoint/model ID, mapping ID, common mass edges, template/workspace ID, inference layer, injected mu, interval, failures, comparison-family/cohort IDs, and all direct receipts. Toys additionally need freeze/claim, parent source, pairing ID, seed, budget, auxiliary-generation rule, and coverage/boundary/failure counts. Sample efficiency adds fraction/draw/full, actual train groups, subset/cell identities, multiplicity plan, and paired-bootstrap provenance.

## Interpretation limits and completion order

An observed narrower Asimov interval alone does not establish reliable coverage. AUC gains do not prove improved inference; subset gains do not prove new independent physical information or a sufficient statistic. Five seeds do not capture all MC uncertainty. Artificial stress is not a measured detector or theory systematic. More Toys or bootstrap replicas cannot create unsupported tails or recover independent information from inspected events.

When there is no significant gain, report the difference interval and the gain range that can be excluded, not information saturation. Missing MELA, insufficient templates, unvalidated statistical models, and fit failures are legitimate recorded limitations, not completed physics arguments.

Complete the scientific work in this order:

1. Audit processes, reconstruction, normalization, support, source access, group/history independence, and protocol applicability.
2. Execute bound MC preparation and minimum models/CDF/templates with G0/G1.
3. Obtain independent MELA and signed-T1 numerical references; keep missing evidence pending.
4. Freeze the applicable protocol, candidates, mappings, grids, likelihood, and evaluation budgets.
5. Execute registered paired Asimov/Toy/bootstrap/T2/stress studies, retaining failures and preventing feedback.
6. Complete compact discovery/controls and genuinely independent confirmation; execute size curves before claiming sample efficiency.
7. Run sourced robustness studies and any cross-platform compatibility checks needed for the intended deployment environments.
8. Generate manuscript figures/tables only from qualified bound artifacts.

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
| Event-MC and calibration variability | Registered 200-replica bootstrap and 20-by-100 T2 implementation | Actual registered runs, failures and coverage must be reported before a scientific reliability claim |
| MELA and sample efficiency | Existing optional repository studies | Neither is required for the six off-only outputs; no superiority-to-ME or training-sample-saving claim |
| Historical access | Prepared audit metadata and original-root claim inspection | Absence of a local claim is not proof of independent historical use; reviewed access evidence remains required |

These comparisons use the already documented literature references and do not represent a new literature search. Parameter choices (mass window, luminosity, minimum effective count, cancellation threshold, learner and pilot budgets) remain the bound core protocol defaults; no claim of optimization or independent physical validation is made. Current code-development verification is recorded separately from historical test counts in the Sprint review evidence.

On 2026-09-14, the isolated off-only implementation completed a controlled-MC A/B replay using 75 existing off checkpoints and five deterministic M0off identities: common grid, G1, freeze, fixed-T1 Asimov and the complete off-only report. The report contains 4 contributions, 24 interactions, 105 pairs, 75 AUC observations and 3125 joint seed resamples. Source model/calibration hashes and timestamps remained unchanged. The post-review output is `runs/m4l-off-003/report-B` in the isolated worktree; its generated evaluation plan binds actual manifests. See [delivery evidence](4-Reviews/sprint-m4-01-delivery.md) and [MC replay receipts](4-Reviews/sprint-m4-01-mc-stage-b.md).

This replay used automatic software-contract P0/T1 materials and has exploratory model-self Asimov scope. Full-MC event bootstrap, model-self/assessment Toys and T2 were not run; independent applicability and assessment-history review remain pending. No assessment population was decoded. The implemented C–E commands and synthetic tests do not complete those scientific evidence requirements.
