---
change_id: h4l-off-marginal-coupling-v3
status: draft
source: Implementation self-checks and controlled-MC template-only engineering evidence
updated_at: 2026-09-18
---

# Implementation verification evidence

## Record scope and subsequent changes

This historical record is dated 2026-09-18 and was relocated on 2026-10-06.
It consolidates the original verification, implementation plan, implementation
review findings and review decisions for `h4l-off-marginal-coupling-v3`.
Original documents remain in Git history before the migration (HEAD
`e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`). The original verification metadata
was `status=draft`; the decisions metadata was `status=awaiting_approval`, and
the findings metadata was `status=verified`. These historical statuses do not
constitute a later human acceptance or default-cutover approval.
The v1/v2 defaults and opt-in v3 routing below describe the implementation stage.
For current routing, see [current methods](../methods-and-evaluation.md#within-seed-marginal-crn-evaluation)
and [reproduction instructions](../implementation-and-reproduction.md).
Local run evidence and host-specific test logs are not bundled with Git and were
not found or revalidated during this migration. This record does not establish
current scientific qualification or the selected paper's numerical results.

Environment: `C:/Users/whchen/anaconda3/envs/pytorch/python.exe`, Python
3.12.13 on Windows. The AGENTS.md `D:/apps` Conda path does not exist on this
host; checks used the dependency-complete `pytorch` environment directly.

| Check | Result |
|---|---|
| Focused v3/inference/compatibility suite | 64 passed in 159.31 s; `D:/tmp/h4v3-focus.log` |
| v3 workflow rerun after schema corrections | 12 passed in 93.06 s |
| Shared state and cross-version history checks | 37 passed in 9.41 s |
| Legacy workflow guards and self-review regressions | 14 passed in 18.53 s; `D:/tmp/h4v3-legacy.log` |
| Final v3 state regressions, including concurrent reservations and invalid legacy directory | 8 passed in 5.78 s |
| Full regression | 622 passed, 5 skipped, 500 warnings in 1019.69 s; `D:/tmp/h4v3-full-final.log` |
| Python compilation | Passed |
| Dependency consistency | `pip check`: No broken requirements found |
| Tracked patch whitespace | `git -c core.safecrlf=false diff --check`: passed |
| New-file sanity | 23 new implementation/schema/test/change-document files: Python/JSON syntax, conflict markers and whitespace passed |

The focused checks cover marginal Poisson laws and covariance, deterministic
streams, signed-rate rejection, canonical totals and role bindings, zero-total
receipts, actual assessment routing with mocked fits, late T2 preflight failure,
versioned schemas, poisoned assessment inputs for J0/J1, immutable terminals,
and cross-version population reservation. These are software/synthetic checks.

Full-suite command (PowerShell, repository root):

```powershell
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' -m pytest -q --basetemp D:/tmp/h4v3fullfinal
```

The final shared-reservation amendment was added while the full suite was
running. Its final state was checked separately by the shared-state, legacy
workflow and final v3 state suites above; the full run alone is not evidence
that every test used the final amendment. Initial failures from copied schema
constants and internal test names were fixed and rerun. An earlier interrupted
full run (`D:/tmp/h4v3-full.log`) is not counted as passing evidence.
The full run collected 627 tests; two subsequently added state regressions
were included in the final 8-test state check (the final tree has 629 tests).
The warning summary is the existing pyhf/jsonschema `RefResolver` deprecation.

## Controlled-MC engineering qualification

Fresh immutable run: `runs/h4l-off-v3-qualification-20260918-final`.
It reuses the audited `h4l-off-test01-v2` source-register/source-nominal inputs
and publishes a new v3 registration, nominal artifact, J0, J1 and template-only
report, historically at
`runs/h4l-off-v3-qualification-20260918-final/report/report.md`.
The earlier `h4l-off-v3-qualification-20260918-1140` run is also preserved.

- J0 passed for seeds 42--46: 62 positive label-level marginals per seed.
- J1 passed for all five seeds: 0/200 failed thinning replicas per seed.
- J0 artifact: `a06c9f1e8be413d5bc12c7798265a2eb543695deb7ba25008562b7f0fc5001dd`.
- J1 artifact: `d5354bdd63d1ac318c6fd77f2a81d3addeebeea7ed6013025d169dc6f5213fee`.
- Both gates record `assessment_payload_read=false`. No freeze or assessment
  evaluation was executed; neither `runs/.h4l-mass-off-v3-claims` nor
  `runs/.h4l-population-access` was created.

This is `label_level_legacy` engineering evidence, not physical-process
qualification or scientific validation. The report correctly remains
`incomplete`, with inference stages `not_run` and sensitivity `pending`.
No prospective assessment/T2, retraining, default cutover or real-data access
was performed. Independent-allocation generation is tested synthetically;
paired-error sensitivity fitting remains pending under the approved spec.

## Review and delivery boundary

Two independent read-only reviewers rechecked their findings; resolutions are
recorded in the consolidated review table below, including the atomic
cross-version reservation and legacy-directory ordering fixes. Reviewers did
not execute scientific validation. Human acceptance and default migration are
not inferred from these checks.

The change includes untracked new modules, schemas and tests; `git diff` alone
does not include them. Existing `h4l_all` default-v2 changes and corresponding
tests were preserved. Other entry points retain v1 defaults; v3 is explicitly
selected. No commit or push was made.

## Implementation scope and authorization (consolidated plan)

The plan had `change_id=h4l-off-marginal-coupling-v3`, `status=implemented`,
`updated_at=2026-09-18`, and the user's instruction to execute the reviewed
[specification](../methods/h4l-off-marginal-coupling-v3.md) and modify code as its
source. That authorization did not authorize default cutover or assessment access.

1. Implement pure marginal support, bound role/numeric contracts, canonical common
   totals, stable cell streams and monotone/independent allocations. Test signed
   rejection, numerical boundaries, identities and Poisson laws.
2. Add opt-in v3 artifact identities and J0/J1 orchestration, preserving v2 consumers
   and historical schemas. Share inference/claim machinery where contracts permit;
   isolate version-specific orchestration.
3. Integrate model-self/assessment marginal generation and two-phase T2, with bound
   outer preflight material and truthful planned/generated counts.
4. Route CLI and wrappers explicitly, retaining the then-existing `h4l_all` v2
   default and off_run/evaluate/attribution v1 defaults. Expose v3 interpretation
   and support fields in reports. Preserve history checks across versions.
5. Run focused synthetic/compatibility tests, full Python 3.12 suite and pip check.
   Inspect template-only controlled-MC J0/J1 feasibility in a fresh run root if
   compatible inputs permit. Record failures without repair. Do not execute
   assessment/T2 on the consumed population or claim scientific proof.

The plan classified this as a high-risk statistical change, with acceptance under
specification criteria 1--16. Software evidence, engineering qualification and
scientific validation remained separate. Historical rollback selected explicit
v1/v2 and retained all v3 evidence. No commit, push, default migration, retraining
or source-data change was authorized. Those historical CLI choices are not
instructions for the current CLI.

## Implementation review findings, decisions and proof

Reviewers were GPT-5.6 Terra (high, correctness) and GPT-5.5 (high, risk).
They reviewed the tracked diff and then-untracked v3 implementation, schemas and
tests in fresh-context, read-only reviews. Neither ran tests or scientific
evaluation. The full verification was still in progress at initial review;
review completion was not final acceptance. Review decisions below were
evidence-backed resolutions with the historical `awaiting_approval` status.

| ID | Severity / source | Finding and location | Decision | Resolution and proof |
|---|---|---|---|---|
| C1 | Medium / GPT-5.6 Terra | T2 preflight overwrote every scientific failure with insufficient_statistics; `likelihood.py`, preflight terminal | Accept | Preserve a sole failure status; mixed states use inference_incomplete and an explicit failure-status set. Parameterized late-outer support-failure regression. |
| C2 | Medium / GPT-5.6 Terra | Null theta lacked an explicit zero-total marker; `marginal_coupling.py`, coupling receipt | Accept | Record zero_total and zero_injected_total separately. Zero-parent-bin/null-theta regression. |
| R1 | Medium / GPT-5.5 | Full v3 wrapper could begin work without the required access receipt; `h4l_off_run.py`, versioned execution | Partial | Reject missing access before full v3 work; retain v2 behavior for compatibility. Wrapper-guard regression. |
| R2 | Medium / GPT-5.5 | Default-version documentation contradicted the existing wrapper default; README and reproduction guide | Accept | State each entry point's default, including the then-existing h4l_all v2 default and explicit v3 selection. Documentation inspection. |
| R3 | Medium / GPT-5.5 | Marginal blocks schema retained joint-contract and wrong block-prefix constants | Accept | Match the actual marginal contract and seed-block identities. Real-block schema validation and joint-contract mutation. |
| R4 | Medium / GPT-5.5 | Terminal schema lacked explicit marginal support, receipts and mandatory CRN metadata | Accept | Require marginal_support, coupling_receipts and conditional metadata; validate legacy alias equality. Terminal-mutation and immutable-resume tests. |
| R5 | Low / GPT-5.5 | Plan-only message always named v2; `h4l_off_run.py` | Accept | Use within-seed wording. Source inspection. |
| S1 | High / implementation self-review; GPT-5.5 recheck | Separate version ledgers allowed concurrent cross-version population reservations; `population_history.py` and v1/v2/v3 claim/freeze paths | Accept | Exclusively and atomically create a shared reservation with durable writes. Forced cross-version race and shared-history tests; risk-reviewer recheck. |
| R6 | Medium / GPT-5.5 follow-up | Invalid legacy claim directory could consume the shared reservation before directory validation; `workflow.py`, legacy assessment claim | Accept | Validate/create the legacy directory before reservation. Invalid-directory regression and risk-reviewer recheck. |

Both reviewers rechecked their findings. The correctness reviewer reported all
findings resolved and no obvious correctness regression. The risk reviewer
reported the functional/schema findings resolved and requested a final wording
correction distinguishing explicit-v2 commands from the default-v2 wrapper;
that correction was subsequently made. The risk reviewer also confirmed the S1
and R6 fixes. The concurrent-reservation regression proved only one version could
reserve the population; invalid-directory rejection did not consume it.
These are software checks only. All raised changes were implemented; no new
unresolved reviewer finding was presented as accepted risk. The review did not
authorize default cutover, new assessment access or scientific claims.
Sensitivity fitting remained explicitly pending under the approved specification.
