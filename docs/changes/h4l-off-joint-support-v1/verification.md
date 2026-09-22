---
change_id: h4l-off-joint-support-v1
status: verified
source: Implementation self-checks against approved spec
updated_at: 2026-09-22T18:02:18+08:00
---

# Verification record

Mode: implementation feedback loop, not independent review. Base revision:
`d26e730840e523cb80e10fc0f512a94acc9ae9e3`, plus the current uncommitted change.
No commits, pushes, formal analysis or assessment access were performed.

## Environment

Python 3.12.13 in `C:/Users/whchen/anaconda3/envs/pytorch`. The repository's
historical `D:/apps/anaconda3` command path is absent on this host. All numerical
checks used the actual `pytorch` environment. `pip check` reported no broken
requirements. `compileall` and `git diff --check` passed.

## Software evidence

- Initial related regression matrix: 92 passed (calibration, bootstrap, attribution,
  marginal workflow/state/coupling, seed blocks and wrapper compatibility).
- Final joint-support tests: 14 passed. Independent group/multiplicity arithmetic,
  nearest-median lower-q tie, no feasible cut, cross-bin projection failure,
  process/role errors, record binding, configuration conflict, RNG separation,
  serial/parallel bootstrap failures, T2 fixed-template mapping, full 80-candidate
  synthetic nominal rebuild, M0off likelihood equivalence, interrupted-publication
  reuse and cross-method rejection are covered.
- Related joint-support/marginal workflow run before the last configuration guard:
  26 passed. The final targeted run covers that guard and publication checks.
- Full suite: 558 passed, 5 skipped, 1 failed in 899.05 seconds. The failure
  was `test_enabled_controls_publish_and_replay_capacity_stage_chain`, whose
  default temporary file path reached 264 characters and could not be created
  on this Windows host. Repeating its original directory setup reproduced the
  same filesystem failure. The unchanged test passed with a fresh short
  `--basetemp`: 1 passed in 214.24 seconds. No test assertion or production
  sample-efficiency code was changed. The full suite was not redundantly rerun
  after resolving this platform path issue; its failed case and the final
  implementation guards were rerun separately as documented here.
- After the final publication/report/seed-block binding guards, the targeted
  joint-support, seed-block and marginal-coupling matrix passed: 25 tests.
- The 5 full-suite skips are platform-dependent symlink creation checks;
  these are not scientific-validation evidence.
- The wrapper's `--plan` command propagates the method through every Stage B
  command without writing a run or consuming a claim. An initial invocation used
  the unsupported spelling `--plan-only`; it was corrected to `--plan`.

Final source-set SHA-256: `336e32cb097f8f57849032505300903054219031cc3e4812fe69b9f89473fc64` (24 source/config/test files). The per-file receipt is in the ignored `var/joint-support-tested-source-sha256.json`. All changed text files use LF. The full-suite attempt predates the last local guards; those guards received the final targeted matrix above.

## Bound development replay (AC-02)

Command:

```powershell
& C:/Users/whchen/anaconda3/envs/pytorch/python.exe scripts/h4l_joint_support_replay.py --output var/h4l-joint-support-replay-20260922-001 --workers 4
```

Result: all 80 candidates replayed against the pinned evidence. The new cohort
has 200/200 complete support passes; there are exactly 131 nonmedian selections
among the 15,000 nonempty candidate/replica cells; all 75 nominal nonempty
thresholds remain medians. Quantiles match exactly; threshold comparisons use
rtol=1e-10 and atol=1e-12. These tolerances never alter support decisions.
Original evidence hashes and its output hash manifest were verified before
loading. Only NPZ row 0 and rows 201–400 were replayed. A serial attempt was
stopped before publication and restarted with four workers; no draws changed.

Local evidence: `var/h4l-joint-support-replay-20260922-001/verification.json` and
`selections.csv`. These are ignored development artifacts. The later strict
configuration-equality guard does not change the numerical selector for the
same checked-in method configuration; its positive and rejection paths are
covered by the final targeted tests.

## Acceptance and evidence boundaries

| Criteria | Evidence |
|---|---|
| AC-01/03/04 | Selector records, schema, hand-calculated grouped signed moments, fixed integer tie rule, no-fallback and constant baseline tests |
| AC-02 | Exact retained development replay above |
| AC-05/06 | Bootstrap role/draw and parallel identity tests; T2 callback mapping/preflight-budget tests; independent stage/contract RNG tests |
| AC-07/09 | Synthetic nominal publication/reload, record hashing, method mismatch rejection, preserved legacy regression and access tests |
| AC-08/10 | Separate execution/qualification fields, explicit 36-unit plan, no-imputation/bootstrap-failure and exploratory report tests |

The complete new formal matrix (nominal/Asimov, formal bootstrap, model-self,
assessment and T2) was not executed. No network was retrained. No real data was
processed. Development support replay and synthetic tests do not validate
selection-aware coverage, bias, physical applicability of signed-MC shapesys,
or the precision of a new formal analysis. These remain unvalidated, with
`primary_claim_eligible=false`. No independent review is claimed.


Resolved full-suite failure command:

```powershell
& C:/Users/whchen/anaconda3/envs/pytorch/python.exe -m pytest tests/h4l/test_sample_efficiency_controls.py::test_enabled_controls_publish_and_replay_capacity_stage_chain --basetemp D:/code/HiggsML/var/js-test-20260922-001 -q
```

Final outcome: implementation and required self-checks completed. No unresolved
implementation failure remains in the exercised checks. This is not an
independent review or scientific-coverage validation. Existing pyhf/jsonschema
RefResolver deprecation warnings remain.
