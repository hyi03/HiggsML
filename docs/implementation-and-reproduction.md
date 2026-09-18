# Implementation and reproduction

This document connects the [scientific methods](methods-and-evaluation.md) to tools, commands, and persisted contracts. Run all commands from the repository root in a suitable environment. Examples containing placeholder paths require verified upstream artifacts; documenting a command does not establish that its scientific prerequisites have passed.

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

Use Python `>=3.12,<3.13` and the Conda `pytorch` environment. The [environment definition](../environment.yml), [Windows lock](../win.yml), and [macOS lock](../osx.yml) define the environment context; [pyproject.toml](../pyproject.toml) defines the package.

```powershell
conda env create -f environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip install -r requirements.txt
python -m pip check
higgsml --help
```

Create the environment only if it does not already exist. `requirements.txt` supplies the inference additions including pyhf. The optional package extra is `.[parallel]`, containing cloudpickle and threadpoolctl; it is not named `research-parallel`. Serial defaults do not require activating parallel execution. Do not change environment locks merely to make a validation claim pass.

Windows, Linux, and macOS on supported CPU architectures are peer execution platforms; none is an authority requirement. Record the actual platform in provenance when evaluating portability. MELA uses an independently configured Linux/WSL environment, described below.

### Controlled acquisition

```powershell
python scripts/init_data.py --dataset atlas2020_4lep
```

The downloader uses direct HTTPS requests for contracted MC members and publishes the receipt only after size/hash verification. Inputs live under `data/raw/<dataset>/`. Never inspect, hash, preprocess, score, or plot real data. The 2025 downloader option does not change the active H4l dataset.

