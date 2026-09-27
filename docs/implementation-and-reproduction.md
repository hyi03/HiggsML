# Implementation and reproduction

This document connects the [scientific methods](methods-and-evaluation.md) to tools, commands, and persisted contracts. Aligned with the code and selected test05 paper on 2026-09-27. Run all commands from the repository root in a suitable environment. Examples containing placeholder paths require verified upstream artifacts; documenting a command does not establish that its scientific prerequisites have passed.

## Tools and architecture

| Tool | Purpose and selection rationale | Boundary |
|---|---|---|
| Python 3.12 | Shared scientific implementation and script environment | Use the repository's supported minor version |
| uproot / Awkward / vector | ROOT access, jagged lepton data, and four-vector operations | Profile units and basket interpretation still require audit |
| NumPy / SciPy / pandas | Array statistics, numerical operations, and analysis tables | Preserve group covariance and signed-weight semantics |
| PyTorch | Fixed MLP, adversary, deterministic training records | Framework support is not evidence of convergence |
| pyhf 0.7.6 | Explicit binned likelihoods, modifiers, and auxiliary observations | Validate the chosen approximation on bound MC |
| Matplotlib / mplhep | Diagnostic and report figures | Figures must reflect bound records, not invented results |
| JHUGenMELA | Optional external matrix-element reference implementation | Requires a separately built backend and independent physical reference |

These tools fit the existing Python workflow and permit explicit model and artifact inspection. The documents do not establish that each is optimal against every alternative. Replacing the statistical engine or learner changes the comparison and requires a separately justified validation.

| Layer | Implementation | Responsibility |
|---|---|---|
| CLI and orchestration | [cli.py](../src/higgsml/cli.py), [workflow.py](../src/higgsml/workflow.py), scripts | Arguments, stage dependencies, binding, and exit codes |
| Physics | [physics](../src/higgsml/physics/) | Selection, reconstruction, kinematics, weights, and grouping |
| Modeling | [modeling](../src/higgsml/modeling/) | Representations, training, CDF, and matrix-element contracts |
| Inference | [inference](../src/higgsml/inference/) | Templates, likelihoods, diagnostics, stress, and reporting |
| Sample efficiency | [sample_efficiency](../src/higgsml/sample_efficiency/) | Registration, subsets, batch, controls, and confirmation |
| Configuration and identity | [config.py](../src/higgsml/config.py), dataset and resource binding modules | Strict parsing and protocol/source seals |
| Artifact publication | [artifacts.py](../src/higgsml/artifacts.py), [_manifest.py](../src/higgsml/_manifest.py), [_transaction.py](../src/higgsml/_transaction.py) | Canonical records, staging, receipts, and immutable publication |

Dependencies run from CLI/orchestration to domain services. Scientific rules belong in protocols and domain code, not CLI branches or plotting. Resource options cannot silently change epochs, thresholds, or scientific identity.

### Persistent software requirements

The IDs below retain the former requirements document's traceability. Implementation/evidence status is maintained only in [Results and limitations](results-and-limitations.md#software-and-validation-status).

| IDs | Requirement |
|---|---|
| DATA-01, DATA-02 | MC-only access; explicit dataset selection; no unvalidated release mixing or shared feedback |
| DATA-03, DATA-04 | Bind bytes, profile, protocol, and upstream identity; preserve physical groups across roles/folds |
| SAFE-01, SAFE-02, SAFE-03 | Protocol-defined mass use; no technical inputs; freeze before assessment; immutable runs and budgeted repeats |
| API-01, API-02, API-03 | One `higgsml` package/console entry; thin CLI; reject unknown, missing, duplicate, or mistyped configuration |
| PHY-01, PHY-02 | Bound reconstruction/selection/weights; explicit mass-only, decay7, engineered19, lab-extension, and ME representations |
| MODEL-01, CAL-01 | Bind candidate, inputs, architecture, seed, checkpoint, diagnostics, calibration measure, grid, ties, and mapping |
| INF-01, INF-02 | Preserve signed template statistics and common bins; record likelihood, intervals, injection, budget, and failures |
| ART-01, ART-02 | Staging, atomic publication, manifest-last, success/failure separation, full lineage and platform |
| QA-01, QA-02, QA-03 | Test isolation and numerical contracts; report evidence levels separately; require independent MELA/coverage evidence for matching claims |

## Environment and installation

Use Python `>=3.12,<3.13` and the Conda `pytorch` environment. The [environment definition](../environment.yml), [Windows environment snapshot](../win.yml), and [macOS environment snapshot](../osx.yml) define the environment context; [pyproject.toml](../pyproject.toml) defines the package.

```powershell
conda env create -f environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip install -r requirements.txt
python -m pip check
higgsml --help
```

Create the environment only if it does not already exist. `requirements.txt` supplies the inference additions including pyhf. For parallel inference, install the optional package extra with `python -m pip install -e ".[parallel]"`, containing cloudpickle and threadpoolctl; it is not named `research-parallel`. Serial defaults do not require activating parallel execution. Do not change environment locks merely to make a validation claim pass.

Windows, Linux, and macOS on supported CPU architectures are peer execution platforms; none is an authority requirement. Record the actual platform in provenance when evaluating portability. MELA uses an independently configured Linux/WSL environment, described below.

### Controlled acquisition

```powershell
python scripts/init_data.py --dataset atlas2020_4lep
```

The downloader uses direct HTTPS requests for contracted MC members and publishes the receipt only after size/hash verification. Inputs live under `data/raw/<dataset>/`. Never inspect, hash, preprocess, score, or plot real data. The 2025 downloader option does not change the active H4l dataset.

Controlled preparation automatically emits `h4l-p0-validation-v2` and `h4l-t1-validation-v2` materials with `status=contract_checked`. Dataset, protocol, source identity and the physical-definition / T1 modifier contracts remain bound. Qualification explicitly keeps `source_audited`, `independent_numerical_validation`, `physical_applicability` and `confirmatory_eligibility` false. `independent_reference=null` and an empty T1 numerical-test list do not invent independent evidence. See [P0 v2](../config/schemas/p0_validation_v2.schema.json) and [T1 v2](../config/schemas/t1_validation_v2.schema.json).

