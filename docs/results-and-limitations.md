# Results and limitations

## Active off-only study

The current paper selects **test05**, `runs/h4l-off-test05/evaluation/report`.
The documentation was aligned on 2026-09-27 with the code, committed manuscript
assets, [paper evidence index](../paper/result-evidence.md), and published aggregate
metadata. Test05 compares 15 nonempty A/B/C/D subsets for seeds 42–46 plus five
deterministic `M0off` identities. Its classifiers omit explicit `m4l`, while the
bound `joint-support-v1` likelihood has one mass bin spanning 105–140 GeV.
Nonempty subsets have two score categories; M0off is an inclusive count.

All 80 nominal identities, 36 evaluation units and 200 event-MC bootstrap replicas
are numerically valid. The result nevertheless remains `exploratory_posthoc`,
`selection_aware_coverage=unvalidated`, `independent=false` for access review, and
`primary_claim_eligible=false`. A narrower nominal interval is not an established
calibrated precision gain, and the comparison does not exploit a resolved mass peak.

## Evidence summary

[The selected snapshot](../paper/selected-snapshot.json) pins the report and
aggregate snapshot/provenance hashes. The execution revision recorded by the
selected report, preparation, freeze and training artifacts is
`c5cdfa8dfab1733ee1cb2c0b4fbca087ab222a4f`, with a clean execution tree.
Paper export has separately recorded provenance; its dirty flag describes the
export environment, not the historical scientific computation.

| Binding | Selected identity |
|---|---|
| Report artifact | `baede583dc2ef36330af1184d266833f3e64a3179fc8d5ce8bff1b6867307cb5` |
| Prepared artifact | `2933b92e8df4909c579499b6f57147830fd72a878bcdd3377689be479dfa23cb` |
| Freeze artifact | `21e5e6aaeea553c274eeceaffefff6afeb60a2f3ce85146933198ac9244bd2a1` |
| Serialized core protocol SHA-256 | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| Separate analysis-contract digest | `04f2be2ace41f3c8fc11e5a8e1132f0aa783339a5246feeb14eda7e3af62927b` |
| Local aggregate snapshot | `var/paper-evidence/test05-20260926/` |

The analysis contract additionally binds threshold selection, candidate definition,
CRN coupling and budgets. A shared core protocol hash alone does not make a median
method and joint-support method the same analysis. File-byte SHA-256 values and
canonical object digests also have different serialization scopes.

The core protocol still declares `synthetic_software_defaults_not_physics_validation`.
Controlled-MC completion does not change that scope or supply independent source,
statistical or physical validation. Nothing here is an ATLAS/CMS result, a Higgs
discovery, or a physics measurement.

## `h4l-off-test05` controlled-MC result

`W68` is the nominal T1 model-self Asimov 68% interval width at injected `mu=1`.
The table follows the complete median ordering in the paper's
[committed nominal table](../paper/latex/generated/nominal_rows.tex). Values are
rounded to five decimal places; inference, ranks and paired differences use full
precision. AUC is the selected-checkpoint validation absolute-weight AUC, not an
independent test metric.

| Subset | Off inputs | Median `W68` | Median validation AUC |
|---|---:|---:|---:|
| M0off | 0 | 1.66372 | unavailable |
| BC | 6 | 1.51162 | 0.81314 |
| AC | 10 | 1.51524 | 0.87754 |
| ABC | 14 | 1.52116 | 0.86172 |
| BCD | 11 | 1.52446 | 0.82831 |
| ABCD | 19 | 1.53593 | 0.84635 |
| B | 4 | 1.56019 | 0.75781 |
| BD | 9 | 1.56136 | 0.75626 |
| ABD | 17 | 1.57368 | 0.76243 |
| AB | 12 | 1.57597 | 0.75542 |
| ACD | 15 | 1.57828 | 0.78858 |
| C | 2 | 1.59192 | 0.69096 |
| CD | 7 | 1.60009 | 0.68837 |
| A | 8 | 1.62289 | 0.68360 |
| AD | 13 | 1.62897 | 0.68456 |
| D | 5 | 1.65908 | 0.55936 |

