# Draft-v2 three-subset workflow

This independent implementation follows `paper/draft-v2/main.tex` and the
subsequently confirmed choices: **all controlled 2020 MC**, including the
historical test partition, and **60% training / 20% validation / 20% final
evaluation**. These resolve choices left open in the review draft. The existing
five-role workflow, its default commands, test05 and selected manuscript assets
retain their original meaning. No historical prepared artifact or classifier is
converted into a revised-study result.

The software implementation and its synthetic tests do not execute or qualify
the proposed MC study. All results remain educational/technical, exploratory,
non-independent and coverage-unvalidated. They are not official ATLAS/CMS
results, a Higgs discovery or a physics measurement.

## Scientific contract

`config/protocols/h4l_draft_v2.json` is a separately validated, fixed version.
The validator rejects changed allocations, shortened training schedules, other
seeds, additional candidates and promoted qualifications. The source remains
the contracted DSIDs 345060 and 363490, common `2e2mu` selection, half-open
`105 <= m4l < 140` GeV window and 10 fb^-1 luminosity. Releases are not mixed.

The preparation extractor reconstructs the common selected MC population and
encapsulates it once. An independent `h4l-draft-v2-role-v1` SHA-256 group hash
assigns buckets 0–59 to training, 60–79 to validation and 80–99 to evaluation.
Assignments are independent of row order, model and network seed; correlated
representations remain together. Fractions are assignment probabilities rather
than exact finite-sample quotas. Signed evaluation yields use
`physical_weight / 0.2`. Separate subset yield estimates represent the same
luminosity and must not be added as separate exposures.

ABCD, BCD, ACD, ABD and ABC have 19, 11, 15, 17 and 14 explicit inputs,
respectively. Each is separately trained for seeds 42–44. Classifiers exclude
explicit `m4l`; this does not remove implicit mass information. The existing
64/64/32 LayerNorm/SiLU network, dropout, CPU float32, AdamW, maximum 200 epochs,
batch size 1024 and validation absolute-weight AUC checkpoint rule are retained.
Scaling is fitted only on training events. Optimizer weights are absolute
physical weights divided by their training-class mean, without assuming equal
class totals. The patience is 20 epochs and minimum AUC improvement is 1e-4.

For each selected checkpoint, the first ordered validation-background score at
which cumulative absolute physical weight reaches half the total is its frozen
threshold. Scores at or above it enter the high category. Ties are never split;
acceptance need not equal one half. No evaluation-support cut scan is performed.
The prepared-event reader skips evaluation payload before JSON decoding during
training. All fifteen models, scalers, thresholds, identities and reporting
rules must be frozen before evaluation payload is decoded by evaluation stages.

Both score categories enter T1 in one mass bin. Positive signed yield, positive
grouped variance, occupancy, signed effective count >=20, cancellation ratio
>=0.2 and independent-category nuisance compatibility are required for each
process/category. Empty tails are not structural zeros. No threshold movement,
clipping, category merging or failed-seed deletion rescues a candidate.

The pyhf 0.7.6 `shapesys` likelihood profiles nominal model-self Asimov data at
injected mu=1 using a 68% chi-square(1) threshold and `0 <= mu <= 20`. Missing
upper crossings remain failures. The inclusive-count reference is built once
from the same evaluation population, including grouped covariance when
aggregating events; it has no trained empty model or training-seed spread.

The report contains all fifteen widths, one shared reference, and the twelve
within-seed reduced-minus-ABCD differences. Medians require all three relevant
seeds, and are formed after computing the differences. Seed variation is not a
confidence interval. Shapley, full subset searches, bootstrap, Toys, T2,
adversaries and CDF transformations are outside this implementation.

## Commands and access

Use the existing Python 3.12 `pytorch` environment, from the repository root:

```sh
conda run -n pytorch python scripts/h4l_draft_v2.py --run-name draft001 --plan-only
conda run -n pytorch python scripts/h4l_draft_v2.py --run-name draft001 --through freeze
```

The default input is the existing
`data/raw/atlas2020_4lep/dataset_receipt.json`; acquisition is never launched.
An explicit `--dataset-receipt` overrides its location. Preparation checks the
contract, file metadata, recorded acquisition hashes, ROOT schema, DSIDs and
sealed selection/profile. It reuses acquisition evidence rather than claiming
an independent new hash of raw-source production.

Output is `runs/h4l-draft-v2-draft001/`, containing `prepare/`, fifteen
`train/<subset>-<seed>/` stages, `freeze/`, `evaluate/` and `report/`. Each uses
immutable research manifests and upstream artifact bindings. The freeze emits
`access-review.pending.json`, which is **not permission to evaluate**. A reviewer
must examine the declared history, all-MC reuse and source eligibility, then
save a separate receipt with `status=approved`,
`decision=allow_exploratory_reuse`, reviewer identity and date. Retain the exact
protocol, prepared, freeze and history bindings. The schema is
`config/schemas/h4l_draft_v2_access.schema.json`; the static pending example
has placeholder identities and is not usable as approval.

```sh
conda run -n pytorch python scripts/h4l_draft_v2.py --run-name draft001 \
  --continue --access-review /path/to/reviewed-access.json
```