Legacy v1 `validated` evidence remains readable for exploratory software execution and is never rewritten in place. G0 and T1 accept bound software prerequisites, while scientific access/applicability gates still require separate receipts, independent packages and history review. New audits/inference metadata publish the conservative interpretation. Pure paper export requires no prepare/train/inference rerun. Publishing new audit/freeze qualification artifacts requires fresh roots for affected downstream stages; do not silently replace old artifacts.

## Main workflow

The end-to-end path first initializes the controlled dataset. Start with a metadata-only preflight and explicitly select the threshold method:

```powershell
python scripts/init_data.py --dataset atlas2020_4lep
python scripts/h4l_all.py --run-name planned-joint-001 --threshold-method joint-support-v1 --plan-only
```

Omitting `--run-name` uses the stable name `default`; `h4l_all.py` defaults to `joint-support-v1` and explicitly forwards the selected method to Stage B and evaluation. Resume legacy median runs with `--threshold-method median-v1`. An existing registration must match the requested method; old artifacts are never converted automatically. `--plan-only` reads manifests, registration metadata and access ledgers, prints the planned commands, and never launches children or opens event/assessment payloads. Without an existing prepared identity it reports `pending_prepare_identity`, which is not access clearance. Actual execution checks again immediately after prepare, before training. Remove `--plan-only` only when ready to execute. Add `--stage-b-only` to stop after verifying the bound Stage B plan, inputs and report, without generating access reviews or running evaluation; historical assessment access does not prevent this explicitly limited scope.

Re-running the same command validates published manifests and skips complete stages before continuing at the next missing stage. Invalid final stage directories are quarantined without deleting `.failed` evidence. The wrapper passes `--worker-threads 1` to `h4l_off_run.py` and selects `--workers` from 1--4 from installed physical memory: it first retains 2 GiB for local orchestration and system variation, then budgets 5 GiB for each worker, falling back to one worker when physical memory cannot be detected. A 16 GiB host therefore starts two workers. The allowance covers transient process peaks while pyhf/SciPy fitting and result serialization overlap. Complete bootstrap, Toy, and T2 work units can therefore run in bounded parallelism without nested thread expansion. A pre-existing bound access review is reused; otherwise a local named-user single-researcher self-review can be generated only when the declared history contains no matching access. This remains explicitly non-independent and exploratory. Frozen assessment/T2 budget claims are never bypassed by resume.

### Cross-root history and completion states

[`config/h4l_history_roots.json`](../config/h4l_history_roots.json) declares the history scope. Paths are relative to the project root, cannot escape it or use symlinks/junctions, and must include the current run root. The current configuration includes only `runs/`, which may be absent before a new run; no files under `var/` are needed for preflight. Malformed ledgers in a declared root fail closed. This single-root audit cannot establish that a population was never assessed in another directory or machine, and does not qualify the run as independent. Preserve archived history and its original ledgers when relocating or resuming an archived run, and explicitly register that root for a cross-root audit.

All registered roots use the first configured root for new atomic population reservations; scans still include every declared root. Claim-only history is evidence of access/budget consumption, not proof of completed computation. Model-self claims do not consume assessment access. A different or unknown freeze for the same population blocks a new assessment/T2 run, including after a new run name or a new prepare artifact. Same-freeze continuation requires its existing bound access receipt and obeys the original budgets.

New local reviews use [`h4l-off-self-review-access-v2`](../config/schemas/h4l_self_review_access_v2.schema.json): `history_review=self_reviewed_no_access_in_declared_roots`, audited root paths, registry hash, and empty matches. Legacy v1 reviews remain readable without rewriting them, but neither schema bypasses the live history gate. `independent=false` and the exploratory-only conclusion remain explicit; external review is also subject to live history.

The wrapper returns `5` for preflight/access/support blocking and `6` when children exit normally but the requested completion evidence is missing or invalid. Other child failures retain their exit codes. Exit `0` means the requested execution scope completed (or a read-only plan returned without blocking). Full completion requires all 36 registered terminal units, their payload hashes and identities, and a report bound to those exact units and the plan. The reported path may select a current `report-resume-*` snapshot instead of an older `report`. Published numerical failures can be terminal: `execution_status=complete` can coexist with `scientific_status=incomplete`. Even numerically valid output remains `unvalidated_exploratory_only`. Stage B alone reports `stage_b_complete` and `evaluation_started=false` for this invocation.

These orchestration checks do not change physical weights, add scale factors, replace T0/T1 interval algorithms, or establish selection-aware coverage. See the [entry-hardening record](changes/h4l-entry-hardening-20260924.md) for verification and remaining scientific prerequisites.

### Prepare reusable inputs

```powershell
python scripts/h4l_prepare.py --run-name pilot-001 --plan-only
python scripts/h4l_prepare.py --run-name pilot-001
```

Defaults bind the 2020 receipt, profile, and H4l protocol, and publish:

```text
runs/h4l-prepare-pilot-001/
  inputs/     ROOT manifest and P0/T1 bindings
  audit/      Source audit
  prepare/    Reusable events.jsonl and manifest
```

Preparation does not train or calibrate. The prepare/check/run helpers support `--continue` for validated recovery; complete stages are reused and invalid final directories are quarantined as `.name.<uuid>.invalid`, preserving prior `.failed` evidence. Use `--run-name` for the named workflow or `--run-root` for an explicit diagnostic or legacy location; they cannot be combined. Published directories cannot be overwritten; use their supported continuation contract or a fresh root. Progress counts may include entries skipped without application payload requests; selected counts refer to published selected events. `--no-progress` disables progress. `root_prepare_metrics` persists timing regardless of terminal display; `--show-prepare-metrics` adds periodic and final timing, spans, throughput, RSS, and hotspot diagnosis. These are software observations.

