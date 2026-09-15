# Sprint M4-01 delivery evidence

Date: 2026-09-14. Worktree: `D:/code/HiggsML-m4l-off`; branch: `codex/m4l-off-feature-attribution`; base: `879560b2c965c417fbbab12b131102e8b738ca89`. Original `D:/code/HiggsML` remains clean. No commit or push, as required by the approved source plan. FR and Sprint are under the ignored `project/1-Requirement` and `project/3-Plan` directories; review evidence is retained here.

## Delivery and evidence boundary

A–E software paths, schemas, CLI orchestration and reporting are implemented. Actual controlled-MC replay is complete through A/B only. C event-MC bootstrap, D model-self/assessment Toys and E T2 have **not** been executed on the full MC population. Independent P0/T1 applicability and historical assessment-use review remain pending; no assessment payload was decoded. Native ARM64 was not run. The full scientific plan is therefore not complete, even if software checks pass.

## Gates

| Gate | Evidence | State |
|---|---|---|
| Requirements and Sprint | `project/1-Requirement/FR-401-m4l-off-feature-attribution.md`, `project/3-Plan/sprint-m4-01.md` | Written and clarified |
| Independent document review | `sprint-m4-01-review-by-gpt-5.6-sol.md`, `sprint-m4-01-review-by-gpt-5.5.md` | Complete |
| Document confirmation | `sprint-m4-01-review-confirm.md` | Accepted/partial actions applied before implementation |
| Independent code review | `sprint-m4-01-code-review-by-gpt-5.6-sol.md`, `sprint-m4-01-code-review-by-gpt-5.5.md` | Complete; exact configured models, fresh contexts |
| Code confirmation | `sprint-m4-01-code-review-confirm.md` | All eight rows addressed before final verification |
| Software verification | Commands and results below | Passed: 481 tests, 5 skipped |
| Commit | Approved plan explicitly excludes commit/push | Skipped by instruction |

The updated review-start skill was reread after the user's update. The required independent passes use Codex subagents, not the superseded external-review program. Earlier review files remain historical evidence only.

## Acceptance traceability

| Requirement group | Implementation / check | Actual evidence level |
|---|---|---|
| Reuse, registration, independent qualification | 75-model checkpoint/input/population audit; immutable source SHA/size/mtime receipts; overlay definition digest; strict P0 applicability schema and independent T1 evidence validator | Actual source audit and software contract checks; independent qualification pending |
| Family G1/freeze without legacy candidates | 80 identities, deterministic M0off, common-grid structural-zero evidence, bound mappings and budget freeze | Actual MC nominal/G1/freeze passed |
| Empty-set likelihood | Constant score, zero parameters, five pairing identities; actual active-bin pyhf model spec equals same-grid mass-only baseline | Synthetic check plus actual MC likelihood certificate |
| Shapley/interactions/pairs | Per-seed estimands before medians; 4 contributions, 24 interactions, 105 canonical pairs; missing/cohort/NaN rejection | Unit tests plus actual B report |
| Seed uncertainty/ranks/ties/AUC | 3125 joint ordered seed vectors with linear quantiles; exact ties; rank of median W68 separate from median rank; 75 checkpoint-bound AUC observations | Unit tests and actual B report |
| Event-MC bootstrap | 200 retained role-group draws, raw threshold/template rebuild, frozen grid, per-replica full summaries; incomplete formal intervals suppressed | Software failure-budget and shared-multiplicity checks; full MC not_run |
| Fixed-T1 Toys | 500 marginal budget at mu 0/1/2 for both expectations; process-wise joint eligibility and nominal marginal equality; equivalent Poisson superposition; explicit unavailable fallback | Synthetic connected model-self dispatcher/joint projection and fallback tests; full MC not_run |
| Coverage/fit failure semantics | Conditional coverage and planned-denominator coverage with Wilson intervals; bias/pull/width/boundary/failure fields | Synthetic/domain tests; full MC coverage not_run |
| T2 | Shared 20 calibration draws, same mapping on template and mother, 100 inner budget retained for every outer replica | Synthetic mapping/budget tests and legacy T2 checks; full MC not_run |
| Access and recovery | Strict P0 numerical/source/freeze bindings before durable claims; exclusive same-freeze per-cell ledger before decode; plan digest/five input IDs/family/budget/legal cell checked in stage/reuse/report | Forged-package, claim-order, repeat-cell and malformed-manifest tests; actual assessment access remains pending |
| Evaluation-plan generation | Stage B report generates the exact plan from actual five manifests; no manually edited IDs | `sprint-m4-01-bound-plan-preflight.json`: zero unresolved inputs, eight cells, no assessment read |
| Off-only reports and immutability | Four CSVs, six result areas, full JSON/JSONL, provenance, field semantics; no on-family paper results | `sprint-m4-01-final-artifact-check.json`: rows 80/4/24/105; source receipts rechecked; original checkout clean |
| Legacy compatibility | Existing CLI, default assessment role, M4/M5 and evaluation v1 remain available | Focused legacy tests and complete suite |

