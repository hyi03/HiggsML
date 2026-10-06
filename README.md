# HiggsML: An MC-only research workflow for H → ZZ* → 4l

This repository maintains an **MC-only educational and technical research workflow** for `H -> ZZ* -> 4l`. The active paper compares all 15 nonempty A/B/C/D kinematic feature subsets for seeds 42–46, reusing 75 classifiers without explicit `m4l` and five deterministic `M0off` identities. It studies nominal signal-strength interval widths, feature-group contributions and complementarity, and training-seed stability. Bound protocols, immutable artifacts, and assessment isolation until after freezing make the workflow auditable.

This README reflects the repository documentation and entry points reviewed on **2026-10-06**. The paper still selects the test05 evidence reviewed on **2026-09-26**; the documentation update does not execute or requalify an analysis.

Repository outputs are not official ATLAS/CMS results, a Higgs discovery, or a physics measurement. Software implementation, synthetic tests, full-MC validation, and independent matrix-element references are distinct evidence levels and cannot substitute for one another. Supported platforms and CPU architectures have equal standing; none has greater scientific authority.

## 1. Understand the project scope and evidence status

- The only active code is the H4l package under `src/higgsml`; legacy15 preprocessing, the old training/testing workflow, and XGBoost implementations have been removed.
- The default study uses the controlled `atlas2020_4lep` MC sample pair, with the protocol-defined `2e2mu` final state and a mass range of 105–140 GeV.
- The active off-only paper uses raw classifier scores and the separately bound `joint-support-v1` method. Software also supports `mass-only`, `decay7`, `engineered19`, `lab-extension`, independently retrained explicit-`m4l` on/off controls, ordinary/adversarial training, conditional CDFs, common mass/score templates, T0/T1 inference, and sample-efficiency studies. Those supporting implementations are not completed results of the active paper.
- The current paper selects test05 through [`paper/selected-snapshot.json`](paper/selected-snapshot.json): 80/80 nominal candidate/seed results, 36/36 evaluation units, and 200/200 event-MC bootstrap replicas are numerically valid. The report is in the locally ignored directory `runs/h4l-off-test05/evaluation/report`, and the aggregate snapshot is in `var/paper-evidence/test05-20260926/`; neither is published through Git. The result is registered as `exploratory_posthoc`, with assessment access review `independent=false`, `selection_aware_coverage=unvalidated`, and `primary_claim_eligible=false`. It supports exploratory technical analysis in the paper, but must not be described as a confirmed precision gain or a physics measurement.
- MELA currently provides only export/import contracts and an optional adapter contract; the actual backend and independent physical reference still require validation.

