---
change_id: h4l-off-marginal-coupling-v3
status: draft
source: Implementation self-checks and controlled-MC template-only engineering evidence
updated_at: 2026-09-18
---

# Implementation verification evidence

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
[report](../../../runs/h4l-off-v3-qualification-20260918-final/report/report.md).
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
recorded in [review-decision.md](review-decision.md), including the atomic
cross-version reservation and legacy-directory ordering fixes. Reviewers did
not execute scientific validation. Human acceptance and default migration are
not inferred from these checks.

The change includes untracked new modules, schemas and tests; `git diff` alone
does not include them. Existing `h4l_all` default-v2 changes and corresponding
tests were preserved. Other entry points retain v1 defaults; v3 is explicitly
selected. No commit or push was made.
