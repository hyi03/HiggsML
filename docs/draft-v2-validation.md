# Draft-v2 supplemental statistical evaluation

This independent workflow binds an existing completed draft-v2 source run. It
reuses its prepared population, fifteen frozen networks and thresholds, nominal
sixteen templates, and report-selected evaluation artifact. It never retrains,
changes the 60/20/20 allocation, selects a checkpoint, or updates manuscript
assets. The nominal wrapper does not invoke these stages.

All results retain `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, and `primary_claim_eligible=false`.
Software tests use labelled synthetic data. Completing this workflow does not
establish physical applicability or independent numerical validation, and is
not an ATLAS/CMS result, Higgs discovery or physics measurement.

## Fixed design

The independent contract is
[`h4l_draft_v2_validation_v1.json`](../config/protocols/h4l_draft_v2_validation_v1.json).
The original training contract is separately retained and checked. Public
entry points reject shortened budgets, altered injections, or promoted labels.

| Stage | Fixed inputs | Repeated changes | Budget |
|---|---|---|---:|
| Fixed-threshold bootstrap | Selected checkpoints and nominal cuts | Evaluation physical groups | 200 |
| Refitted-threshold bootstrap | Selected checkpoints and cut rule | Independent validation groups and the same evaluation draw | 200 |
| Model-self | Nominal T1 templates and thresholds | Poisson main counts and regenerated auxiliary observations | 500 per model at each of mu=0,1,2 |

Each bootstrap role samples uniformly with replacement from **all sorted
physical event groups**, retaining its original group count. This is an
unstratified multinomial draw; signed weights are never probabilities. All
models and training seeds share the same multiplicities. Validation and
evaluation streams are independent; the two modes share evaluation draws.
There is one inclusive reference per replica, shared by both modes: 31 interval
computations per replica, or 6,200 planned interval groups. Physical yields keep
`physical_weight / 0.2`; no replicate-specific yield normalization is applied.

Refitted thresholds use the first sorted validation-background score reaching
half the resampled **absolute physical weight**. Ties stay together and
`score >= threshold` defines the high category. Thresholds remain local to the
replica and never overwrite source models or freeze. For each deletion, subtract
ABCD within each seed, then take the median of those three differences. Formal
16/84 and 2.5/97.5 percentile ranges require all three seeds in every one of the
200 replicas. Direction flips are strict sign reversals relative to the nominal
median difference; a zero nominal value leaves this diagnostic undefined.

### Fixed-model threshold diagnostics (second implementation batch)

The bootstrap already computes both threshold modes within each paired replica.
The `paired-threshold-diagnostics-v1` reporting extension uses those published
aggregates and the frozen nominal cuts; it adds no resampling, event reads,
model inference or likelihood fits. Existing unit budgets and RNG identities
remain unchanged. Regenerate the report with `report --continue` to publish an
updated aggregate while preserving the original report and unit artifacts.

For each of the fifteen models, `thresholds.csv` records the nominal threshold,
refitted threshold, signed difference, exact-change flag and both mode statuses.
`threshold-summary.csv` reports the change fraction, lower/higher counts, median
difference and 2.5/16/84/97.5 percentiles. A change means an exact difference
between empirical score thresholds; it is not an optimization tolerance.
Formal threshold summaries require all 200 estimates. `threshold-shifts.png/pdf`
shows the available differences around zero, with availability labelled; the
absolute-threshold plot retains the frozen threshold as a dashed reference.

Two yield differences have distinct meanings:

- `category-yield-changes.csv`: refitted replica minus nominal. This includes
  both evaluation resampling and the change of threshold.
- `paired-category-yield-changes.csv`: refitted minus fixed threshold **on the
  same evaluation draw**. This isolates signed yield redistribution between the
  two categories for that draw. Low/high changes sum to zero per process, up to
  floating-point error. Negative weights remain signed and are not clipped.

Paired yields remain descriptive when a support check or fit fails; the two
statuses accompany every comparison. Missing comparisons are blank, not zero.
Threshold-estimation failures are counted separately from downstream support
failures. Both planned-denominator failure rates require all 200 terminals;
`support_assessed_replicas` also records how many thresholds were available for
support checking. A missing threshold makes its support result unavailable,
not a successful support check. None of these diagnostics reselects a checkpoint,
changes the original cut or establishes whole-selection uncertainty.

Model-self comprises fifteen classifiers and one shared inclusive reference:
48 cells and 24,000 planned fits. Each cell constructs its model and auxiliary
sampler once. Each Toy has its own candidate/injection/index-derived random
stream. It uses the existing T1 `shapesys` model, mu bounds [0,20], and a single
68% bounded profile-likelihood interval. There is no artificial CRN coupling,
paired coverage comparison, 95% fitted interval, critical-value calibration,
assessment Toys or nested T2. The coverage estimate's Wilson interval uses 95%
confidence, which is distinct from the fitted interval's 68% confidence.

Nested T2 is implemented under a different [protocol and runbook](draft-v2-t2.md).
It keeps this validation protocol and its budgets unchanged, fixes two disjoint
evaluation parents and resamples validation only before independent inner Toys.

Every planned Toy remains in the denominator. Reports distinguish success and
coverage divided by all 500 Toys from conditional coverage among valid fits.
Bias and mean width describe valid fits only. Failure, missing-upper-crossing,
and boundary-hit rates retain the planned denominator. Missing estimates are
not counted as boundary hits, and their failure counts remain visible. Coverage
under a model's own truth does not validate that model for signed MC or physics.

## Commands and access

Use Python 3.12 in the existing `pytorch` Conda environment. Inspect an existing
source without opening or hashing event payload:

```sh
python scripts/h4l_draft_v2_validate.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name validation001 --plan-only
```

The plan reads only protocol/manifest metadata and small binding metadata. It
does not score events, construct output directories, launch workers, or validate
unit payloads. Listed existing unit directories are explicitly **unverified**.
An input identity in a plan is not clearance for access.

Register a fresh sibling output directory:

```sh
python scripts/h4l_draft_v2_validate.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name validation001 --through register
```

Registration validates source model and aggregate hashes, but does not open or
hash event files. It emits a **pending**, plan-bound access template in
`register/access-review.pending.json`. The original nominal receipt does not
extend to this new budget. A reviewer must check the supplemental design and
current declared history and save a separate approved receipt, with
`decision=allow_exploratory_supplement`, reviewer identity and date, and unchanged
bindings. The [access schema](../config/schemas/h4l_draft_v2_validation_access.schema.json)
and [placeholder example](../config/examples/h4l_draft_v2_validation_access.pending.json)
do not grant approval. If history changes, use the newly printed plan template
for review; never change the registered scientific design.

After explicit authorization for the actual controlled-MC run:

```sh
python scripts/h4l_draft_v2_validate.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name validation001 \
  --continue --access-review /path/to/reviewed-supplement.json --workers 2