BC and AC improve nominally over M0off by median 9.14% and 8.92%. Their observed
five-seed W68 ranges are 1.51060–1.51960 and 1.49720–1.51785; these ranges are
not confidence intervals. Both have smaller widths than ABCD in all five paired
seeds, with median relative reductions about 1.30% and 1.42%. AC wins against BC
in two seeds; their median paired difference is +0.00188, which is different from
the difference of their median widths. Per-seed winners are AC for 42/46, BC for
43/44, and BCD for 45. The median ranking does not identify a universal winner.

AC has the highest median validation AUC, while BC has the narrowest median W68.
ABCD has higher AUC than BC but a wider interval. AUC cannot substitute for the
final likelihood metric; neither metric on its own establishes reliable coverage.

### Feature attribution and interactions

The complete coalition value is `v(S)=-W68(S)`. Exact Shapley and all 24 conditional
second differences are calculated within each seed before median aggregation.
Contributions are in interval-width units, not percentages of physical information.
The following MC ranges come from the complete 200-replica event-group bootstrap,
as stored in [the paper's uncertainty table](../paper/latex/generated/mc_uncertainty_rows.tex).
They are distinct from the enumeration of 3125 training-seed vectors.

| Estimand | Nominal median | 95% MC percentile range |
|---|---:|---:|
| A Shapley | +0.01502 | [−0.00191, +0.02959] |
| B Shapley | +0.06222 | [+0.03789, +0.08465] |
| C Shapley | +0.06094 | [+0.03744, +0.08003] |
| D Shapley | −0.01110 | [−0.01654, +0.00117] |
| AC − BC width | +0.00188 | [−0.03308, +0.04018] |
| AC − ABCD width | −0.02191 | [−0.04826, +0.00162] |
| BC − ABCD width | −0.01995 | [−0.05611, +0.00349] |

The nominal ordering is `B ≈ C >> A > D`; D is negative in all five training seeds.
Its MC range nevertheless includes zero, as does A's. The unconditional AC second
difference has median +0.04246 and AB −0.05344. These are complementarity contrasts
for this learner, threshold selection and likelihood, not causal synergy, mutual
information or absence of angular physics information. The 105 direct subset
comparisons are descriptive and have no simultaneous-coverage guarantee.

### Finite-MC and threshold-selection diagnostics

All 200 replicas are valid under the joint-support analysis. They resample physical
groups separately in calibration and template, share each draw across models,
reselect thresholds and rebuild inference/attribution with fixed networks and mass
grid. They do not resample training or assessment parents. The 95% ranges above
span zero for all three highlighted compact/full contrasts; nominal advantages
are not statistically resolved by these summaries.

All 75 nominal thresholds choose the median quantile; the minimum selected signed
effective count is about 24.97. Of 15,000 nonempty-model bootstrap selections,
112 choose a nonmedian quantile and none fails. This differs from the older local
replay's 131 nonmedian selections: that replay uses different fixed draws and is
not test05's formal bootstrap. Full budget completion supplies percentile spreads,
not selection-aware interval calibration. At 200 replicas each 2.5% tail contains
only about five order statistics, so tail precision is limited.

### Conditional coverage diagnostics

The 36 units are one MC bootstrap, 15 model-self cells, 15 assessment cells and
five T2 cells. Model-self and assessment each produce 120,000 valid candidate
fits (500 × 16 × 15); T2 produces 160,000 (20 × 100 × 16 × 5). These totals count
candidate fits, not independent MC populations or independent selection procedures.

The table reports five-seed median conditional coverage at `mu=1`. T2 first
aggregates inner conditional coverage over its twenty outer calibration replicas
within each seed. Values agree with [the committed numerical macros](../paper/latex/generated/numbers.tex).

| Candidate | Model-self 68% / 95% | Assessment 68% / 95% | T2 68% / 95% |
|---|---:|---:|---:|
| M0off | 0.6500 / 0.9540 | 0.6280 / 0.9480 | 0.6370 / 0.9515 |
| AC | 0.6680 / 0.9640 | 0.6380 / 0.9620 | 0.6535 / 0.9660 |
| BC | 0.6780 / 0.9560 | 0.6580 / 0.9540 | 0.6635 / 0.9580 |
| ABCD | 0.6560 / 0.9660 | 0.6460 / 0.9640 | 0.6495 / 0.9675 |

All four assessment 68% medians are below 0.68; coverage is not uniformly nominal
across confidence levels or injections. At `mu=0`, the physical boundary makes
68% coverage conservative. The nominal expected count at `mu=1` is only about
5.27, and the nonnegative boundary, finite signed templates and template-assisted
threshold selection prevent an unqualified asymptotic guarantee. These diagnostics
do not identify a unique cause or calibrate interval critical values.

Within a training-seed block, `marginal_common_total_monotone_crn` preserves each
candidate's marginal Poisson law using shared totals and category uniforms.
`physical_event_pairing=false`: paired errors concern this artificial coupling,
not covariance from common physical events. Cross-seed Toy indexes are not paired.
Independent-allocation sensitivity is pending. Five seeds share the same MC;
seed minima/maxima in coverage figures are not coverage confidence intervals.

Report successful-fit conditional coverage, planned-denominator success-and-coverage,
and failures separately. Their denominators happen to agree in these valid cells;
future failures cannot be dropped or replaced. More Toys reduce conditional
simulation noise, not missing MC support or historical dependence.

### Publication and qualification

The access receipt is a single-researcher self-review with `independent=false`.
Independent process/normalization/reconstruction and historical-access review,
signed-MC T1 applicability, whole-selector coverage calibration, and required
sourced variations remain incomplete. MELA, capacity controls and sample-size
experiments were not part of this paper result.

The 2026-09-26 paper evidence index records a prior integrity review of 403 manifests
and 884 bound files across the three test05 roots, and a reconstruction of 4160
coverage summaries from saved Toy intervals. This documentation update does not
claim to repeat that full review. The paper collector checks 15 selected aggregate
sources and their manifest links, not every checkpoint, event or ROOT payload.
Neither hash integrity nor same-implementation recomputation is an independent
physical/statistical reference. The local runs and snapshot are ignored; permanent
external archival publication remains pending.

## Historical test01 result

<a id="h4l-off-test01-controlled-mc-result"></a>

The archived test01 report `var/runs-test-01/h4l-off-test01-old1/evaluation/report`
(artifact `3fe3e15ffe27f8480719deaa2a84a201d6a5062ca2611b0c5f67d62f54d23e05`)
remains historical evidence. It had 161/200 valid bootstrap replicas and null
formal bootstrap intervals, with a non-independent access review. It is not the
selected paper source. Its nominal agreement with some test05 values does not
make their method identity, random draws, coverage values or qualification
interchangeable. Historical checks are in [the dated alignment record](changes/evidence-alignment-20260923.md);
those records and old runs are not rewritten by this update.

## Historical exploratory observations

The earlier sample-efficiency proposal recorded a five-seed subset report in which AB had median W68 approximately 1.49184 and ABCD approximately 1.50080, with a median paired reduction near 0.60%. These numbers are retained only as an attributed historical observation from the superseded proposal, not as a newly verified result. The documentation did not identify a sufficient immutable run/receipt reference for independently replaying them here; they are excluded from the conclusions and must not set a tolerance or candidate automatically.

That report was described as `scientific_results_obtained=false`, with a synthetic-software-default protocol scope. AB was selected after examining the same fifteen-combination family, the ranking was primarily relative to M0c rather than a frozen AB/ABCD noninferiority test, and complete selection/event/calibration uncertainty and a training-size experiment were absent. Independent confirmation and authority evidence were not completed.

| Research question | Evidence status | Supported interpretation |
|---|---|---|
| Do engineered inputs improve M5/M4 precision? | Method and reporting available; qualified full-MC primary comparison not documented | An executable hypothesis, not a confirmed gain |
| How do off-only subsets compare? | Complete test05 nominal vectors, 36/36 valid units and 200/200 bootstrap replicas; independent qualification incomplete | BC/AC nominal advantages and group attribution are exploratory; compact/full MC difference ranges cross zero |
| How much does explicit `m4l` add within each feature subset? | Paired training, mass-slice diagnostics, T1 comparison, and exports implemented | The active result is off-only; it does not by itself quantify the on/off mass increment |
| Is a compact subset noninferior? | Historical exploratory candidate observation | Motivation for a registered independent test |
| Does compactness reduce training-MC requirements? | Workflow exists; formal registered experiment pending | No established sample-saving factor |
| Are intervals reliable under signed MC and variations? | Software/synthetic checks exist; independent and full-MC scope incomplete | No general coverage or physical-systematics conclusion |
| Is a matrix-element baseline validated? | Interface and internal transformations tested | No independent M1/M1c physics result |

## Software and validation status

The following distinguishes implemented capabilities from the selected test05 evidence. Historical software counts below are dated records, not a promise that every later checkout passes.

| Capability | Recorded software state | Remaining evidence boundary |
|---|---|---|
| Controlled acquisition and dataset contracts | Implemented and bound in the retained prepared artifact | Release equivalence and independent source authority are not established |
| Selection, reconstruction, Angular5, features, and weights | Non-assessment role counts recorded in the selected prepared audit | Independent physical-definition and source-access audits remain incomplete |
| Five-role physical-group isolation | Bound population and role counts recorded; G0 passed | Does not replace history audit or ROOT interpretation validation |
| Mass-only, decay7, engineered19, lab-extension | Implemented | Interpretation depends on shared mass/input scope |
| Grouped M3 off-only attribution | Five-seed nominal controlled-MC result, exact attribution and pair tables recorded | 200/200 bootstrap valid; independent qualification pending; off models can retain implicit mass information |
| Ordinary/adversarial training and history | Implemented | Diagnostics do not prove convergence or generalization |
| MELA export/import and adapter | Implemented interface | Actual backend and independent physical reference pending |
| CDF, common templates, pyhf inference | Implemented | Signed-MC T1 approximation requires independent evidence |
| G0/G1, freeze, assessment, report | Implemented | Published exploratory test05 result; no independently qualified confirmatory result |
| Enhanced exports | Recorded synthetic and existing-MC-artifact replay checks | AUC remains selected-checkpoint validation AUC |
| Registered evaluation orchestration | Controlled-MC assessment and T2 cells completed | All 36 units numerically valid; independent-allocation sensitivity pending |
| Within-seed marginal CRN evaluation | Test05 36-unit controlled-MC report published | Artificial CRN is not physical-event pairing; independent P0/T1/history review remains missing |
| Independent evidence import | Receipt/type guards implemented | Missing materials remain `external_pending` |
| Sample-efficiency subsets, batch, report, controls, confirmation | Implemented with synthetic tests | Registration values and independent/full-MC evidence pending |
| Cross-platform compatibility | Not comprehensively run in the recorded change | The recorded platform only establishes behavior on that environment |

### Dated software checks

| Record | Reported result | Interpretation |
|---|---|---|
| 2026-09-27 top-level documentation alignment | 57 passed, 6 pyhf/jsonschema deprecation warnings; 24 unique CLI examples parsed; local links/anchors and LF checked | Focused tests: `test_h4l_all_script.py`, `test_h4l_off_run_script.py`, `test_h4l_readiness.py`, `test_joint_support.py`, `test_paper_evidence.py`. No full-suite rerun or new scientific execution. |
| 2026-09-23 F4/F11/F12 final verification | Windows Python 3.12.13: 596 passed, 5 skipped, 511 deprecation warnings, 922.92 s; short temporary root | Final software/synthetic suite for this working-tree change; not independent numerical or scientific validation. [Record](changes/evidence-alignment-20260923.md) |
| 2026-09-13 enhanced-report/status update | Focused 39 passed; Windows full suite 416 passed / 34 failed | The source record attributes failures to existing scientific-resource seals and training-history contract inconsistency; no resources were re-signed. This rewrite has not independently reproduced the diagnosis. |
| 2026-09-11 performance implementation | Windows 532 passed, 60 warnings, 332.74 s; dependency check and diff check passed | A historical checkout/test inventory, not the latest suite result |

This documentation check matched all 16 nominal table rows to receipt-verified test05
CSV values, all 24 displayed coverage entries to committed paper macros, and the
four Shapley MC intervals to the bound bootstrap export. Four selected aggregate
file receipts were checked. Command checks stopped after argument parsing. The focused suite exercises software
and synthetic cases; no controlled-MC retraining, refitting, new Toy generation,
event/assessment payload decoding, raw-data validation, independent reference
validation or cross-platform replay was performed.
The historical performance JSON was verified unchanged against Git. This limited
check is distinct from the prior full test05 integrity review described above.

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

Consequently, an application request that excludes held-out entry indices is insufficient evidence that every bound branch satisfies a strict no-held-out-interpretation contract. The issue also applied to the earlier per-entry baseline. Neither version is certified by this throughput result. Independent controlled-MC source-access acceptance remained incomplete in that campaign and requires a separate bound-source interpretation audit before production performance experiments. This finding does not authorize reading restricted payload to investigate it.

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
| Expected mu-precision improvement | The specifically registered candidate/reference contrast, qualified T1 model, finite-MC uncertainty, acceptable coverage and independent confirmation; off-only and M5/M4 estimands remain separate |
| Reliable intervals | Registered injections/budgets, bias and coverage with binomial/paired uncertainty, boundary/failure accounting |
| Compact noninferiority/sample efficiency | Frozen candidate/tolerance, complete batch and controls, independent confirmation; actual size curves for efficiency claims |
| Physical robustness | Sourced variations, process/response/correlation definitions, independent references |

Formal result provenance includes dataset, prepared population, protocol digest, code/dirty state/environment, representation, feature subset, explicit-mass flag and ordered inputs, seed/checkpoint/model ID, mapping ID, common mass edges, template/workspace ID, inference layer, injected mu, interval, failures, comparison-family/cohort IDs, and all direct receipts. Toys additionally need freeze/claim, parent source, pairing ID, seed, budget, auxiliary-generation rule, and coverage/boundary/failure counts. Sample efficiency adds fraction/draw/full, actual train groups, subset/cell identities, multiplicity plan, and paired-bootstrap provenance.

## Interpretation limits and completion order

An observed narrower Asimov interval alone does not establish reliable coverage. AUC gains do not prove improved inference; subset gains do not prove new independent physical information or a sufficient statistic. Five seeds do not capture all MC uncertainty. Artificial stress is not a measured detector or theory systematic. More Toys or bootstrap replicas cannot create unsupported tails or recover independent information from inspected events.

When differences remain unresolved, report the interval and its calibration limits. A calibrated exclusion requires corresponding coverage evidence; unresolved differences do not establish information saturation. Missing MELA, insufficient templates, unvalidated statistical models, and fit failures are legitimate recorded limitations, not completed physics arguments.

The prepared population, G0/G1, off-only freeze, nominal five-seed vectors,
assessment cells and T2 cells already exist and must remain immutable. Complete
the outstanding scientific work in this order:

1. Obtain independent process, reconstruction, normalization, source-access and historical-use review for the bound population.
2. Obtain an independent signed-MC T1 applicability reference; keep MELA separate unless a matrix-element claim is made.
3. Independently calibrate coverage for the whole joint threshold-selection and bounded-interval procedure; test05 bootstrap completion does not supply this validation. A resolved-mass comparison needs its own supported, fixed design.
4. Run the registered independent-allocation sensitivity and any sourced robustness studies required by the intended claim.
5. Repeat the frozen assessment on a genuinely eligible independent source if a primary claim is sought; the existing self-review cannot be upgraded retrospectively.
6. Complete compact discovery/controls and independent confirmation; execute size curves before claiming sample efficiency.
7. Preserve the existing pinned manuscript figures/tables and source runs; publish later qualified results only with explicit new selections, provenance and evidence labels.

The current paper commits six figures: subset widths, compact comparisons, Shapley attribution, AUC versus width, MC uncertainty and conditional coverage. Supporting studies may later add epoch/control diagnostics, raw/CDF acceptance versus mass and qualified sample-efficiency curves when those experiments exist. Schematic figures must be labelled as such. Missing experiments cannot be replaced with illustrative numerical results.

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
| Event-MC and calibration variability | Test05 completed 200/200 bootstrap replicas and five 20-by-100 T2 cells | Fixed networks; bootstrap percentile ranges are not calibrated total intervals; T2 is conditional on fixed parents and non-independent access |
| MELA and sample efficiency | Existing optional repository studies | Neither is required for the six off-only outputs; no superiority-to-ME or training-sample-saving claim |
| Historical access | Prepared audit metadata and original-root claim inspection | Absence of a local claim is not proof of independent historical use; reviewed access evidence remains required |

These comparisons use the already documented literature references and do not represent a new literature search. Parameter choices (mass window, luminosity, minimum effective count, cancellation threshold, learner and pilot budgets) remain the bound core protocol defaults; no claim of optimization or independent physical validation is made. Dated Sprint records concern their original checkout. Current documentation verification is distinct from those historical test counts and from scientific validation.

On 2026-09-14, the isolated implementation first completed a controlled-MC A/B replay using 75 existing off checkpoints and five deterministic M0off identities. That historical `runs/m4l-off-003/report-B` artifact stopped before C–E evaluation; its delivery and replay receipts remain in [delivery evidence](4-Reviews/sprint-m4-01-delivery.md) and [MC replay receipts](4-Reviews/sprint-m4-01-mc-stage-b.md).

Historical test01 continued through assessment/T2 with incomplete bootstrap. The selected test05 later completed the joint-support matrix summarized above. Both histories remain immutable; the newer completion does not retrospectively repair independence or change the meaning of old diagnostics.

The active workflow uses pre-freeze J0/J1 support gates, claim-aware terminal publication, and a 37-unit report sequence. Historical v1/v2/v3 fields remain for artifact identity and compatibility; the current command-line workflow does not expose them as scientific alternatives. Software/synthetic checks, the older A/B replay, and the current controlled-MC execution remain distinct evidence records.

### Default marginal CRN evidence boundary

The default workflow uses marginal common-total CRN coupling. Its paired errors are
conditional diagnostics, not physical-event covariance. Independent-allocation
sensitivity remains pending unless the report contains completed bound evidence.
Template-only J0/J1 engineering qualification, assessment execution and
independent scientific validation are distinct gates. `h4l-off-test05` completed
assessment under a non-independent self-review, so its diagnostics remain
exploratory. Changing the workflow or run name does not reset source usage history.

The [F4/F11/F12 record](changes/evidence-alignment-20260923.md) describes historical software and archive checks. Current paper selection and build boundaries are maintained in [the paper evidence index](../paper/result-evidence.md) and [build instructions](../paper/README.md).