The same run name makes G1 and batch commands consume this scoped prepared artifact. Omitting `--run-name` retains the legacy `runs/h4l-prepare/` default for explicit-path workflows. For a separate bounded diagnostic, use a fresh directory:

```powershell
python scripts/h4l_prepare.py --run-root runs/h4l-prepare-diagnostic-001 --diagnostic-entries-per-file 10000 --show-prepare-metrics
```

The resulting `diagnostic_complete` state is not a training/G1 input. The ROOT interpretation limitation remains in force.

### Gate and standard batch

```powershell
python scripts/h4l_check.py --run-name pilot-001 --plan-only
python scripts/h4l_check.py --run-name pilot-001
python scripts/h4l_run.py --run-name pilot-001 --plan-only
python scripts/h4l_run.py --run-name pilot-001
```

G1 reuses the prepared artifact, running seed-42 M0c/M2/M3, five calibrations, and common templates. The output root is `runs/h4l-train-pilot-001/`, with `g1/` and `batch/` underneath. On failure, preserve the run and use a new run name/output root; an explicit `--prepared-run` can reuse the same prepared artifact. Follow the script's printed next command to preserve the correct gate binding.

The default `h4l-feature-combination-batch-v3` batch uses seeds 42--46, training M0c, M2, M3, and every one of the 15 nonempty A/B/C/D feature combinations both with and without explicit `m4l`. The config binds the original `engineered19_raw_T1` family, the `engineered19_raw_T1_m4l_on_off` comparison family, and the ordered variants `["on","off"]`. Both variants receive raw calibration and enter the same common template/T1 model-self Asimov `mu=1` comparison; the existing M2/M3 physical calibrations remain unchanged. The documented matrix is 165 training, 175 calibration, and three aggregate stages; the actual plan output is authoritative. An explicit `--seed 42` is a 71-stage single-seed diagnostic, not a completed five-seed comparison.

The on key is `M3:<seed>:groups=<subset>` and the off key appends `:m4l=off`; this prevents the two independently trained artifacts from colliding in templates, inference, or exports. Batch completion requires a valid 15-pair comparison for every requested seed. A complete five-seed run additionally requires a valid mass-input summary, so a missing model, invalid T1 width, mismatched/unsupported mass slice, missing M0c reference, duplicate seed, or deleted failure cannot be silently summarized.

The three helpers accept `--protocol`, defaulting to the sole H4l protocol, and propagate it to child stages. `--plan-only` audits planned commands; it does not provide scientific qualification. The standard Asimov batch does not authorize assessment or complete the optional candidate/variation matrix. Its fine-grid/CDF contracts and mass-on/off diagnostics are distinct from the later single-bin joint-support attribution analysis.

### Direct stage composition

```text
audit -> prepare -> [me-export -> me-import] -> train -> calibrate
      -> templates -> freeze -> infer -> [mc-bootstrap] -> report
                                      [evidence-import] ----^
```

For direct CLI calls, provide dataset, explicit protocol, correct upstream runs, and a fresh `--run-dir` under `runs/`. For example, after all relevant preparation gates:

```powershell
higgsml train --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare-pilot-001/prepare --candidate M2 --seed 42 --run-dir runs/h4l-m2-42
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare-pilot-001/prepare --model-run runs/h4l-m2-42 --transform physical --run-dir runs/h4l-m4-42
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare-pilot-001/prepare --model-run runs/h4l-m2-42 --transform raw --run-dir runs/h4l-m2-raw-42
higgsml train --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare-pilot-001/prepare --gate-run runs/h4l-train-pilot-001/g1 --candidate M3 --groups AB --mass-input off --seed 42 --run-dir runs/h4l-m3-ab-m4l-off-42
```

`--mass-input` defaults to `on`. `off` is accepted only by `train` for a grouped M3 with a nonempty A/B/C/D subset; other stages and candidates reject it. The model records the flag, exact ordered inputs, and validation AUC for every registered 5 GeV mass slice. Downstream calibration reads the flag from the bound model, so it does not take another off switch.

Build the other minimum participants and pass their calibration runs together to `templates`. G1 precedes remaining seeds, grouped on/off controls, M6, fixed200 control, absolute-weight bridge, and L1. Absolute calibration requires the same prepared population/protocol and passed `--gate-run` before calibration payload is read.

```powershell
higgsml infer --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --template-run runs/h4l-templates-001 --layer T0 --mu 1 --run-dir runs/h4l-t0-001
higgsml report --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --result-run runs/h4l-t0-001 --run-dir runs/h4l-report-001
```

These paths assume existing verified templates; T0 does not substitute for the registered T1 primary comparison. Use each subcommand's `--help` for its exact required arguments.

### Frozen assessment and registered evaluation

Assessment requires bound freeze evidence and a durable claim. `infer --expectation-kind assessment` takes prepared and freeze runs; `--repeat-assessment` is only for explicitly permitted reuse of the same frozen analysis. `--procedure t2 --layer T1` uses the separate outer/inner protocol budget and does not take an additional `--toys` budget. Stress kinds are normalization, mass, score, and correlation, with direction -1/+1 and mode omitted/modeled. Score/correlation uses the frozen `M3:42` reference and rejects a replacement before claim and decoding.

The [evaluation-plan example](../config/examples/h4l_evaluation_plan.json) is an `exploratory_posthoc` template containing zero artifact IDs. Create a new complete plan with the actual prepared/template/freeze IDs, budgets, and registration status before assessment. A retrospectively written plan is not preregistration.

```powershell
python scripts/h4l_evaluate.py --plan config/examples/h4l_evaluation_plan.json --prepared-run runs/h4l-prepare/prepare --template-run runs/h4l-train-pilot-001/batch/all-seeds/templates --freeze-run runs/h4l-freeze-001 --output-root runs/h4l-evaluation-001 --plan-only
```