No access approval is generated automatically. Historical claims are scanned
through the declared history roots and conservatively treated as potentially
overlapping the all-MC source, even when population hashes differ. A newly
arriving foreign claim makes an earlier history-bound review stale. Review the
current history and bind its digest before evaluation; do not change the frozen
analysis. This local audit cannot prove that there was no access elsewhere.

The shared history scanner also recognizes `.h4l-draft-v2-claims`. A durable
claim precedes the first evaluation payload decode. Earlier historical claims
are preserved; explicitly reviewed exploratory reuse does not confer independent
confirmation. Subsequent legacy/development access also recognizes controlled
all-MC claims as overlapping despite different population hashes. Labelled
synthetic claims do not establish controlled-MC source overlap.

Individual stages require explicit `--protocol` and `--run-root`:

```sh
conda run -n pytorch python -m higgsml.cli draft-v2 train \
  --protocol config/protocols/h4l_draft_v2.json \
  --run-root runs/h4l-draft-v2-draft001 --continue
```

The stage choices are `prepare`, `train`, `freeze`, `evaluate`, `report`.
`train` executes the fifteen registered units and can reuse independently
completed units. `--plan-only` reads manifest metadata without opening event
files, writing artifacts or launching child processes; a pending identity is
not clearance. The wrapper uses one CPU thread and serial units on every OS.

Terminal progress is enabled by default on stderr. The wrapper announces each
stage before its checks; preparation shows ROOT event counts, percentage,
elapsed/remaining time and selected events. Training shows the fifteen units
(including validated reused units) and a per-model epoch bar with validation
AUC, selected epoch and patience. The 200-epoch total is a maximum: early
stopping can finish below 100%, and the final message reports the actual epoch
count. Use `--no-progress` on either entry point to disable progress. Plan-only
execution does not create progress bars. Already-running processes do not pick
up this display change automatically.

## Recovery and outputs

`--continue` validates hashes, stage identities, protocol, source and upstream
bindings. Corrupt and failed evidence is preserved, with no automatic deletion
or quarantine. A claim without a valid terminal requires explicit
`--retry-failed`, the identical freeze and a bound access review. Its new output
is `evaluate-retry-<uuid>/`; preserve the original failure. Completed evaluation
terminals, including scientifically unsupported outcomes, cannot be retried.
The wrapper passes the actual validated evaluation path to the report. Direct
reporting after a retry must use `--evaluation-run <printed-evaluation-path>`.

`report/` contains bound JSON, `widths.csv`, `inclusive-reference.csv`, `contrasts.csv`, `report.md`,
`mass-bins.csv`, `yield-summary.csv`, and signed-yield/normalized-shape PNG/PDF
figures for ABCD/BCD seed 42. The spectra use seven 5 GeV display bins, separately
for signal/background, and preserve grouped before/after and normalization
covariance. Low-support bins are shaded, negative bins remain visible, and
unsupported signed normalization is labelled rather than forced. These display
bins do not enter the inference likelihood. Errors condition on fixed networks
and cuts; they omit retraining, threshold-estimation and coverage uncertainty.

Execution and scientific completeness are distinct. Exit 6 reports missing
scientific results while retaining complete terminal records; binding failures
use nonzero errors. An exit 0 never grants physical applicability or calibrated
precision gains. Generated runs, models and figures remain ignored. This
implementation does not update the pending revised-study manuscript table.

## Synthetic verification

`prepare --synthetic-events <fixture.json>` accepts only
`h4l-draft-v2-synthetic-v1`, `source_kind=synthetic`, the target dataset identity,
and an `events` array of already-selected unassigned synthetic feature rows.
Rows contain the nineteen features, `m4l`, signed `physical_weight`, event/source
row/group identities, `split=exploratory`, dataset and label. Fixtures cannot
contain inherited roles or yield weights. Synthetic provenance remains attached
to every model, freeze and report; it never becomes controlled-MC evidence.

```sh
conda run -n pytorch python -m pytest -q tests/h4l/test_draft_v2.py
```

The end-to-end test uses the unmodified production protocol and real training
with early stopping on synthetic inputs. No shortened training contract is
accepted as a formal artifact. These are software checks, not a full-MC run,
independent numerical reference or physics validation.

### Verification on 29 October 2026

Tested on macOS x86_64 in the existing `pytorch` environment: Python 3.12.13,
PyTorch 2.7.1, NumPy 2.5.1, pandas 3.0.5, SciPy 1.18.1 and pyhf 0.7.6.
The full regression run passed 664 tests with one platform-specific skip.
After the final source-overlap and learner-provenance checks, the affected
draft-v2/data/history/self-review regression passed 72 tests. The synthetic
end-to-end test also passed after figure-axis changes. Existing
pyhf/jsonschema deprecation warnings remain; no dependency definitions or locks
were changed. Compileall, pip check, schema/example validation, LF checks and
diff whitespace checks passed. Generated synthetic spectra were inspected.

No controlled-MC analysis, new data acquisition, physical applicability check,
independent coverage validation or other-platform execution was performed.
Historical sources, manuscript numbers and publication assets were preserved.