Controlled preparation additionally requires P0 evidence binding `status=validated`, dataset, protocol digest, source-evidence digest, evidence ID, independent reference, and physical definitions for processes, units, four-vectors, pairing, weights, and selection. Filling in the word `validated` cannot replace that audit. The distinction between acquisition evidence and preparation-time checks is explained in [Data and processing](data-and-processing.md#input-identity-and-access).

## Main workflow

The normal end-to-end path first initializes the controlled dataset and then accepts only one optional workflow argument, `--run-name`:

```powershell
python scripts/init_data.py --dataset atlas2020_4lep
python scripts/h4l_all.py --run-name test01
```

Omitting `--run-name` uses the stable name `default`. Re-running the same command validates published manifests and skips complete stages before continuing at the next missing stage. Invalid final stage directories are quarantined without deleting `.failed` evidence. The wrapper passes `--worker-threads 1` to `h4l_off_run.py` and selects `--workers` from 1--4 using 6 GiB of currently available physical memory per worker, falling back to one worker when memory cannot be detected. Complete bootstrap, Toy, and T2 work units can therefore run in bounded parallelism without nested thread expansion. A pre-existing bound access review is reused; otherwise the command records a local named-user single-researcher self-review, which remains explicitly non-independent and exploratory. Frozen assessment/T2 budget claims are never bypassed by resume. The commands below remain available for diagnosis, explicit planning, independent access-review replacement, and individual-stage recovery.

### Prepare reusable inputs

```powershell
python scripts/h4l_prepare.py --plan-only
python scripts/h4l_prepare.py
```

Defaults bind the 2020 receipt, profile, and H4l protocol, and publish:

```text
runs/h4l-prepare/
  inputs/     ROOT manifest and P0/T1 bindings
  audit/      Source audit
  prepare/    Reusable events.jsonl and manifest
```

Preparation does not train or calibrate. It has `--run-root`, not `--run-name`. Existing directories cannot be overwritten. Progress counts may include entries skipped without application payload requests; selected counts refer to published selected events. `--no-progress` disables progress. `root_prepare_metrics` persists timing regardless of terminal display; `--show-prepare-metrics` adds periodic and final timing, spans, throughput, RSS, and hotspot diagnosis. These are software observations.

For a separate bounded diagnostic, use a fresh directory:

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

The three helpers accept `--protocol`, defaulting to the sole H4l protocol, and propagate it to child stages. `--plan-only` audits planned commands; it does not provide scientific qualification. The standard Asimov batch does not authorize assessment or complete the optional candidate/variation matrix.

### Direct stage composition

```text
audit -> prepare -> [me-export -> me-import] -> train -> calibrate
      -> templates -> freeze -> infer -> [mc-bootstrap] -> report
                                      [evidence-import] ----^
```

For direct CLI calls, provide dataset, explicit protocol, correct upstream runs, and a fresh `--run-dir` under `runs/`. For example, after all relevant preparation gates:

```powershell
higgsml train --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --candidate M2 --seed 42 --run-dir runs/h4l-m2-42
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --model-run runs/h4l-m2-42 --transform physical --run-dir runs/h4l-m4-42
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --model-run runs/h4l-m2-42 --transform raw --run-dir runs/h4l-m2-raw-42
higgsml train --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --gate-run runs/h4l-train-pilot-001/g1 --candidate M3 --groups AB --mass-input off --seed 42 --run-dir runs/h4l-m3-ab-m4l-off-42
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

The unchanged example may be used only to inspect its matrix, not execute a formal experiment. Replace it with the completed plan for execution. Matrix-only planning checks schema/budgets without requiring the local runs to exist or opening assessment; execution checks artifact IDs. The described 25 stages cover one paired fixed-network MC bootstrap, model-self/assessment Toys at 0/1/2, one T2 procedure, sixteen artificial stress cases, and an enhanced report. Failed replicas stay in the original denominators.

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

The performance work reduces repeated computation while preserving scientific rules. Serial ROOT requests use maximum legal spans, identity backfill, and source/entry order. For roughly random development selection at probability p, expected span count is `p+(N-1)*p*(1-p)`; p=0.8 gives mean spans near five entries. Batching therefore does not promise hundreds rather than hundreds of thousands of calls, nor proportional end-to-end speedup.

Templates use a sparse physical-group/bin matrix G: yield is its column sum and covariance is `G.T @ G`. Keep a separate occupancy relation: zero signed contribution does not imply no group. With a merge map A, `G_new=G@A` and `C_new=A.T@C@A`; merged variance includes `2*C[a,b]`. Count groups by union, retain process/category ordering and structural support, and apply the original leftmost-failure merge sequence across all participants.

Calibration caches interval membership/moments but recombines groups and rechecks cross-score-bin restrictions after merging. It does not adopt template weight formulas blindly. Score interpolation is chunked, preserving endpoint, single-slice, ties, and boundary behaviour. Training caches tensors/masks and diagnostic encodings without reducing epoch scoring or threshold recomputation.

`profile_intervals` shares one unconditional MLE across levels; `profile_interval` remains a wrapper. Root searches and per-level failures stay separate. Fixed-POI warm starts are not enabled by default. Toy/T2 computation uses bounded tasks with fixed inputs and ordered collection. The parent owns publication. T2 prerequisite recalibration remains ordered in the parent and consumes inner seeds only after success; workers do not launch another inference pool. Unexpected worker errors propagate to the original failure transaction.

JSONL is streamed with identity-first access. Population digests retain deduplicated, sorted physical-group tuples and original encoding, not file-order hashing. Copied JSONL is revalidated on the final copy. ME lookup, joint-cell projection, stress encodings, auxiliary layout, and fixed-score caches are reused only under matching identities within the call. Upstream hashes are rechecked before publication; stat-only caches cannot replace receipts.

Resources can be supplied through [resources.json](../config/examples/resources.json):

```json
{"workers":1,"worker_threads":1,"root_max_entries":4096}
```

Unknown fields, booleans, nonintegers, and nonpositive values fail. Resources and performance records are in the manifest, with `performance_implementation=research-refactor-v1`; they do not redefine model/mapping scientific identities. CDF/joint-cell temporary arrays use approximately 8 MiB blocks; T2 score caching is bounded near 64 MiB. These are local budgets, not process RSS limits: final tables, results, dense output covariance, and worker runtimes still consume memory.

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

Use a fresh run root. The source model run is read-only and is audited for candidate, seed, exact inputs, mass flag, selected checkpoint/AUC, core protocol, prepared population and calibrated mapping. The registration records allowed-source hashes and timestamps and inspects historical claim metadata without opening assessment payload. Historical detailed diagnostics are optional; missing histories are not fabricated.

```bash
python -m higgsml.cli attribution register \
  --source-root runs/h4l-train-T2/batch/all-seeds \
  --prepared-run runs/h4l-prepare/prepare \
  --t1-validation runs/h4l-train-T2/batch/all-seeds/templates/t1-validation.json \
  --run-dir runs/off-study-001/register
python -m higgsml.cli attribution nominal \
  --registration-run runs/off-study-001/register --run-dir runs/off-study-001/nominal
python -m higgsml.cli attribution freeze \
  --registration-run runs/off-study-001/register --template-run runs/off-study-001/nominal \
  --run-dir runs/off-study-001/freeze
python -m higgsml.cli attribution asimov \
  --registration-run runs/off-study-001/register --template-run runs/off-study-001/nominal \
  --freeze-run runs/off-study-001/freeze --run-dir runs/off-study-001/asimov
python -m higgsml.cli attribution report \
  --registration-run runs/off-study-001/register --template-run runs/off-study-001/nominal \
  --freeze-run runs/off-study-001/freeze --result-run runs/off-study-001/asimov \
  --run-dir runs/off-study-001/report-B
```

The paths must point to actual eligible artifacts. Each stage refuses an existing destination. A Stage B report may be published while later evidence is `not_run` or `pending`. Constant M0off models are embedded in the nominal calibration artifact with individual model IDs and prepared/seed binding; they have no trainable parameters. Nominal G1 requires exactly 80 identities and an active-bin likelihood equivalence certificate. The immutable freeze binds the registration, nominal artifact, mappings, mass grid and budget definition; the later evaluation plan binds the freeze, without a circular digest.

The Stage B report automatically writes `evaluation-plan.json` from the five actual registration/prepared/nominal/freeze/Asimov manifests; no manual ID editing is needed. Every C–E run stores this snapshot, its canonical digest and all five input identities, which report/reuse ingestion checks again. The [off-only evaluation example](../config/examples/h4l_mass_off_evaluation_plan.json) contains unresolved zero IDs for schema illustration only. `--plan-only` reads safe manifests/protocol snapshots, displays the 80 candidates and complete budgets, and reports unresolved identities without opening assessment payload. It does not validate numerical payloads or authorize assessment. Old evaluation v1 remains compatible. The off-only default does not run the legacy stress matrix; additional stress requires separate registration outside this fixed plan.

```bash
python scripts/h4l_evaluate.py --plan runs/off-study-001/report-B/evaluation-plan.json \
  --registration-run runs/off-study-001/register --prepared-run runs/h4l-prepare/prepare \
  --template-run runs/off-study-001/nominal --freeze-run runs/off-study-001/freeze \
  --result-run runs/off-study-001/asimov --output-root runs/off-evaluation-001 \
  --workers 2 --worker-threads 1 --plan-only
```

`--workers` parallelizes complete bootstrap/T2 replicas and complete model-self or assessment candidates while preserving registered draw order. Start with two workers on a 16 GB host and keep `--worker-threads 1`; increase the process count only after measuring peak memory without another prepare or training job running concurrently. The default remains one worker.

Individual `mc-bootstrap`, `model-self --mu 0|1|2`, `assessment --mu 0|1|2` and `t2` stages use the same registration/template/freeze arguments plus `--evaluation-plan runs/off-study-001/report-B/evaluation-plan.json --result-run runs/off-study-001/asimov`. Assessment/T2 additionally require `--access-review` with schema `h4l-off-assessment-access-v1`, exact population/protocol/freeze binding, independent P0/T1 file receipts, explicit historical-use and group-isolation review. P0 must satisfy [the applicability schema](../config/schemas/h4l_off_p0_applicability.schema.json): its recomputed `package_id` hashes the package without that field; dataset, prepared, protocol, freeze, template and original P0 source-file hash must match. Each physical definition has nonempty referenced content and a typed, finite expected/actual numerical comparison within declared tolerances. Source files have verified receipts and an independent producer/reference/basis. The schema checks evidence structure and bindings; independent human review must establish physical validity and acceptable tolerances. T1 uses the existing independent evidence package contract. Missing evidence is `assessment_qualification_pending`; an automatic reference or a new freeze name cannot restore independence. The original prepared run's `.research-claims` root owns exclusive per-cell budget claims; a failed or interrupted claimed cell is not rerun automatically.

### Default marginal CRN evaluation

The off-only wrapper, evaluator and attribution CLI use the registered
common-total monotone CRN coupling by default. The version selector has been
removed. Each candidate keeps its two-category Poisson marginal law; paired
errors are conditional diagnostics under an artificial coupling, with
`physical_event_pairing=false`. Legacy labels qualify only aggregate
signal/background support, not separate physical-process support. Independent
allocation sensitivity is reported as pending until authorized and executed.

J0 and all 200 J1 group-thinning replicas per seed must pass before freeze.
T2 preflights every outer mapping/support record before any inner generation.
Failed preflight preserves the planned denominator and generates zero inner
Toys for that seed. Existing assessment history remains binding, including
receipts written by older workflow versions.

Use a fresh run name and existing compatible training/prepared artifacts:

```bash
python scripts/h4l_off_run.py \
  --source-run-name test01 --run-name marginal-v3-001 --stage-b --show-command
```

Stage B publishes `source-register`, `register`, `source-nominal`, `nominal`,
J0, J1, `evaluation-spec`, `freeze`, `asimov`, `evaluation-plan` and `report-B`.
Neither support gate reads assessment. Full evaluation requires an unused
eligible source. The one-command wrapper creates a bound, explicitly
non-independent local self-review when no external receipt is supplied, then
continues through all 36 units and the final report. Pass an independently
reviewed receipt to replace that exploratory default:

```bash
python scripts/h4l_off_run.py \
  --source-run-name fresh01 --run-name marginal-001 --evaluation \
  --access-review path/to/validated-off-assessment-access.json --show-command
```

For the complete automatic path, including local self-review and access
adaptation, run `python scripts/h4l_all.py --run-name fresh01`. Outputs from
that default path remain `single_researcher_self_review`, `independent=false`,
and exploratory. The wrapper never upgrades them to independent evidence.

The evaluator runs 36 scientific units and one report. Use claim-aware
`--continue` for interrupted work; consumed assessment/T2 budgets are never
replayed. The schema filenames under `config/schemas/` are unversioned defaults,
while schema IDs inside immutable artifacts remain versioned. Software and
synthetic checks do not establish controlled-MC qualification.