The unchanged example may be used only to inspect its matrix, not execute a formal experiment. Replace it with the completed plan for execution. Matrix-only planning checks schema/budgets without requiring the local runs to exist or opening assessment; execution checks artifact IDs. This separate generic plan describes 25 stages covering one paired fixed-network MC bootstrap, model-self/assessment Toys at 0/1/2, one T2 procedure, sixteen artificial stress cases, and an enhanced report. It is not the current off-only 36-unit evaluation plan. Failed replicas stay in the original denominators.

### Cleanup and recovery

The helpers expose `--clean`, mutually exclusive with `--plan-only`. It computes and deletes paths without validating scientific inputs or running stages. Preparation targets its `inputs`, `audit`, and `prepare`; gate cleanup targets `g1`; batch cleanup targets `batch/all-seeds` or an explicit seed directory. Explicit paths use `--run-root` for prepare and `--output-root` for gate/batch. Gate/batch cleanup requires an explicit name or path. Root `runs/`, files, links, and escaped paths are rejected.

Cleanup is destructive and is not permission to remove completed, failed, diagnostic, or published evidence. Review the exact target through help/planning before any eligible cleanup. Normal recovery uses a new directory and preserves the previous terminal state. Sample-efficiency cleanup is narrower: only owned unstarted staging, as documented in [its workflow](sample-efficiency.md#execution-and-artifact-contracts).

## Artifact and lineage contract

Main stages use `research-run-v1`. Write into a same-parent staging directory, validate, then publish atomically with the success manifest last. It records the size and SHA-256 of every other file. Failure publication exposes sanitized failure evidence without a fabricated success state. Completed, failed, and diagnostic runs are immutable.

Bind dataset/profile/protocol bytes and digests; each direct upstream path, stage, artifact ID and receipt; parameters, seeds, resources, code version/dirty state, packages and platform; file and canonical-payload digests; and scientific terminal state. Readers reload and validate disk-backed artifacts rather than trusting constructed in-memory objects, including upstream multiplicity and recomputable identities. Models contain numeric JSON tensors, not executable pickle.

| Stage | Main content and bindings |
|---|---|
| audit | Source manifest, dataset/profile/protocol, provenance and support |
| prepare | `events.jsonl`, reconstructed population, identity/role and weight summaries |
| me-export / me-import | Ordered inputs, backend/process/adapter, independent reference, result digest |
| train | `model.json`, ordered inputs, explicit-mass flag, scaler, architecture, seed, checkpoint, global and fixed-mass-slice validation AUC, history/curves |
| calibrate | Model, calibration population, weight target, mapping/threshold identity |
| templates | Participant mappings, common edges, yields, sumw2/covariance, G1 |
| freeze | Candidate/status completeness, template/likelihood identities, access budget |
| infer | Workspace, layer, injection, intervals/Toys, auxiliary-generation and failure records |
| mc-bootstrap | `bootstrap.json`, sealed plan, paired groups and common grid |
| evidence-import | `evidence.json`, external receipts and scope/independence metadata |
| report | Explicit result/training/evaluation/evidence bindings and qualified exports |

The prepared-event envelope and role semantics are in [Data and processing](data-and-processing.md#prepared-event-contract). Sample-efficiency schemas and stages are maintained in [Sample efficiency](sample-efficiency.md#execution-and-artifact-contracts).

Typical exits are 0 for a normal terminal return, 2 for usage errors, 3 for input/binding errors, 4 for path/transaction errors, 5 for denied access, and 70 for unclassified internal errors. A zero exit alone is not proof of a passed scientific gate; inspect the published state. Internal errors retain sanitized failure records and never expose unauthorized assessment features, predictions, or thresholds.

### Enhanced analysis exports

`report` accepts repeatable `--training-run`, `--evaluation-run`, and `--evidence-run`, with `--result-run` for primary inference. Relationships come from explicit validated bindings, never directory scanning. Existing runs can feed a new report directory without rewriting or retraining them.

The `h4l-analysis-export-v1` outputs include:

| Files | Logical row unit |
|---|---|
| `models.csv`, `training_history.csv`, `model_mass_diagnostics.csv` | Model/seed, model/epoch, model/mass bin |
| `feature_metrics.csv`, `feature_summary.csv` | Combination/seed and paired five-seed summary |
| `mass_input_metrics.csv`, `mass_slice_auc.csv`, `mass_input_summary.csv` | Paired explicit-`m4l` on/off AUC, fixed 5 GeV validation-slice AUC with local support, and T1 W68 comparisons |
| `calibration_summary.csv`, `calibration_slices.csv`, `calibration_bins.csv` | Mapping, mass slice, score bin |
| `template_bins.csv`, `template_covariance.csv` | Candidate/process/bin and nonzero group covariance |
| `inference_intervals.csv`, `toy_fits.csv` | Asimov interval and Toy/confidence-level fit |
| `coverage_summary.csv`, `fit_diagnostics.csv`, `paired_comparisons.csv` | Coverage, bias/pull, paired observations |
| `bootstrap_replicas.csv`, `procedure_replicas.csv`, `stress_results.csv` | Bootstrap, T2 replica, stress scenario |
| `feature_attribution.csv`, `feature_interactions.csv` | Shapley and second differences |
| `run_statuses.csv`, `evidence_status.csv` | Stage and independent-evidence status |

`provenance.json` records protocol, populations, upstreams, plan, grid, environment, and export receipts. `data_dictionary.json` defines types, units, formulas, roles, and missingness. `analysis_records.jsonl` mirrors every CSV logical row as `{table,row}`, retaining JSON numeric precision. CSV is UTF-8 and retains full precision.

Missing historical values remain null with `not_recorded` or explicit status, never zero-filled or inferred from total loss. AUC is `validation_absolute_weight_auc` at the selected checkpoint; M4/M5 do not inherit raw AUC under a CDF-AUC label. For mass-input controls, `delta_auc_on_minus_off=AUC_on-AUC_off`, `delta_width68_on_minus_off=W68_on-W68_off`, and `relative_w68_improvement_from_m4l=1-W68_on/W68_off`. `mass_slice_auc.csv` retains background/signal row counts, absolute-weight sums, and effective counts for the fixed validation slices. Training and inference states stay separate. `report.json` retains summaries, indices, row counts, and `result_count`/`results_export` rather than duplicating large per-Toy arrays. Missing or ambiguous paired fixed200 controls are recorded, not chosen by best performance.

### Independent evidence

`h4l-independent-evidence-v1` supports `signed_mc_t1`, `physical_systematics`, `mela`, and `frozen_assessment`. A validated package needs external producer/reference ID, independence explanation, type-specific comparison metadata, and at least one contained file receipt with size/hash. Reject escaping/link paths, invalid receipts, or unsourced variations.

The [pending example](../config/examples/h4l_independent_evidence.pending.json) can represent missing evidence as `external_pending`. `evidence-import --evidence-file <package>` only validates declared metadata/files; it does not run external experiments or promote schema validity to scientific validity. An empty [schema registry](../config/schemas/registry.json) provides no self-certified golden reference; authority references must be independently registered.

## MELA backend contract

The optional [adapter](../scripts/mela_kinematic_adapter.py) and [interop runner](../scripts/research_mela.py) bind [JHUGenMELA commit 10d36ced1d71b5e4e21abb1c9834a02570bf31c0](https://github.com/JHUGen/JHUGenMELA/tree/10d36ced1d71b5e4e21abb1c9834a02570bf31c0). The retained API review covered Python bindings and Mela/TUtil/TVar source; it did not build or execute MELA on Windows.

The external adapter implements `compute_probabilities(event, backend, process)` and declares `PROBABILITY_DEFINITION='kinematic_decay7_at_fixed_m4l_no_mass_pdf'`. It returns nonnegative finite `p_signal` and `p_background`; the score follows the bound `p_signal/(p_signal+p_background)` definition and rejects unsupported values.

The pinned API exposes `Mela`, `SimpleParticle_t(id,px,py,pz,E)`, `SimpleParticleCollection_t(list)`, `setInputEvent`, `setProcess`, `resetInputEvent`, and a floating-return `computeP(useConstant)` wrapper. The adapter calls `computeP(False)`, never the separate `computePM4l` interface. Settings are 13 TeV, pole mass 125 GeV, signal `HSMHiggs/JHUGen/ZZGG`, background `bkgZZ/MCFM/ZZQQB`, and the source-default NNPDF30_lo_as_0130 member 0. Full settings/process are recorded in adapter metadata; the background choice does not establish DSID composition.

Exported leptons first reconstruct repository decay7/mass, then define canonical massless leptons with zero total three-momentum. Original system pT/rapidity, lepton masses, and global azimuth are excluded. Repository Z ordering, negative-lepton direction, and angle conventions must be respected; names alone do not establish agreement with MELA. Undefined angles or mass support fail.

In an isolated Linux/WSL directory, build the pinned Python extension and set `H4L_MELA_BUILD_RECEIPT` to an existing JSON record:

```json
{"source_commit":"10d36ced1d71b5e4e21abb1c9834a02570bf31c0","extension_sha256":"<loaded extension SHA-256>"}
```

The runner's working directory should be isolated because upstream initialization creates Pdfdata links. Bind the actual loaded extension hash, backend `name=JHUGenMELA`, full-commit version, `configuration_digest(build_receipt)`, and exact `PROCESS`. A matching hash alone does not independently certify source-build provenance.

```python
import json
from scripts.mela_kinematic_adapter import SOURCE_COMMIT, PROCESS, configuration_digest

with open("mela-build-receipt.json", encoding="utf-8") as source:
    receipt = json.load(source)
config = {
    "backend": {"name": "JHUGenMELA", "version": SOURCE_COMMIT,
                "configuration_sha256": configuration_digest(receipt)},
    "process": PROCESS,
}
with open("backend-config.json", "x", encoding="utf-8") as output:
    json.dump(config, output)
```

Use that configuration for `me-export --backend-config`, then run the verified adapter:

```bash
python scripts/research_mela.py --input /path/me-input.json --adapter /path/verified_mela_adapter.py --adapter-sha256 SHA256 --output /path/new-me-output.json
```

The result, independent reference, and every reference check must bind the same adapter SHA, backend, process, units, input digests, and expected/actual probability pairs with traceable evidence ID. Missing, duplicate, unknown events and negative/nonfinite probabilities fail. No fake module or arbitrary substitute formula can produce an M1/M1c scientific result.

Pre-freeze ME export excludes assessment. After freeze, a bound `me-export --freeze-run` and newly verified import can supply `--assessment-me-run` to assessment inference. Overlapping events must have identical input digests and scores; only missing assessment rows are supplemented. Frozen models/maps/thresholds do not change. The supplement is a new upstream artifact; old runs lacking `me_binding` must be rebuilt under a new path, not patched.

## Performance implementation

The performance work reduces repeated computation while preserving scientific rules. ROOT payload requests preserve legal spans, identity backfill, and source/entry order. A call-scoped bounded thread executor (resource default `root_threads=4`) performs uproot decompression/interpretation within those requests; it does not authorize wider entry ranges or create independent ROOT process workers. For roughly random development selection at probability p, expected span count is `p+(N-1)*p*(1-p)`; p=0.8 gives mean spans near five entries. Batching therefore does not promise hundreds rather than hundreds of thousands of calls, nor proportional end-to-end speedup.

Templates use a sparse physical-group/bin matrix G: yield is its column sum and covariance is `G.T @ G`. Keep a separate occupancy relation: zero signed contribution does not imply no group. With a merge map A, `G_new=G@A` and `C_new=A.T@C@A`; merged variance includes `2*C[a,b]`. Count groups by union, retain process/category ordering and structural support, and apply the original leftmost-failure merge sequence across all participants.

Calibration caches interval membership/moments but recombines groups and rechecks cross-score-bin restrictions after merging. It does not adopt template weight formulas blindly. Score interpolation is chunked, preserving endpoint, single-slice, ties, and boundary behaviour. Training caches tensors/masks and diagnostic encodings without reducing epoch scoring or threshold recomputation.

`profile_intervals` shares one unconditional MLE across levels; `profile_interval` remains a wrapper. Root searches and per-level failures stay separate. Fixed-POI warm starts are not enabled by default. Toy/T2 computation uses bounded tasks with fixed inputs and ordered collection. The parent owns publication. T2 prerequisite recalibration remains ordered in the parent and consumes inner seeds only after success; workers do not launch another inference pool. Unexpected worker errors propagate to the original failure transaction.

JSONL is streamed with identity-first access. Population digests retain deduplicated, sorted physical-group tuples and original encoding, not file-order hashing. Copied JSONL is revalidated on the final copy. ME lookup, joint-cell projection, stress encodings, auxiliary layout, and fixed-score caches are reused only under matching identities within the call. Upstream hashes are rechecked before publication; stat-only caches cannot replace receipts.

Resources can be supplied through [resources.json](../config/examples/resources.json):

```json
{"workers":1,"worker_threads":1,"root_max_entries":4096,"root_threads":4}
```

The checked-in example omits `root_threads` and inherits the default of four. Unknown fields, booleans, nonintegers, and nonpositive values fail. Resources and performance records are in the manifest, with `performance_implementation=research-refactor-v1`; they do not redefine model/mapping scientific identities. CDF/joint-cell temporary arrays use approximately 8 MiB blocks; T2 score caching is bounded near 64 MiB. These are local budgets, not process RSS limits: final tables, results, dense output covariance, and worker runtimes still consume memory.

ROOT process pools, candidate/seed training pools, warm starts, GPU/mixed precision, and changes to fixed small scientific loops are not default outcomes of this work. The historical A--G sequence covered baseline instrumentation, legal spans, interpolation/training caches, group statistics/merging, shared MLE, bounded inference parallelism, and streaming/identity caches. Every replacement must preserve discrete states, order, random inputs, merge history, and serialized identity where applicable. Numerical tolerances are set before comparison; near-equal payloads must not be called identical artifacts. Rollback uses a new run and retains failure evidence.

## Verification commands and evidence levels

For focused H4l software checks, then the full suite and environment:

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest tests/h4l -q
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest -q
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
git diff --check
```

Optional syntax/package checks use `python -m compileall -q src scripts tests` and `python -m build --wheel --no-isolation` when build tooling is installed. Generated outputs are not committed. A separate synthetic benchmark is available as `python -m scripts.research_performance_benchmark --output <fresh-path.json>`; never overwrite retained measurements or benchmark alongside competing training/tests.

Relevant scientific-contract checks include all/none/alternating eligible ROOT spans, boundaries, repeated groups, signed cancellation, cross-bin covariance, bootstrap multiplicity, CDF tails/ties, exact training histories, MLE/root failures, worker-order/failure cleanup, ME coverage/bindings, and artifact round trips. Independent expected values or a fixed baseline must accompany implementation checks. Full-MC, external MELA, source access, and optional cross-platform compatibility checks remain distinct from these tests; dated evidence is in [Results and limitations](results-and-limitations.md).

## Off-only attribution execution

### Selected test05 evidence snapshot

The paper selects `runs/h4l-off-test05/evaluation/report`, artifact
`baede583dc2ef36330af1184d266833f3e64a3179fc8d5ce8bff1b6867307cb5`.
The source training batch is `runs/h4l-train-test05/batch/all-seeds`, and preparation
is `runs/h4l-prepare-test05/prepare`. Execution records revision
`c5cdfa8dfab1733ee1cb2c0b4fbca087ab222a4f`; the separate threshold method is
`joint-support-v1`. Full bindings and the frozen snapshot are in
[the evidence index](../paper/result-evidence.md) and
[selection file](../paper/selected-snapshot.json).

The report's aggregate status is `valid`, with 36/36 valid evaluation units and
200/200 valid bootstrap replicas. Scientific qualification remains exploratory,
non-independent and selection-aware-coverage unvalidated. Do not rerun or overwrite
test05 to follow this manual. The following examples use new names and require
eligible sources; a new name does not make the same MC population independent.

| Published table | Interpretation |
|---|---|
| `mass_off_feature_metrics.csv` | 80 nominal candidate/seed rows, width and validation AUC |
| `mass_off_feature_attribution.csv` | Four nominal Shapley summaries; its intervals describe training-seed stability |
| `mass_off_feature_interactions.csv` | All 24 conditional second differences |
| `mass_off_pairwise_comparisons.csv` | All 105 nonempty-subset pairs |
| `evaluation_completeness.csv`, `seed_block_status.csv` | All 36 planned scientific units and retained terminal status |
| `mc_bootstrap_uncertainty.csv` | Finite-MC percentile ranges from the complete replica budget |
| `seed_descriptive_diagnostics.csv`, `five_seed_descriptive_diagnostics.csv` | Conditional per-seed and aggregate Toy/T2 diagnostics |
| `candidate_fit_status.csv` | Candidate-level fit outcomes and failure denominators |
| `report.json`, `provenance.json`, `data_dictionary.json` | Bound aggregate result, source identities and field semantics |

`report.md` is a compact status view, not a replacement for numerical tables.
Some result files are large; paper export selects aggregate fields and verifies
receipts without decoding event data. Preserve local runs and snapshots separately
from Git. Historical test01 paths and bootstrap failures are not current test05
instructions or result sources.

### Reuse checkpoints and publish Stage B

The wrapper audits candidate keys, seeds, ordered inputs, explicit-mass flags,
checkpoints/AUC, core protocol, prepared population and mappings for all 75 source
off models. It creates five deterministic M0off identities without retraining.
`--force` is rejected by the current marginal workflow; it cannot waive compatibility.
An explicit `--prepared-run` may select a differently located, matching source.

```powershell
python scripts/h4l_off_run.py --source-run-name pilot-001 --run-name study-001 --threshold-method joint-support-v1 --stage-b --plan-only
python scripts/h4l_off_run.py --source-run-name pilot-001 --run-name study-001 --threshold-method joint-support-v1 --stage-b
```

The dependency chain is:

```text
source-register -> register -> source-nominal -> nominal
  -> support-j0 -> support-j1 -> evaluation-spec -> freeze
  -> asimov -> evaluation-plan -> report-B
```

`source-register` and `source-nominal` are created by the corresponding adapter
stages. Joint support rebuilds the nominal thresholds/templates on `[105,140]`;
it does not reuse an old median-method nominal artifact under a new label.
G1 requires all 80 identities and an active-bin M0off likelihood-equivalence
certificate. J0/J1 are additional pre-freeze support gates. A failed gate publishes
`gate-failure-report` and prevents freeze; a normal child exit is not a passed gate.

The evaluation specification binds registration, nominal templates, passed gates,
seed blocks, coupling and budgets before freeze. The evaluation plan is a separate
artifact published after Asimov; it binds all five registration/prepared/nominal/
freeze/Asimov IDs without a circular digest. Its path is
`runs/h4l-off-study-001/evaluation-plan/evaluation-plan.json`, not a file fabricated
by editing the generic evaluation example or inferred from `report-B`.

For direct composition, the required middle stages are explicit. These commands
assume registration and nominal already exist and that each destination is fresh:

```powershell
python -m higgsml.cli attribution support-check --registration-run runs/h4l-off-study-001/register --template-run runs/h4l-off-study-001/nominal --gate J0 --run-dir runs/h4l-off-study-001/support-j0
python -m higgsml.cli attribution support-check --registration-run runs/h4l-off-study-001/register --template-run runs/h4l-off-study-001/nominal --gate J1 --j0-run runs/h4l-off-study-001/support-j0 --run-dir runs/h4l-off-study-001/support-j1
python -m higgsml.cli attribution evaluation-spec --registration-run runs/h4l-off-study-001/register --template-run runs/h4l-off-study-001/nominal --j0-run runs/h4l-off-study-001/support-j0 --j1-run runs/h4l-off-study-001/support-j1 --run-dir runs/h4l-off-study-001/evaluation-spec
python -m higgsml.cli attribution freeze --registration-run runs/h4l-off-study-001/register --template-run runs/h4l-off-study-001/nominal --specification-run runs/h4l-off-study-001/evaluation-spec --run-dir runs/h4l-off-study-001/freeze
```

Do not run these again after a wrapper already published their destinations.
Direct later stages derive the threshold method from registration; an explicitly
supplied `--threshold-method` must match. `attribution --help` lists `asimov`,
`evaluation-plan`, `access-review`, evaluation and report arguments. `--plan-only`
reads safe manifests/protocol snapshots, reports unresolved identities and budgets,
and does not open event/assessment payload or grant access.

### Access review and C–E evaluation

The direct `h4l_off_run.py --evaluation` and `h4l_evaluate.py` paths require an
existing bound access receipt. They do not automatically generate or approve one.
Only `h4l_all.py` provides automatic local self-review and adaptation when no
external review is supplied and the declared history permits it. Its receipt
remains `single_researcher_self_review`, `independent=false`.

The current evaluator consumes `h4l-off-assessment-access-v3`, bound to the
specification, evaluation plan, five blocks and the hash of its source review.
The [pending example](../config/examples/h4l_off_assessment_access.pending.json)
has placeholder digests and no complete blocks; it is not executable approval.
For an independently reviewed source package, the source review must establish
exact prepared/population/protocol/freeze bindings, P0/T1 receipts, historical use
and group isolation. P0 definitions and independent numerical comparisons follow
[the applicability schema](../config/schemas/h4l_off_p0_applicability.schema.json).
Schema validity alone cannot establish physical validity or suitable tolerances.

Adapt a reviewed source receipt to the actual Stage B via:

```powershell
python -m higgsml.cli attribution access-review --registration-run runs/h4l-off-study-001/register --template-run runs/h4l-off-study-001/nominal --freeze-run runs/h4l-off-study-001/freeze --result-run runs/h4l-off-study-001/asimov --evaluation-plan runs/h4l-off-study-001/evaluation-plan/evaluation-plan.json --access-review path/to/reviewed-source-access.json --run-dir runs/h4l-off-study-001/access-review
```

Adaptation preserves the source's independence status, checks live history and
publishes a new receipt; it does not invent evidence or consume an assessment
claim. Use an already valid v3 receipt directly rather than adapting it again.
Same-freeze recovery reuses its existing receipt. Missing evidence or conflicting
history blocks evaluation before decoding assessment payload.

```powershell
python scripts/h4l_off_run.py --source-run-name pilot-001 --run-name study-001 --threshold-method joint-support-v1 --evaluation --access-review runs/h4l-off-study-001/access-review/validated-off-assessment-access.json --workers 2 --worker-threads 1
```

The explicit evaluator equivalent can first be inspected without execution:

```powershell
python scripts/h4l_evaluate.py --plan runs/h4l-off-study-001/evaluation-plan/evaluation-plan.json --registration-run runs/h4l-off-study-001/register --prepared-run runs/h4l-prepare-pilot-001/prepare --template-run runs/h4l-off-study-001/nominal --freeze-run runs/h4l-off-study-001/freeze --result-run runs/h4l-off-study-001/asimov --output-root runs/h4l-off-study-001/evaluation --workers 2 --worker-threads 1 --plan-only
```

Execution requires the bound access receipt for assessment/T2. The matrix is one
200-replica event-MC bootstrap, 15 model-self and 15 assessment cells (three
injections × five seeds, 500 Toys per each of 16 candidates), and five T2 cells
(20 outer calibration replicas × 100 inner Toys at mu=1). The final report is the
37th unit. Individual `model-self`, `assessment` and `t2` calls require
`--training-seed 42|43|44|45|46`; MC bootstrap uses the complete 80-identity family.
All evaluation stages bind the generated plan and nominal Asimov source.

### Default marginal CRN evaluation

The wrapper, evaluator and attribution CLI use one common-total monotone marginal
CRN contract. There is no command-line v1/v2/v3 choice; version strings in artifacts
identify immutable schemas and compatibility. Candidate counts share total Poisson
draws and monotone category uniforms within each seed. Their Poisson marginals are
preserved, but `physical_event_pairing=false`. Cross-seed Toy indexes carry no
pairing meaning. Independent-allocation sensitivity remains pending until a bound
budget and its execution exist.

J0 checks nominal marginal support and common totals. J1 checks all 200 group-level
Bernoulli-thinning replicas per seed with zero allowed support failures. They are
template-only engineering screens, not independent physical or interval validation.
T2 validates every outer threshold/support record before inner generation; failed
preflight retains planned denominators and generates no inner Toys for that seed.
Existing population history, including older schema claims, remains binding.

### Resources and recovery

`--workers` bounds complete bootstrap/T2 replicas and supported candidate tasks;
results retain registered order. Windows uses thread workers for MC bootstrap,
assessment candidates and T2 replicas because long-running spawned workers can
fail in `torch_cpu.dll`; other platforms use process workers for those tasks.
The direct default is one worker. On a 16 GiB host start with two and
`--worker-threads 1`; avoid concurrent preparation/training and measure peak memory
before increasing parallelism. `h4l_all.py` chooses its bounded worker count as
described in the main workflow.

`--continue` validates and reuses published stages without changing frozen choices.
Terminal artifacts, including published scientific failures, remain immutable.
Interrupted assessment/T2 claims cannot be silently discarded or allocated a new
random stream. To recompute a specifically selected claimed unit that has no
complete or recoverable terminal after an implementation/infrastructure failure:

```powershell
python scripts/h4l_off_run.py --source-run-name pilot-001 --run-name study-001 --threshold-method joint-support-v1 --evaluation --continue --evaluation-unit t2-mu1-seed42 --retry-failed --access-review runs/h4l-off-study-001/access-review/validated-off-assessment-access.json --workers 2 --worker-threads 1
```

`--retry-failed` requires at least one `--evaluation-unit`. Complete terminals are
skipped. Population, freeze, plan, candidates, stream and budget stay unchanged.
Before payload decoding a durable receipt is stored in
`runs/.h4l-mass-off-v3-recomputations/` and bound into the new terminal. The final
report may be a fresh `report-resume-*` snapshot; use the printed path and verified
bindings instead of assuming `evaluation/report` is always the current report.

### Joint support threshold selection

`h4l_all.py` defaults to `joint-support-v1`. Direct `h4l_off_run.py` and attribution
registration still default to `median-v1`; explicitly select joint support for a
new analysis of the paper's method. Resuming an older run requires its original
method flag. Existing artifacts are not converted automatically.

The [method definition](../config/protocols/h4l_off_joint_support_v1.json) fixes
nineteen calibration quantile proposals, nearest-median feasible selection,
calibration/template weight conventions, support thresholds and `[105,140]` mass
edges. [Methods and evaluation](methods-and-evaluation.md#joint-support-thresholds-used-by-the-paper)
explains the selector. All records bind the separate analysis-contract digest,
model, upstream roles, draw identity, proposals and support diagnostics.

Each bootstrap draw reselects using both resampled roles. T2 reselects with
resampled calibration and fixed template; ordinary Toys keep thresholds fixed.
No feasible cut is a scientific terminal. Incomplete budgets yield null MC
percentile intervals. Even complete test05 remains exploratory with
`selection_aware_coverage=unvalidated` and `primary_claim_eligible=false`.

The optional `scripts/h4l_joint_support_replay.py --output <fresh-path> --workers 4`
uses original local pinned diagnostic inputs, NPZ rows 201–400 plus nominal row 0.
Its 200/200 support and 131 nonmedian selections are historical implementation
consistency checks, not test05 formal replicas or independent validation. It does
not import those draws into an existing analysis or access assessment. Its input
availability is not required for ordinary paper compilation.

## Manuscript reproduction

The formal paper is [paper/latex/main.tex](../paper/latex/main.tex). Six PDF figures
and four generated TeX inputs are committed. Ordinary compilation needs Python's
standard library and a TeX distribution with REVTeX 4.2, BibTeX and latexmk; it does
not read `runs/`, `var/`, `paper/evidence/` or the selected snapshot.

```powershell
python paper/scripts/build.py
```

The wrapper checks missing assets, compiler errors, undefined references, overfull
boxes and stuck floats, then copies the PDF to `paper/latex/main.pdf`. Alternatively,
from `paper/latex/`, `latexmk -pdf -outdir=.build main.tex` writes `.build/main.pdf`.
Author/contact/affiliation/funding placeholders still require author input.

Only intentional evidence/asset refresh requires the ignored local source runs,
NumPy and Matplotlib. The following verifies a fresh extraction against the pinned
selection, regenerates six figures and four TeX inputs, then compiles:

```powershell
python paper/scripts/build.py --run-name test05
```

Review the regenerated asset diff before committing. This is aggregate replay,
not model retraining, likelihood refitting, new Toy generation or new assessment
access. To export a separate aggregate package without editing manuscript assets:

```powershell
python paper/scripts/collect_evidence.py --run-name test05 --output var/paper-evidence/test05-new-check
```

The output must be fresh. Optional repeatable `--path-map OLD=NEW` relocates sources
with longest-prefix precedence; it never changes stored bytes, hashes or identities.
The collector can also use an explicit `--evidence-manifest` to bind a report and
access source. The build wrapper accepts either `--run-name` or `--evidence-manifest`.
Missing required sources or wrong hashes fail closed. It checks selected aggregate
sources and enclosing manifests, not every raw/event/checkpoint payload. See
[paper/README.md](../paper/README.md) for build and archive details. Preserve runs
and snapshots separately; a clean checkout supports compilation from committed
assets but cannot regenerate the underlying scientific evidence by itself.