```

A durable `.h4l-draft-v2-validation-claims` record is written before event hash,
read, or score caching, and participates in the existing population-history
scanner. The local history audit cannot prove absence of access elsewhere.
Another plan's new claim makes an older receipt stale. Claims for this same
registration are excluded when rechecking its receipt for continuation.

Individual entry points require an explicit supplemental protocol:

```sh
python -m higgsml.cli draft-v2-validation model-self \
  --source-run runs/h4l-draft-v2-draft001 \
  --run-root runs/h4l-draft-v2-validation-validation001 \
  --protocol config/protocols/h4l_draft_v2_validation_v1.json --continue
```

Stages are `register`, `bootstrap`, `model-self`, and `report`. Model-self uses
published nominal template aggregates and does not open or hash event payload.
It can run independently of bootstrap after registration. `--no-progress`
suppresses progress bars. Workers default to one and can be set to 2–4. The
optional parallel extra supplies `cloudpickle` and `threadpoolctl`. This
supplement requires `threadpoolctl` even for serial numerical execution to
enforce the one-native-thread contract; registration and reporting do not.

## Immutable units and recovery

Bootstrap units are `bootstrap-0000` through `bootstrap-0199`; each contains both
modes and the common reference. Toy units are named, for example,
`model-self-ABCD-42-mu0` or `model-self-inclusive-mu2`; each contains all 500
planned outcomes. The parent process atomically publishes complete units and
records immutable unit claims before dispatch. Workers do not write files.

`--continue` validates complete units before skipping them. Numerical failures
are complete scientific terminal outcomes and cannot be replaced or resampled.
An interrupted or corrupt unit requires both explicit flags:

```sh
python scripts/h4l_draft_v2_validate.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name validation001 \
  --unit bootstrap-0012 --retry-failed \
  --access-review /path/to/reviewed-supplement.json
