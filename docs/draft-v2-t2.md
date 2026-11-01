# Draft-v2 nested T2 cross-evaluation

This separately registered extension evaluates repeated threshold calibration
conditional on the fifteen existing draft-v2 networks. It uses the approved
two-fold design within the existing evaluation role and does not change the
source run, its 60/20/20 allocation, nominal thresholds or manuscript assets.
The nominal and [supplemental validation](draft-v2-validation.md) wrappers do
not start T2. Neither original protocol is extended in place.

The contract is
[`h4l_draft_v2_t2_v1.json`](../config/protocols/h4l_draft_v2_t2_v1.json), with
its [strict schema](../config/schemas/h4l_draft_v2_t2_v1.schema.json).
Results remain `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, and `primary_claim_eligible=false`.
The scope remains `synthetic_software_defaults_not_physics_validation`.

## Estimand and fixed budget

| Component | Rule |
|---|---|
| Candidates | Fifteen frozen models and one inclusive reference |
| Outer repetition | 20 uniform multinomial bootstraps of all sorted validation physical groups, preserving group count |
| Threshold | Background absolute-physical-weight empirical median, with `score >= threshold` in the high category |
| Fixed evaluation parents | Two disjoint physical-group halves, exchanging fit-template and Toy-mother roles |
| Inner experiment | 100 Toys per candidate, fold and outer repetition at mu=1 |
| Inference | Existing T1 `shapesys`, mu in [0,20], 68% profile-likelihood interval |
| Execution unit | One candidate × template fold × outer repetition, containing all 100 planned Toys |
| Total budget | 16 × 2 × 20 = 640 cells; 64,000 planned fits |

The outer draw is shared by all models, training seeds and both folds. Only
validation is resampled. Fit-template and mother events remain fixed across
outer repetitions, while their category assignment follows each new threshold.
No network, checkpoint, mass bin, feature set or threshold rule is selected.
The inclusive reference has no threshold to recalibrate; its repeated cells
provide a conditional count-model baseline with independent Toy streams.

The evaluation fold is the first eight bytes, big-endian, of
`SHA256("h4l-draft-v2-t2-eval-fold-v1:" + event_group_id)`, modulo two.
Group membership is deterministic and does not use event values or weights.
Each physical group stays intact. Each half uses the assignment probability
0.5: its T2 yield weight is `physical_weight / (0.2 * 0.5)`. The implementation
doubles a copy of the nominal evaluation yield weight. It never normalizes
by the observed fold size, class count or signed yield. Nominal normalization
remains `/0.2`.

Signed weights form template yields and group covariance; they are never
sampling probabilities. Both parents must pass positive-yield, group covariance,
`N_eff >= 20`, `rho >= 0.2` and category-independence checks. Halving the parent
sample can fail these checks even when nominal evaluation passes. Categories
are not merged, rates are not clipped, and folds are not repartitioned to rescue
support. Every cell is preflighted before any Toy is generated. A failed cell
retains all 100 planned failure slots; other supported cells can run.

Main observations are Poisson draws from the other fold's nonnegative process
expectations. Regenerated auxiliary observations follow the fit template's
nominal nuisance parameters, gamma=1, using the existing T1 auxiliary sampler.
Thus this is a conditional test of recalibration and disagreement between fixed
MC parents. It does not validate physical truth or model the sampling uncertainty
of the mother itself. Each fit model and auxiliary sampler is built once per cell.

Independent main/auxiliary streams bind the T2 version, protocol digest, source
freeze, base seed, candidate, fold, outer index, injection and Toy index. Outer
calibration streams exclude candidate and fold. Streams exclude worker count,
scheduling and output directory; changing execution order cannot replace a Toy.
There is no artificial marginal CRN coupling or paired coverage comparison.

## Interpretation and aggregation

The second-batch refitted-threshold bootstrap resamples both validation and
evaluation and studies finite-MC interval-width changes. T2 instead nests
pseudodata inside validation recalibration with fixed evaluation parents and
estimates conditional repeated-calibration coverage. Model-self Toys generate
main observations from their own fitting template and answer a different question.

The two folds exchange the same parent populations and share the outer draw.
They are not two independent datasets. Reports first average the two fold
fractions within each outer repetition, then summarize 20 outer clusters for
each candidate separately. They do not pool the three training seeds.

For each candidate, all 40 cells are required for a formal aggregate:

- Success and coverage uses all 4,000 planned slots; numerical failures stay
  in this denominator.
- Conditional coverage uses valid fits only, with failure rate alongside it.
- Unqualified `coverage` is available only if all 4,000 fits are valid.
- The outer-cluster standard error is the sample standard deviation of the
  20 fold-averaged success-and-coverage fractions divided by sqrt(20).
- Outer 16/84 percentiles describe variation across recalibrations, not a
  confidence interval. Aggregate uncertainty does not include parent or network
  resampling.
- Bias and mean width describe valid fits. Per-cell diagnostics also include
  missing upper bounds, boundary hits and failures. Per-cell Wilson intervals
  use 95% confidence conditional on that cell's mapping and parents; there is
  no pooled Wilson interval treating 4,000 Toys as independent recalibrations.

Execution completeness, numerical completeness and scientific qualification
remain separate. No critical value is automatically calibrated and no scientific
validity is inferred from a completed run or apparently nominal coverage.
This is not retraining-aware or full model-selection coverage, an ATLAS/CMS
result, a Higgs discovery or a physics measurement.

## Commands and access

Use the existing Python 3.12 `pytorch` environment from the repository root.
Start with a metadata-only plan:

```bash
python scripts/h4l_draft_v2_t2.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name t2-001 --plan-only
```

This reads manifests, protocol and identity metadata, never event payloads or
their hashes, does not score events, launch children or create output, and does
not treat existing unit paths as verified. Registration also leaves source
events unopened, but checks frozen models and nominal aggregate bindings:

```bash
python scripts/h4l_draft_v2_t2.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name t2-001 --through register
```

The new sibling directory is `runs/h4l-draft-v2-t2-t2-001/`. Its registration
contains the complete 640-unit plan and `access-review.pending.json`.
Before an authorized controlled-MC preparation, copy the pending receipt to a
separate file and review its actual source, freeze, population, history and
64,000-fit budget. An approved receipt requires `status=approved`,
`decision=allow_exploratory_t2`, and nonempty `reviewed_by` and `reviewed_at`.
Its identity and budget fields must match exactly. The
[schema](../config/schemas/h4l_draft_v2_t2_access.schema.json) and
[pending example](../config/examples/h4l_draft_v2_t2_access.pending.json)
are format references; a pending example is not authorization.

Prior nominal, bootstrap or off-only assessment receipts do not authorize T2.
No command generates an approval automatically. Later population access makes
an unconsumed receipt stale; review it again before opening events. Preparation
records a durable `.h4l-draft-v2-t2-claims` entry in the existing history scope
and a local preflight claim **before event hash, read or scoring**.

The following command is for the separately authorized execution phase:

```bash
python scripts/h4l_draft_v2_t2.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name t2-001 \
  --continue --access-review /path/to/reviewed-t2-access.json --workers 2
