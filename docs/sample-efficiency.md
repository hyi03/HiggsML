# Compact representations and sample efficiency

## Question and scope

This subordinate study asks whether fewer kinematic inputs can retain the full engineered representation's performance under a fixed MC process, event selection, mass condition, learner, and inference procedure, and whether relative performance depends on training sample size. It supports the representation questions in [Research design](research-design.md), without replacing the primary M5/M4 comparison.

Sample size means physical training-event groups, not table rows. Sample efficiency is the performance-versus-training-size relationship or the groups needed to reach a registered target. It is distinct from training speed, memory use, and total MC consumption across all analysis roles.

All main representations receive `m4l`. Compactness counts inputs other than this common condition; it does not exclude dilepton masses `mZ1` and `mZ2`. This remains MC-only educational and technical research, not a physics measurement.

## Hypotheses and design choices

The study tests whether a compact candidate is noninferior to engineered19 within a registered W68 tolerance; whether representation differences change with training size; and whether those differences depend on mass region, calibration, or model capacity. These are hypotheses, not assumed findings.

| Choice | Reason | Limit |
|---|---|---|
| Full A/B/C/D discovery family | Measures complementarity rather than deleting inputs one at a time | Selection over 15 subsets requires independent confirmation |
| Only three learning-curve representations | Restricts cost and avoids selecting another winner across the full size grid | Freeze the compact candidate before curve evaluation |
| Nested group subsets | Makes changes with size interpretable and preserves pairing | Resampling cannot repair missing support |
| Fixed evaluation populations | Isolates dependence on training MC | Does not measure total-analysis MC savings |
| Noninferiority relative to engineered19 | Tests acceptable precision loss rather than a favourable ranking | Tolerance must come from scientific acceptability, not observed differences |
| Capacity and raw/CDF controls | Tests plausible explanations of apparent compactness | Controls are limited registered comparisons, not another search |