```

Recovery writes a new `units/<unit>-retry-<uuid>/`, preserving old directories
and claims, and uses the same budget and random streams. Streams derive from
version, source freeze, base seed, stage, role or candidate, and replica/Toy
index. Worker count, output name, retry path and scheduling order are excluded.
Bootstrap common streams exclude candidate and training seed.

Reports preserve execution completeness, numerical completeness, and scientific
qualification separately. CLI exit 6 indicates an incomplete report's execution;
exit 0 never certifies numerical completeness or valid coverage. A report can
be generated before all units finish and labels missing/corrupt units. A later
`report --continue` reuses an identical validated report or publishes a new
`report-resume-*` aggregate. Use the printed path.

Outputs include bound JSON, bootstrap differences and percentile summaries,
threshold and category-yield CSV files, a 48-row coverage CSV including missing
unit states and Wilson intervals, and PNG/PDF figures for the four deletions, refitted
thresholds, and model-self coverage. Missing official bootstrap percentiles are
not replaced with successful-only ranges. Threshold histograms include available
thresholds even when support or fitting fails; availability is labelled.
All outputs remain separate from source runs and publication assets.

## Computation and verification

One bootstrap invocation decodes only validation/evaluation payload, predicts
each model once per role, and retains sorted scores for weighted medians.
Group contribution arrays compute `Y = sum(m_g u_g)` and
`V = sum(m_g u_g u_g.T)`. Multiplicity is never squared. Absolute, positive and
negative row weights and copied-group occupancy are accumulated separately.
The existing positive-yield, covariance, effective-count >=20, cancellation
ratio >=0.2 and category-independence checks remain active. Failed support is
neither clipped nor rescued by category merging.

One bounded executor serves each stage, using processes on non-Windows systems
and threads on Windows. Each worker uses one native numerical thread; there is
no nested parallelism. Per-unit timing separates template/model setup and fits;
per-invocation timing records loading, scoring, publication, worker count,
platform and the monotonic clock. Worker-duration sums are not wall time.
Software versions are retained in research manifests. No wall-time or speedup
guarantee follows from the nominal fit counts.

Run focused synthetic checks before the full suite:

```sh
python -m pytest -q tests/h4l/test_draft_v2_validation.py tests/h4l/test_draft_v2.py
python -m pytest -q
python -m compileall -q src scripts tests
python -m pip check
```

The private Toy kernel permits small synthetic unit-test budgets, but public
registration and terminal validation require the exact fixed production
budgets. These software tests do not execute or qualify the controlled-MC
supplement; that remains a separately authorized future stage.

## Synthetic performance observation

On macOS 15.8.1 x86_64, Python 3.12.13 and NumPy 2.5.1,
`python scripts/benchmark_draft_v2_moments.py` compared ten identical draws
of 4,000 synthetic groups with three rows per group, two bins, and signed
weights. Explicit copies plus reference moments took 0.09561 s. Cached group
moments took 0.000382 s to build and 0.001557 s for the ten weighted reductions
(0.001939 s total). All six outputs matched with rtol=1e-11 and atol=1e-10.
Both paths used one native numerical thread. This is a small group-moment
benchmark, not a full-pipeline or pyhf-fitting speedup estimate; hardware, data
size and support failures change end-to-end timing.

## Software verification on 30 October 2026

The related draft-v2 and supplemental regression passed 54 tests. The full
repository regression completed with **690 passed and 1 skipped** in 1,312.19 s
on macOS x86_64 in the existing Python 3.12.13 `pytorch` environment. After the
reporting-only CSV additions, all **17 supplemental tests** passed again. The
final figure-axis adjustment was checked by regenerating all 13 synthetic
export files and inspecting the coverage figure; bootstrap and threshold
figures were also inspected. These exports include an intentionally incomplete
run with injected fit failures, not a successful coverage result.

Compileall, pip check, local documentation links, LF and diff-whitespace checks
passed. Pyhf-related warnings remain visible in test output; dependency
versions/locks were not changed. A metadata-only plan against draft001 listed
248 units and the fixed budgets without opening event payload or creating its
proposed output directory. The synthetic integration checks also verified
byte-for-byte source preservation, independent streams, shared bootstrap draws,
serial/process equivalence, failure denominators, stale-access rejection,
corruption recovery, cross-registration rejection and incomplete reporting.

No controlled-MC supplemental run, retraining, paper asset refresh or other-OS
numerical execution was performed. These are software and synthetic numerical
checks, not independent physical applicability or coverage qualification.

### Second-batch verification

The threshold-diagnostic extension passed **22 related tests** using
`tests/h4l/test_draft_v2_thresholds.py` and
`tests/h4l/test_draft_v2_validation.py` (165.54 s on the same macOS environment).
Five new focused checks cover threshold deltas and complete-budget summaries,
unchanged cuts, threshold versus support failures, signed paired redistribution,
validation-only threshold estimation, ties, frozen-model preservation and CSV/plot
exports with explicitly missing replicas. The deterministic synthetic export
fixture produces 16 report files, including the new paired-yield CSV and
threshold-shift PNG/PDF; the shift figure was visually checked. This fixture is
an export test, not a sampled full-MC result.

Compileall, pip check, LF, local links and diff-whitespace checks also passed.
The full-suite count above belongs to the preceding implementation batch; the
full suite was not repeated for this aggregate-report extension. No new event
access, controlled-MC execution, original threshold update or paper edit occurred.