## Verification commands and observed results

Environment: Python 3.12.13, `C:/Users/whchen/anaconda3/envs/pytorch/python.exe`. Every Python command used `PYTHONPATH=D:/code/HiggsML-m4l-off/src`. The documented D:/apps Conda path is absent; the discovered local executable was used. No parallel Conda commands.

- Baseline full suite: 448 passed, 3 failed, 5 skipped; `sprint-m4-01-baseline-tests.txt`. Two failures were tests assuming optional diagnostics/history fields; corrected to test actual required contracts. The Windows long-path case is avoided with a fresh shorter pytest base directory, without changing scientific code.
- Implementation before review corrections: 468 passed, 5 skipped, 340 warnings in 712.06 seconds; `sprint-m4-01-implementation-tests.txt`.
- Final focused attribution/evaluator/assessment/reporting checks: 46 passed, 177 warnings in 23.19 seconds. Legacy `tests/h4l/test_mc_bootstrap.py`: 2 passed in 3.99 seconds.
- Final full suite: **481 passed, 5 skipped, 500 warnings in 701.60 seconds** (exit 0); output preserved in `sprint-m4-01-final-tests.txt`. Warnings are pyhf/jsonschema deprecation notices; skipped tests are not passing evidence.
- Environment check: `C:/Users/whchen/anaconda3/envs/pytorch/python.exe -m pip check` returned `No broken requirements found.`
- `git diff --check` passed. Git emitted only line-ending conversion notices.
- Two exploratory test invocations referenced an incorrect test filename and collected no tests; they are not passing evidence. Correct focused commands above completed successfully.

Final full-suite command:

```powershell
$env:PYTHONPATH='D:/code/HiggsML-m4l-off/src'
& 'C:/Users/whchen/anaconda3/Scripts/conda.exe' run --no-capture-output -n pytorch python -m pytest -q --basetemp D:/code/HiggsML-m4l-off/runs/pytest-final-002
```

The pytest destination was confirmed absent before execution. Existing run artifacts were not removed or overwritten.

## Actual output

The post-review report is `runs/m4l-off-003/report-B/report.md`, backed by `report.json`, `evaluation-plan.json` and immutable file receipts. Details and artifact IDs are in `sprint-m4-01-mc-stage-b.md`. This is exploratory fixed-T1 model-self Asimov evidence, not a measurement or validated coverage result.

Remaining scientific work: obtain independently reviewed applicable P0/T1/history evidence; execute the registered C and model-self D budgets; only then execute authorized assessment D/E cells with the frozen population and unchanged protocol. Do not upgrade absent or automatic references or treat synthetic tests as full-MC validation.

Final software status: accepted after both review confirmations, all accepted/partial corrections, focused/full tests, pip check and diff checks. Full scientific A–E acceptance remains incomplete for the explicitly unrun/pending evidence above.