Freeze the variable dictionary described in [Data and processing](data-and-processing.md#features-and-information-content). Variables reconstructible from the baseline can offer learning convenience without adding information. Added boost, acceptance, or laboratory inputs change the information set. AUC, Shapley, or subset rankings alone cannot resolve this distinction.

## Discovery and candidate freeze

Retrain all 15 nonempty A/B/C/D subsets and a same-procedure M0c empty set. Share mass conditioning, roles, train population, learner, weights, calibration, common grid, T1 model, and seeds 42--46. The discovery value is `v_s(S)=-W68_Asimov(S,s)` at `mu=1` and 10 fb^-1. Compute Shapley and interactions per seed before aggregation, using the [attribution rules](methods-and-evaluation.md#feature-attribution).

Also record validation absolute-weight AUC, registered mass-slice AUC summaries, local class support, efficiencies, score distributions, parameter counts, epochs, and failures. Negative contributions and unestimable regions are retained.

Candidate selection is not simply the smallest observed W68. Before confirmation access, register an ordered rule: exclude undefined inputs and incomplete comparisons; compare each subset directly with engineered19 using paired differences; require a prespecified practical tolerance; prefer fewer variables, clearer interpretation, and stable directions among qualifying candidates; freeze one primary compact candidate. If none qualifies, stop compact confirmation and report the discovery study with its limitations.

The freeze records discovery/selection artifact IDs, inspected and excluded populations, selection rule/version/reason, tolerance and its source, group list, ordered inputs, and payload digest. Its evidence status remains `exploratory_only`. Selection history must include discovery reports, and browsed populations must be covered by confirmation exclusions. A new name or role split cannot erase historical selection feedback.

## Training-size experiment

Train `decay7`, `engineered19`, and the frozen compact candidate. The initial research proposal suggests 25%, 50%, and 100% nested train fractions and at least five subset draws per non-full fraction, with network seeds 42--46. These are proposed registration choices: the checked-in overlay leaves fractions, draw seeds, support thresholds, and several budgets null. They must be frozen before the learning curve, not silently inferred from this prose.

The registered algorithm is label-stratified physical-group SHA-256 ordering with shared sorted prefixes and per-label floor rounding. For each draw, the smaller subset is contained in the larger one; representations share membership. Full size has a single `full` identity, not repeated independent full samples under different draw labels. Fit scaler and class normalization afresh within each training subset.

Do not redraw failed or unsupported subsets. Keep validation, calibration, template, and assessment populations fixed; assessment remains forbidden for discovery and learning curves. Distinguish subset-draw seeds, network seeds, evaluation-bootstrap seeds, and optional calibration-bootstrap seeds.

The fixed MLP is documented in [Methods and evaluation](methods-and-evaluation.md#classifier-and-checkpoint-selection). Its parameter count is

\[
P(d)=64d+6657.
\]

At actual dimensions 8, 13 (AB), and 20 this gives 7169, 7489, and 7937 parameters. Equal hidden widths do not imply equal capacity. The registered capacity control adjusts the first width to the nearest positive integer to `5568/(d+67)`, breaking ties downward, to approximate the engineered19 parameter count. Do not tune a collection of architectures and report only the favourable one. Without the control, qualify conclusions as specific to this MLP procedure.

## Metrics and noninferiority

For representation R and training-group count n,

\[
\Delta W_{68}(R,n)=W_{68}(R,n)-W_{68}(\mathrm{engineered19},n).
\]

Plot actual n, not only fractions. Show subset variability, network variability, and evaluation uncertainty separately. Five network seeds are not a substitute for finite-event uncertainty.

For frozen compact C and full F, define paired `D=W68(C)-W68(F)`. A negative difference favours C. Register `delta_W > 0` from an acceptable mu-precision loss and achievable confirmation precision. Noninferiority requires

\[
\operatorname{UpperCI}(D)\leq\delta_W.
\]

The overlay specifies a paired event-group percentile interval with two-sided equal tails and an upper-endpoint decision. Confidence level, bootstrap count/seed, and tolerance must be registered. Crossing the tolerance means insufficient evidence for noninferiority, not equivalence.

Separate network, train-subset, fixed-model evaluation, calibration, template, and sourced-model uncertainties. Preserve event-group multiplicity and pairing in each resample. The current overlay's evaluation bootstrap measures validation absolute-weight AUC; calibration uncertainty defaults to `not_estimated`. Neither should be described as a complete W68 or full-procedure uncertainty estimate. Formal confirmation needs the declared evaluation package and evidence.

If a registered W68 target Q* is reached on the observed grid, compare required training groups using the registered monotone linear interpolation. No extrapolation is allowed. Unreached targets stay unreached. A shrinking difference at larger n supports only a bounded finite-sample interpretation, not an information limit or universal MC-saving factor.

## Calibration controls and independent confirmation

Compare raw and physical-CDF results for the three selected representations under common support, grid, ties, tails, and T1 rules. Calibration does not retrain the network or use assessment to select a grid. Separate working-point acceptance error from mass-dependent deformation. The controls use absolute-weight acceptance denominators; signed physical weights fit the physical mapping.

If raw/CDF does not materially affect the compactness conclusion, keep the report concise. If finite calibration dominates, a broader signed-calibration study requires its own research design.

Confirmation uses a population that did not participate in selection. Before claim, scan only header, identity, and file receipts. Exclude overlaps with train, validation/calibration as applicable to recorded use, template, assessment, and all registered explored populations; the exclusion sets must cover every population used in selection. An exclusive durable claim precedes payload decoding. Success and failure both consume the attempt; an explicit repeat is restricted to the same freeze and allowed protocol.

The implemented confirmation guards do not create independent MC or certify external evidence. Controlled-MC confirmation remains `external_pending` until the required evaluation, independence, and authority evidence exists. Synthetic inputs support synthetic conclusions only.

## Execution and artifact contracts

These are independent scripts, not `higgsml` subcommands:

```powershell
python scripts/h4l_learning_curve.py --help
python scripts/h4l_sample_efficiency_report.py --help
python scripts/h4l_sample_efficiency_controls.py --help
```

### Prerequisites and registration

Use a verified prepared artifact, compact-freeze run, training-subsets run, passed G1 template run, and receipt-bound T1 evidence. Complete a new registration based on [sample_efficiency_v1.json](../config/protocols/sample_efficiency_v1.json), binding the base protocol digest, prepared artifact/population IDs, compact-freeze ID/digest, representations, fractions, seeds, support rules, tolerance, uncertainty, controls, and budgets. Null placeholders are not executable scientific choices.

Freeze construction is exposed by `freeze_compact_candidate` in the [protocol service](../src/higgsml/sample_efficiency/protocol.py); subset publication uses `publish_training_subsets` in the [subset service](../src/higgsml/sample_efficiency/subsets.py). The batch expects these upstream artifacts to exist and does not automatically select a candidate or supply a separate freeze-creation CLI. Do not manufacture a validated receipt to satisfy a prerequisite.

### Batch and report

Adapt the checked-in [batch](../config/examples/sample_efficiency_batch.json), [report](../config/examples/sample_efficiency_report.json), and [controls](../config/examples/sample_efficiency_controls.json) configurations into explicit registered files. Their example paths are placeholders. A reviewed batch config can be audited and executed as follows, replacing the example with the completed configuration:

```powershell
python scripts/h4l_learning_curve.py --dataset atlas2020_4lep --config config/examples/sample_efficiency_batch.json --plan-only
python scripts/h4l_learning_curve.py --dataset atlas2020_4lep --config config/examples/sample_efficiency_batch.json
python scripts/h4l_sample_efficiency_report.py --dataset atlas2020_4lep --config config/examples/sample_efficiency_report.json
python scripts/h4l_sample_efficiency_controls.py --dataset atlas2020_4lep --config config/examples/sample_efficiency_controls.json --controls-only
```

These commands are templates, not runnable formal experiments with the untouched examples. Batch plan mode validates existing upstream runs; it is different from the main evaluation planner's matrix-only mode. `output_root` must resolve to the project's `runs` directory; `output_name` selects a fresh direct child. CLI path overrides are available for batch/report. Controls require exact config and either `--controls-only` or `--confirm`; config mode must match. Controls-only requires empty exclusions, null confirmation input, and `repeat=false`. Confirmation requires explicit input and exclusion sets.

Batch `--clean` is limited to an owned, unstarted batch with only its ownership marker and empty staging. It cannot remove published/unknown evidence, cannot combine with plan mode, and rejects links, reparse points, and traversal. It is not recovery for a completed or failed experiment.

| Stage or schema | Binding and deliverable |
|---|---|
| `h4l-compact-candidate-freeze-v1` / `compact-freeze` | Candidate, exploration history, exclusions, tolerance, payload digest |
| `h4l-sample-efficiency-protocol-v1` | Base protocol, prepared population, freeze, experiment budget |
| `training-subsets` | Fraction/draw member JSONL, full alias, per-class statistics |
| `sample-efficiency-train` | Subset, representation, architecture, network seed, checkpoint, lineage |
| `sample-efficiency-plan` | `batch-plan.json`; scientific plan separated from execution/resources |
| `sample-efficiency-calibration` | Bound model and raw calibration lineage |
| `sample-efficiency-common-grid` | Recomputable grid from the complete participant set |
| `sample-efficiency-template` | Mapping, common grid, prepared source, signed template |
| `sample-efficiency-inference` | Model-self Asimov semantics, W68, AUC pointer |
| `sample-efficiency-batch` | Ledger and summary for every planned cell and blocked stage |

Subset readers verify all prepared identity/receipts but decode only train payload for membership and digests. Representations share `pairing_id` when data, network, and architecture conditions match; individual cells have `experiment_cell_id`. Scientific terminal states retain published stages and blocked-stage records. Binding errors, duplicates, missing participants, and unknown exceptions must not produce a report-consumable batch.

The report publishes `report-contract.json`, `sample-efficiency-records.jsonl`, `sample-efficiency-summary.json`, `sample-efficiency-curves.csv`, `sample-efficiency-curves.png`, `sample-efficiency-report.md`, and `manifest.json`. Readers replay the batch, cells, bootstrap, paired summaries, and Q*, comparing JSON/JSONL/CSV/Markdown bytes. PNG is a non-authoritative cache of the bound plot specification. Always give planned, complete, terminal, and valid-pair denominators; missing cells cannot establish noninferiority.

## Deliverables and interpretation

| Stage | Deliverable |
|---|---|
| S0 | Input dictionary, historical-use audit, common support |
| S1 | Complete subset discovery, per-seed attribution, failures |
| S2 | One compact candidate, tolerance, and freeze |
| S3 | Three-representation curves with actual n and layered uncertainty |
| S4 | Limited raw/CDF and capacity controls |
| S5 | Independent noninferiority confirmation, bias, coverage, failures |
| S6 | Sourced robustness and traceable manuscript results |

Report the feature dictionary; subset dimension versus W68 and paired full-reference differences; mass-region support; per-seed attribution; learning curves; observed-range target crossings; raw/CDF acceptance diagnostics; confirmation intervals; and the complete failed/missing-cell table. Do not draw an invented smooth curve where no experiment exists.

A confirmed compact representation is a result about this MC population and learner, not a minimum sufficient statistic. An unconfirmed subset advantage is a discovery hypothesis. A wide interval is inconclusive, not equality. Complementarity is metric-dependent, not causal synergy. Smaller W68 without qualified coverage is not reliable sensitivity improvement. A paper can discuss compactness after credible discovery and independent confirmation; claims of sample efficiency additionally require the actual training-size experiment. Historical exploratory observations are kept in [Results and limitations](results-and-limitations.md#exploratory-observations), not used as registration defaults here.