For the identities, numerical results, and limitations of the current paper, see the [paper evidence index](paper/result-evidence.md) and [Results and limitations](docs/results-and-limitations.md#h4l-off-test05-controlled-mc-result). For the research design and general methods, see [Research design](docs/research-design.md). Historical test01 results and synthetic performance records retain their original meaning and are not the numerical source for the current paper.

The test05 [`joint-support-v1`](config/protocols/h4l_off_joint_support_v1.json) method explicitly uses one mass bin over 105–140 GeV: nonempty feature combinations use two score categories, while `M0off` is an inclusive-count reference. `W68` is the nominal T1 model-self Asimov 68% interval width at injected `mu=1`. The five-seed median nominal `W68` values for BC, AC, ABCD, and M0off are 1.511617, 1.515244, 1.535930, and 1.663723, respectively. The nominal Asimov intervals for BC and AC are approximately 9.14% and 8.92% narrower than the reference; the 95% finite-MC paired difference ranges for both versus the full ABCD combination include zero. This comparison does not use a resolved mass peak, and removing the explicit mass column does not exclude implicit mass information in correlated kinematics. Interval coverage under low counts and the entire threshold-selection procedure still require independent calibration; nominal gains must not be interpreted as confirmed precision improvements.

The 200 event-MC bootstrap replicas hold trained networks fixed. Their percentile ranges do not include independent retraining or calibrated post-selection uncertainty, and five-seed ranges are not confidence intervals. Independent signed-MC/T1 applicability validation, whole-procedure coverage calibration, category-allocation sensitivity, and independent confirmation remain separate requirements.

The core protocol's `protocol_scope` remains `synthetic_software_defaults_not_physics_validation`; completing a run does not change this applicability limitation.

The feature groups contain 19 inputs in total:

| Group | Inputs | Count |
|---|---|---:|
| A | `lep1_pt` through `lep4_pt`, `lep1_eta` through `lep4_eta` | 8 |
| B | `mZ1`, `mZ2`, `deltaR_Z1`, `deltaR_Z2` | 4 |
| C | `pt4l`, `deltaPhi_ZZ` | 2 |
| D: Angular5 | `cos_theta_star`, `cos_theta_1`, `cos_theta_2`, `phi_decay_planes`, `phi_production_plane` | 5 |

Leptons are ordered by transverse momentum. `m4l` is outside these groups and is omitted from the active classifiers; BC has six off inputs, AC ten, and ABCD nineteen. `M0off` has a constant score of 0.5 and is not a trained empty classifier. Definitions, units, angular conventions, and information limits are in [Data and processing](docs/data-and-processing.md#features-and-information-content).

## 2. Explore the repository layout

```text
src/higgsml/       H4l package: physics reconstruction, modeling, inference, and sample efficiency
config/            Dataset contracts, profiles, protocols, schemas, and examples
scripts/           Controlled download, main workflow, and research helper scripts
tests/             Unit, workflow, and synthetic scientific-contract tests
docs/              Methods, reproduction, artifacts, and validation documentation
  methods/         Detailed joint-support and marginal CRN designs
  studies/         Supporting study records and unexecuted confirmation proposals
  history/         Dated implementation, review, and verification records
paper/             LaTeX manuscript, committed figures and TeX numerical tables, evidence index
data/raw/          Local controlled MC inputs (ignored; do not commit)
runs/              Local immutable run artifacts (ignored; do not commit)
var/               Local aggregate paper snapshots and other derived evidence (ignored; do not commit)
```

## 3. Configure the environment and install the project

The project requires Python `>=3.12,<3.13` and uses the Conda `pytorch` environment by repository convention.

If the environment does not already exist, create it from the environment definition:

```bash
conda env create -f environment.yml
```

Activate the existing or newly created environment, install the package, and add the inference dependencies (including `pyhf`):

```bash
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip install -r requirements.txt
python -m pip check
```

Parallel inference uses the optional dependencies `cloudpickle` and `threadpoolctl`, installed with `python -m pip install -e ".[parallel]"`. Serial execution does not require enabling parallelism; run `python -m pip check` after installation to check dependencies.

`win.yml` and `osx.yml` are existing Windows and macOS environment snapshots, while `environment.yml` provides a general environment definition; none establishes an authoritative platform requirement. The project can run on Windows, Linux, or macOS and on different CPU architectures where its dependencies are available. The MELA backend requires a separately configured Linux/WSL environment.

After installation, the common core entry point is:

```bash
higgsml --help
```

## 4. Download and verify the controlled MC dataset

The downloader uses only the fixed HTTPS requests in the dataset contract and publishes a receipt after all file sizes and SHA-256 hashes match:

```bash
python scripts/init_data.py --dataset atlas2020_4lep
```

Inputs are written to `data/raw/<dataset>/`. The downloader also recognizes `atlas2025_exactly4lep`, but it belongs to a separate release/collection and must not be mixed with 2020 files; the current formal H4l protocol and workflow remain bound to `atlas2020_4lep`. No stage may read or process real data.

Dataset contracts are located at:

- [`config/datasets/atlas2020_4lep.json`](config/datasets/atlas2020_4lep.json)
- [`config/datasets/atlas2025_exactly4lep.json`](config/datasets/atlas2025_exactly4lep.json)

## 5. Run the H4l workflow

After initializing the controlled dataset, review prepare, G1, the five-seed batch, off-only Stage B, C–E evaluation, and the final report through a read-only plan, then execute:

```bash
python scripts/h4l_all.py --run-name planned-joint-001 --threshold-method joint-support-v1 --plan-only
python scripts/h4l_all.py --run-name planned-joint-001 --threshold-method joint-support-v1
```

`planned-joint-001` is an example of a new name; do not rerun or overwrite test05 to follow this example. A new name does not give an already accessed MC population independent qualification.

`--plan-only` does not launch child tasks, write run artifacts, or open event or assessment values. Without a prepared manifest, it returns only `pending_prepare_identity`, which is not clearance to use a new population. Remove this option for an actual full run; adding `--stage-b-only` stops after validating the Stage B plan and report, without generating access reviews or starting evaluation.

`--run-name` is used for the prepare, train, and off-only directories. `h4l_all.py` defaults to the `joint-support-v1` threshold method and explicitly forwards the selected method to Stage B and evaluation. To resume an existing `median-v1` run, pass `--threshold-method median-v1`; execution is rejected if the method does not match the registration, and old artifacts are not converted automatically. Direct `h4l_off_run.py` execution and attribution registration default to `median-v1`, so explicitly pass `--threshold-method joint-support-v1` for the paper method. `--access-review` accepts an explicit review file whose qualification depends on its contents and bindings. Omitting the run name uses `default`:

```bash
python scripts/h4l_all.py
```

Repeating the same command automatically checks progress. Stages with consistent bindings and complete manifests are skipped; missing stages continue. Corrupt, incomplete, or mismatched final directories are preserved as `.name.<uuid>.invalid` before the current stage is attempted again, and existing `.failed` evidence is not deleted. If assessment/T2 already has a claim but lacks a complete or recoverable terminal state, automatic reruns are still rejected by default; explicitly recompute the unit with `--evaluation-unit <unit> --retry-failed`. The original claim is preserved, the retry receipt and final artifact record this attempt, and other complete units are not recomputed.

The wrapper passes `--worker-threads 1` to `h4l_off_run.py` and selects `--workers` between 1 and 4 from installed physical memory, reserving 2 GiB for local scheduling/system overhead and budgeting 5 GiB per worker; if memory detection fails, it uses 1 worker. A 16 GiB host therefore starts only 2 workers. This budget covers transient peaks when pyhf/SciPy fitting overlaps with result serialization. On Windows, MC bootstrap replicas, assessment candidates, and T2 replicas use thread workers to avoid crashes in `torch_cpu.dll` in long-running spawned Python processes; other platforms use process workers. Parallelizable full bootstrap, Toy, and T2 units retain their registered order, while Stage B registration, templates, freeze, and Asimov stages follow dependency order.

Access history is declared centrally in [`config/h4l_history_roots.json`](config/h4l_history_roots.json), which currently scans only this repository's `runs/`. Preflight and new runs can proceed when the directory is empty or does not yet exist, without relying on archives in `var/`. Corrupt existing `runs/` history, or a different freeze already claiming the same population, still blocks a full run. This scan cannot establish the absence of access history in other directories or on other machines; renaming, repeating prepare, or changing directories does not create an independent population. New self-review v2 records the actual scope checked and a configuration summary and always has `independent=false`. Resuming the same freeze still requires an existing, validly bound access receipt.

Completion checks verify all 36 scientific terminal units, terminal summaries and their hashes, and the bound report (the 37th unit), then print the actual report path (which may be `report-resume-*`). Wrapper exit code `5` indicates preflight or gate blocking, `6` indicates incomplete execution artifacts, and `0` indicates that execution completed for the requested scope (or that the read-only plan encountered no block). Published numerical failures can be terminal: `execution_status=complete` can coexist with `scientific_status=incomplete`. Even with exit code `0`, inspect the separate `scientific_status`; numerically valid output remains exploratory and does not establish independent scientific validation. Physical weights and interval algorithms retain their existing definitions. `m4l=off` only means the classifier does not receive explicit four-lepton mass; the likelihood still retains a mass coordinate. For full stage contracts, manual independent review, and recovery restrictions, see [Implementation and reproduction](docs/implementation-and-reproduction.md).

The formal paper is available as [LaTeX source](paper/latex/main.tex). Its six PDF figures and four generated TeX inputs are committed to Git; ordinary compilation requires no local run artifacts, figure-generation scripts, or `paper/evidence/`:

```bash
python paper/scripts/build.py
```

To explicitly refresh the current paper's figures and tables, run `python paper/scripts/build.py --run-name test05`; this requires the corresponding local `runs/`, NumPy, and Matplotlib. The command verifies the pinned selection before rebuilding six figures and four TeX inputs; review the generated-file diff. An ordinary build requires only Python's standard library and a TeX environment with REVTeX 4.2, BibTeX, and latexmk. It does not read `runs/`, `var/`, `paper/evidence/`, or the selection file. You can also run `latexmk -pdf -outdir=.build main.tex` directly in `paper/latex/`. The PDF is written to `paper/latex/main.pdf` (or `.build/main.pdf` when running latexmk directly). The wrapper rejects undefined references, overfull boxes, and stuck floats. Author, contact, affiliation, and funding placeholders still require author input. For details, see the [paper build instructions](paper/README.md).

To export a separate aggregate snapshot into a fresh directory without retraining, refitting, generating Toys, or opening new assessment data:

```bash
python paper/scripts/collect_evidence.py --run-name test05 --output var/paper-evidence/test05-new-check
```

The collector checks selected aggregates and manifest links, not every checkpoint, event, or raw payload. Preserve the original source runs and `var/paper-evidence/test05-20260926/` separately from Git; the committed manuscript assets suffice for ordinary compilation.

## 6. Run the H4l workflow by stage

The off-only analysis entry point is `python -m higgsml.cli attribution --help`. It reuses the 75 off models from the five-seed batch, adds five deterministic M0off identities, and publishes registration, common templates, freeze, Asimov, event bootstrap, Toys, T2, and the final report in sequence. For complete commands, see [off-only attribution execution](docs/implementation-and-reproduction.md#off-only-attribution-execution). Reusing existing models does not require retraining for the same analysis; a new independent confirmatory study requires a separate design.

`m4l=off` only means the classifier does not receive explicit four-lepton mass; the likelihood still retains a mass coordinate. Automatically emitted P0/T1 v2 materials have `status=contract_checked` and do not establish independent numerical validation, physical applicability, or confirmatory eligibility. Event bootstrap, Toys, T2, and external-reference status are stored separately.

Run the following commands from the repository root. `example01` and `study-001` are examples of new run names. For complete rules, gates, and recovery procedures, refer to [Implementation and reproduction](docs/implementation-and-reproduction.md) and each command's `--help`.

### 6.1 Prepare and persist reusable inputs

```bash
python scripts/h4l_prepare.py --run-name example01
```

The script executes `audit` and `prepare`, using these defaults:

- Receipt: `data/raw/atlas2020_4lep/dataset_receipt.json`
- Profile: `config/profiles/open_data_2020.yaml`
- Protocol: `config/protocols/h4l_protocol.json`
- Output root: `runs/h4l-prepare-example01/`

The reusable prepared artifact is located at `runs/h4l-prepare-example01/prepare`. The script does not continue to training, calibration, or template construction. Use `--diagnostic-entries-per-file` when a bounded-workload performance diagnostic is needed first; diagnostic artifacts cannot serve as G1 inputs.

The named prepare root has this structure:

```text
runs/h4l-prepare-example01/
├── inputs/    ROOT manifest and P0/T1 binding evidence
├── audit/     Source audit artifacts
└── prepare/   events.jsonl and prepared manifest
```

`h4l_prepare.py --run-name <name>` shares the same short name with G1, training, and off-only stages. `--run-name` cannot be combined with `--run-root`; omitting `--run-name` retains the old default directory `runs/h4l-prepare/` for compatibility with explicit-path workflows.

### 6.2 Run gate checks

```bash
python scripts/h4l_check.py --run-name example01
```

The gate runs M0c, M2, M3, five calibrations, and common templates from the global prepared artifact. Gated candidates can be expanded only after the gate passes. Failed directories remain immutable evidence; after a fix, use a new `--run-name` or `--output-root`.
The experiment output root for `--run-name example01` is `runs/h4l-train-example01/`.

### 6.3 Run the formal five-seed batch

```bash
python scripts/h4l_run.py --run-name example01
```

The default batch executes registered candidates, calibration, common templates, T1 `mu=1` inference, and reporting for seeds 42–46. Explicit `--seed 42` is only a single-seed diagnostic and cannot support the main five-seed comparison.

After a batch is interrupted, resume with `--continue`: valid complete stages are skipped; incomplete, corrupt, or mismatched final stage directories are first quarantined as `.name.<uuid>.invalid`, then retried once. Existing `.failed` evidence is not deleted.

```bash
python scripts/h4l_run.py --run-name example01 --continue
```

All three scripts support `--help`, `--plan-only`, `--no-progress`, and validated `--continue`. Completed, failed, diagnostic, or published runs must be preserved; recovery must use the continuation contract, and new diagnostics require new directories. `--clean` deletes local artifacts and cannot be used to bypass immutable evidence or assessment history during recovery.

### 6.4 Run Stage B to produce a freeze

```bash
python scripts/h4l_off_run.py --source-run-name example01 --run-name study-001 \
  --threshold-method joint-support-v1 --stage-b
```

Run Stage B first to produce a freeze and an automatically bound evaluation plan. Direct off-only planning uses `--plan`, rather than the full wrapper's `--plan-only`.

The joint-support selector proposes 19 calibration-background quantile cuts, checks signed-yield support in both calibration and template roles, and chooses the feasible cut nearest the median. It does not optimize AUC or `W68`. All 75 test05 nominal selections use the median. For support rules, tie-breaking, resampling, and identities, see the [joint-support design](docs/methods/h4l-off-joint-support-v1.md).

`scripts/h4l_off_run.py` directly reuses the complete five-seed batch specified by `--source-run-name` and its corresponding `runs/h4l-prepare-<source-run-name>/prepare`, without repeating prepare or training. It automatically checks the prepared artifact, population, core protocol, and the candidate, seed, checkpoint, and upstream bindings of all 75 `m4l=off` training/calibration artifacts; reuse is rejected if any identity does not match.

The default marginal CRN workflow requires exact agreement of source protocols; `--force` cannot bypass compatibility review.

### 6.5 Review assessment access

After Stage B completes, assessment/T2 can use only an access-review bound to the actual freeze, population, protocol, and P0/T1 files. The current evaluator consumes an `h4l-off-assessment-access-v3` receipt, which must also bind the evaluation specification, plan, five seed blocks, and source-review summary. The [pending example](config/examples/h4l_off_assessment_access.pending.json) contains placeholder IDs and lacks complete blocks, so it cannot be used directly.

An independent reviewer must supply actual source-review materials covering historical access, event-group isolation, and applicability evidence, then bind them to the actual Stage B through this command:

```bash
python -m higgsml.cli attribution access-review \
  --registration-run runs/h4l-off-study-001/register \
  --template-run runs/h4l-off-study-001/nominal \
  --freeze-run runs/h4l-off-study-001/freeze \
  --result-run runs/h4l-off-study-001/asimov \
  --evaluation-plan runs/h4l-off-study-001/evaluation-plan/evaluation-plan.json \
  --access-review path/to/reviewed-source-access.json \
  --run-dir runs/h4l-off-study-001/access-review
```

Binding checks live access history and preserves the source's independence status; it does not fabricate independent evidence. An existing valid v3 receipt can be used directly; resuming the same freeze requires reusing the existing receipt. Only `h4l_all.py` provides an automatic local self-review when history permits, and its result is always non-independent, exploratory material.

### 6.6 Generate the final report

After binding the required access review, execute; eligibility for an independent claim depends on the review's actual evidence and independence:

```bash
python scripts/h4l_off_run.py --source-run-name example01 --run-name study-001 \
  --threshold-method joint-support-v1 --evaluation \
  --access-review runs/h4l-off-study-001/access-review/validated-off-assessment-access.json
```

This command reads and binds the actual prepared, registration, nominal, freeze, and evaluation-plan artifacts, then performs C–E evaluation and generates the final report. It does not automatically generate or approve an access-review.

The script completes registration, common nominal templates, freeze, Asimov, event bootstrap, three groups of model-self Toys, three groups of controlled assessment Toys, T2, and the final report in sequence. Stage B uses a fresh directory; `--evaluation` reuses that Stage B and refuses to overwrite an existing evaluation. If the source batch does not yet exist or is incomplete, first use `scripts/h4l_run.py` to produce a new complete five-seed batch. For detailed stage contracts and recovery rules, see [off-only attribution execution](docs/implementation-and-reproduction.md#off-only-attribution-execution).

### 6.7 Default marginal CRN evaluation

```bash
python scripts/h4l_off_run.py \
  --source-run-name example01 --run-name marginal-v3-001 \
  --threshold-method joint-support-v1 --stage-b
```

The default workflow uses artificial CRN coupling with common totals and monotone category allocation, preserving each candidate's marginal Poisson distribution; it does not represent joint pairing of physical events. J0/J1 must pass before freezing, and previously opened assessment does not regain eligibility as a result. The command line no longer offers v1/v2/v3 version selection; version fields in existing artifacts remain identifiers for immutable evidence. For the full contract, see [Implementation and reproduction](docs/implementation-and-reproduction.md#default-marginal-crn-evaluation).

The 36-unit scientific matrix contains one 200-replica event-MC bootstrap; model-self and assessment cells at `mu=0,1,2` for each of five training seeds, with 500 Toys per candidate per cell; and five T2 cells at `mu=1`, each with 20 outer calibration replicas and 100 inner Toys. T2 inner fits are conditional on their outer replicas and must not be treated as independent repetitions of the whole procedure. The [marginal CRN design](docs/methods/h4l-off-marginal-coupling-v3.md) records the probability, stream, and support contracts; independent category-allocation sensitivity remains pending.

### 6.8 Explore the separately registered sample-efficiency study

Sample efficiency is a supporting study with its own compact-candidate freeze, training subsets, registration, controls, and confirmation. Its classifiers receive explicit `m4l`; the off-only BC/AC results do not select a compact candidate or complete its registration. The checked-in overlay contains null choices and the example configurations contain placeholder paths, so they are not executable formal experiments without completed bindings.

The independent script entry points are:

```bash
python scripts/h4l_learning_curve.py --help
python scripts/h4l_sample_efficiency_report.py --help
python scripts/h4l_sample_efficiency_controls.py --help
```

See [Sample efficiency](docs/sample-efficiency.md) for prerequisites and registration. The current paper reports one training budget, not learning curves, capacity-matched controls, or independent compact-candidate noninferiority.

## 7. Use the project tools for research

`higgsml` exposes twelve core composable stages, plus dedicated `attribution`, `sample-efficiency`, `sample-efficiency-report`, and `sample-efficiency-controls` entry points:

```text
audit -> prepare -> [me-export -> me-import] -> train -> calibrate
      -> templates -> freeze -> infer -> [mc-bootstrap] -> report
                                      [evidence-import] ---^
```

```bash
higgsml train --help
higgsml calibrate --help
higgsml templates --help
higgsml infer --help
higgsml mc-bootstrap --help
higgsml evidence-import --help
```

Direct stage calls must explicitly bind the dataset, `config/protocols/h4l_protocol.json`, upstream runs, and a fresh output directory under `runs/`. Orchestration scripts automatically pass this single default protocol; `higgsml` subcommands still require explicit `--protocol`. `manifest.json` records the dataset, protocol snapshot, upstream artifacts, file digests, code/environment, random seeds, and scientific terminal state; model JSON stores only numerical tensors and does not load executable pickle. For detailed fields, see the [artifact and lineage contract](docs/implementation-and-reproduction.md#artifact-and-lineage-contract).

The final `report` accepts repeated `--training-run`, `--evaluation-run`, and `--evidence-run` arguments, while `--result-run` continues to carry the main inference result. In addition to `report.json`/`report.md`, the enhanced report publishes full-precision UTF-8 CSV files, `analysis_records.jsonl` with logical rows for each table, `provenance.json`, and `data_dictionary.json`. `models.csv` and `feature_metrics.csv` explicitly record the selected checkpoint's validation absolute-weight AUC and its absolute AUC difference from M0c for the same seed; training and inference status are stored separately. Old runs remain unchanged and can serve as explicit upstream inputs for a new report directory.

Registered statistical evaluation uses a separate script:

```bash
python scripts/h4l_evaluate.py --help
python scripts/h4l_evaluate.py --plan config/examples/h4l_evaluation_plan.json \
  --prepared-run runs/... --template-run runs/... --freeze-run runs/... \
  --output-root runs/h4l-evaluation-001 --plan-only
```

The example plan is an `exploratory_posthoc` template whose three input artifact IDs are zero-valued placeholders that must be replaced; it cannot be executed directly as a formal registered plan. Actual execution checks prepared/template/freeze artifact IDs, protocol digests, and Toy/T2 budgets; plan mode only audits the matrix and does not open assessment. External signed-MC/T1 materials, physical systematic variations, and MELA materials are incorporated read-only through `evidence-import`; missing materials must retain `external_pending` status.

## 8. Follow scientific and operational constraints

- Process only controlled MC or explicitly labeled synthetic events; never read, hash, preprocess, score, or plot real data.
- Use `m4l` only as defined by the versioned H4l protocol; signed `physical_weight` is for physical yields, while optimizer weights follow the protocol.
- Keep each physical event group within the same split/fold; do not mix the responsibilities of train, validation, calibration, template, and assessment roles.
- Access assessment only after the protocol-defined frozen state; results must not feed back into candidate, threshold, binning, mapping, or protocol adjustments.
- Preserve dataset identities, SHA-256 hashes, protocol seals, checkpoints, upstream bindings, and lineage.
- Passing software tests establishes only the corresponding software behavior; it does not establish improved `mu` precision, reliable coverage, or full-MC scientific conclusions.

## 9. Validate code, dependencies, and the environment

Run from the repository root:

```powershell
python -m compileall -q src scripts tests
python -m pytest -q
python -m pip check
```

## 10. Browse project documentation

Start with the [documentation index](docs/README.md), then choose the reading path for your task:

| Topic | Current documentation |
|---|---|
| Questions, candidate families, and study scope | [Research design](docs/research-design.md) |
| Controlled samples, selections, features, weights, and roles | [Data and processing](docs/data-and-processing.md) |
| Training, calibration, templates, likelihoods, and uncertainty | [Methods and evaluation](docs/methods-and-evaluation.md) |
| Commands, architecture, bindings, and recovery | [Implementation and reproduction](docs/implementation-and-reproduction.md), [module architecture](docs/implementation-and-reproduction.md#tools-and-architecture), and [artifact and lineage contract](docs/implementation-and-reproduction.md#artifact-and-lineage-contract) |
| Numerical results and claim boundaries | [Results and limitations](docs/results-and-limitations.md), [evidence requirements](docs/results-and-limitations.md#evidence-required-for-conclusions), and [software/validation status](docs/results-and-limitations.md#software-and-validation-status) |
| Separately registered training-size study | [Sample efficiency](docs/sample-efficiency.md) |
| Manuscript evidence and compilation | [Paper evidence index](paper/result-evidence.md), [pinned selection](paper/selected-snapshot.json), [build instructions](paper/README.md), and [LaTeX source](paper/latex/main.tex) |

Detailed designs, study records, and historical verification were reorganized on **2026-10-06**:

| Location | Contents and interpretation |
|---|---|
| `docs/methods/` | [Joint-support threshold design](docs/methods/h4l-off-joint-support-v1.md) and [marginal CRN design](docs/methods/h4l-off-marginal-coupling-v3.md); detailed contracts with scope notes on historical defaults |
| `docs/studies/` | [Statistical validation](docs/studies/statistical-validation-20260923.md), [physics and baseline audit](docs/studies/physics-baseline-audit-20260923.md), and [confirmation draft](docs/studies/confirmation-design-20260923.md); dated findings and outstanding proposals, including a non-executable off-only confirmation design separate from sample efficiency |
| `docs/history/` | [Evidence alignment](docs/history/evidence-alignment-20260923.md), [entry hardening](docs/history/h4l-entry-hardening-20260924.md), [joint-support implementation](docs/history/h4l-off-joint-support-v1-verification-20260922.md), and [marginal CRN implementation](docs/history/h4l-off-marginal-coupling-v3-verification-20260918.md); historical implementation and review evidence |

Implementation plans and review decisions were consolidated into the corresponding historical records. The migration did not create a scientific contract, confirmation registration, or assessment clearance. Historical test counts are not current test runs. Code defines implemented behavior; versioned contracts and run snapshots define the executed analysis; published artifacts establish numerical results.

## 11. License and third-party terms

See [`LICENSE`](LICENSE). Third-party data, software, and experimental materials remain subject to their respective licenses and terms of use.