```

Preparation reads validation/evaluation once, scores each model once per role,
sorts validation scores once, and publishes all outer mappings and parent
templates. Once that valid preflight exists, fitting and reporting consume
published aggregates without opening events; their saved access provenance is
still checked. A later history entry does not invalidate already-authorized
cached work. Source artifacts remain read-only.

The direct CLI provides `higgsml draft-v2-t2 register|prepare|run|report` and
requires explicit `--source-run`, `--run-root` and `--protocol`. Use
`--through prepare` on the wrapper to stop after support preflight. Direct
`report` can publish an explicitly incomplete inventory before all units exist.
The wrapper defaults to one worker, accepts 1–4 and uses one native numerical
thread per worker. Windows uses thread workers; other platforms use processes.
Only the parent publishes artifacts. Timing records cover loading, scoring,
preparation, generation, fitting and publication; no wall-clock speed promise
is attached to the planned fit count.

## Continuation and recovery

`--continue` verifies and skips complete units, including scientific failures.
Numerical failures cannot be replaced by favorable draws. Interrupted or corrupt
units require a specific unit and `--retry-failed`, for example:

```bash
python scripts/h4l_draft_v2_t2.py \
  --source-run runs/h4l-draft-v2-draft001 --run-name t2-001 \
  --unit t2-ABCD-42-fold0-outer00 --retry-failed --no-progress
```

Recover damaged preflight with `--unit preflight --retry-failed` and a currently
bound reviewed access receipt, because recovery reopens the parents. Original
failure and corrupt artifacts remain in place; retry artifacts have new paths.
Scientific preflight identity excludes elapsed timing, allowing a deterministic
recovery to retain the binding of existing complete units. Budgets, parents,
threshold rule and random streams are unchanged. Unexpected dependency or model
setup errors remain interrupted attempts, not fabricated scientific terminals.

Reports contain `summary.json`, `cells.csv`, `outer-clusters.csv`, `coverage.csv`,
`thresholds.csv`, `t2-coverage.png/pdf` and `report.md`. Missing/corrupt cells
prevent a complete candidate aggregate; successful subsets are not presented
as the full budget. Repeated reporting uses `--continue`, reusing an identical
report or publishing `report-resume-*`. Use the returned report path. Exit 6
denotes incomplete execution evidence; exit 0 does not grant scientific validity.

## Software verification scope

The synthetic T2 tests cover probability normalization and fixed disjoint
parents, shared outer mappings, stream isolation, main/auxiliary generator
distributions, serial/process agreement, all-slot failure denominators,
outer-cluster aggregation, payload-free planning, access-before-read ordering,
stale receipts, immutable source files, unit/preflight recovery and incomplete
reports. Existing likelihood tests supply the profile-interval numerical checks.
Private kernel tests may use smaller synthetic Toy counts; public registration
and result validation require the full contract budget and reject shortened units.

These tests do not execute the controlled-MC supplement, establish cross-platform
runtime acceptance or supply new numerical evidence for draft001. Full MC
support and coverage outcomes require a separately authorized run.

Verification on 2026-10-30 used macOS 15.8.1 Intel and Python 3.12.13 in the
existing `pytorch` environment. The related T2/validation/threshold suite passed
33 tests in 317.24 seconds. The final full regression passed 706 tests with one
Windows-only skip in 1,551.41 seconds, using `OMP_NUM_THREADS=1`,
`MKL_NUM_THREADS=1` and `OPENBLAS_NUM_THREADS=1`. `compileall`, `pip check`,
local Markdown links, LF checks and `git diff --check` passed. These timings
describe software tests, not an estimate for the controlled-MC T2 run.

A metadata-only plan against local draft001 confirmed 640 units and 64,000
planned fits without creating the proposed output directory or opening event
payloads. No controlled-MC T2 preparation, Toy generation or fitting was run.
The paper files and original nominal protocol were unchanged.
