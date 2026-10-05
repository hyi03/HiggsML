# Repository Agent Guide

## Project scope

This repository maintains one MC-only educational and technical workflow for
`H -> ZZ* -> 4l`. The active package is `src/higgsml`; legacy15 preprocessing,
training, qualification, final-fit, test-opening, and XGBoost implementations
have been removed. Do not reintroduce them unless the user explicitly changes
the project scope.

The active paper compares all 15 nonempty A/B/C/D subsets for seeds 42–46,
reusing 75 classifiers without explicit `m4l` and five deterministic `M0off`
identities. Its separately bound `joint-support-v1` method uses one mass bin
over 105–140 GeV, with two score categories for nonempty subsets and an
inclusive-count reference. Removing the mass input does not eliminate implicit
mass information, and this is not a comparison against a resolved mass-peak fit.
MELA, mass-conditioned CDF/adversarial comparisons, and sample efficiency are
separate supporting studies, not completed results of the off-only paper.

Never describe repository output as an ATLAS/CMS result, a Higgs discovery, or a
physics measurement.

## Start here

Read `README.md`, `docs/README.md`, and the task-specific method, protocol, or
runbook before changing scientific behavior. The main entry points are:

- `docs/research-design.md`
- `docs/data-and-processing.md`
- `docs/implementation-and-reproduction.md`
- `docs/methods-and-evaluation.md`
- `docs/results-and-limitations.md`
- `docs/sample-efficiency.md` for the separately registered sample-size study
- `config/protocols/h4l_protocol.json`
- `config/protocols/h4l_off_joint_support_v1.json` for joint threshold selection
- `config/protocols/feature_attribution_mass_off.json` for off-only attribution
- `paper/README.md`, `paper/result-evidence.md`, and `paper/selected-snapshot.json`
  for manuscript builds, current claims, and selected result identities

Code defines implemented behavior; versioned contracts and run snapshots define
the executed analysis; published artifacts establish numerical results. Do not
change a frozen contract or promote scientific qualification through prose edits.

## Code discovery and agent tools

The codebase knowledge graph database is stored in `.codebase-memory/` at the
repository root. When its MCP tools are available, prefer them for code discovery:

1. `search_graph` to locate functions, classes, routes, or variables.
2. `trace_path` to inspect callers and callees.
3. `get_code_snippet` to read specific function or class source.
4. `query_graph` for complex graph queries.
5. `get_architecture` for a high-level project overview.

Use `rg` for string literals, errors, configuration values, and non-code files,
or when graph tools are unavailable or insufficient. Do not automatically enable
Superpowers skills unless the user explicitly requests Superpowers in the prompt.
Authorized network access must use direct HTTP or HTTPS requests, not a
webservice abstraction; the controlled downloader uses contracted HTTPS URLs.

## Repository layout

- `src/higgsml/physics/`: selections, reconstruction, kinematics, weights, and splits.
- `src/higgsml/modeling/`: representations, discriminants, calibration, and matrix elements.
- `src/higgsml/inference/`: templates, likelihood inference, diagnostics, stress tests, and reporting.
- `src/higgsml/sample_efficiency/`: registered sample-efficiency study.
- `config/`: datasets, profiles, protocols, schemas, and examples.
- `scripts/`: controlled download and H4l workflow helpers.
- `tests/`: unit, workflow, and synthetic scientific-contract tests.
- `docs/`: paper-relevant methods, reproducibility, and validation documentation.
- `paper/`: LaTeX manuscript, committed PDF figures/TeX tables, and evidence index.
- `data/raw/` and `runs/`: ignored local inputs and immutable generated evidence.
- `var/`: ignored local aggregate evidence snapshots; preserve separately from Git.

## Environment and commands

Use Python 3.12 and the `pytorch` Conda environment. Run commands from the
repository root:

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip install --no-deps -e .
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip install -r requirements.txt
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m compileall -q src scripts tests
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest -q
```

Create the environment from `environment.yml` only if it does not already exist.
`requirements.txt` supplies inference additions including pyhf; parallel execution
uses the optional extra `python -m pip install -e ".[parallel]"` (cloudpickle and
threadpoolctl). Do not change dependency locks to make a validation claim pass.
Windows, Linux, macOS and supported CPU architectures are peer platforms; record
the actual tested environment without treating one platform as scientific authority.

The installed console entry point is `higgsml`. The orchestration helpers are
`scripts/h4l_all.py`, `scripts/h4l_prepare.py`, `scripts/h4l_check.py`,
`scripts/h4l_run.py`, `scripts/h4l_off_run.py`, `scripts/h4l_evaluate.py`, and the
sample-efficiency scripts. Use `python -m higgsml.cli attribution --help` for the
dedicated off-only stages. Direct core CLI stages require an explicit `--protocol`;
orchestration helpers propagate the default H4l protocol.

## Workflow and recovery

- Use `--plan-only` to inspect metadata and planned commands before execution;
  it must not launch children or open event/assessment payload. A
  `pending_prepare_identity` result is not access clearance.
- `h4l_all.py` defaults to `joint-support-v1`; direct `h4l_off_run.py` and
  attribution registration default to `median-v1`. Select joint support explicitly
  for the paper method and retain the original method when resuming old runs.
- `--stage-b-only` on the full wrapper stops after validated Stage B without
  generating access reviews or starting evaluation. Direct off-only execution
  reuses the source five-seed batch and prepared identity without retraining.
- Assessment/T2 requires a bound `h4l-off-assessment-access-v3` receipt. Adapt a
  reviewed source using `attribution access-review`; pending examples are not
  approval. Direct evaluation does not generate or approve reviews. The full
  wrapper's automatic self-review remains `independent=false` and exploratory.
- `config/h4l_history_roots.json` declares the live access-history scope, currently
  `runs/`. A new name, directory or prepare artifact does not create an independent
  population. A local scan cannot establish the absence of access on other machines.
- Supported `--continue` validates complete stages and preserves invalid or failed
  evidence. A claimed assessment/T2 unit without a complete or recoverable terminal
  requires explicit `--evaluation-unit` and `--retry-failed`; keep the original
  population, freeze, plan, stream and budgets. Never use `--clean` to bypass history.
- Full completion checks 36 scientific terminal units plus their bound report;
  continuation may publish `report-resume-*`. Use the verified printed report path.
  Wrapper exit `5` means blocking and `6` means incomplete execution evidence.
  Exit `0` or `execution_status=complete` does not establish scientific validity.
- The full wrapper uses one native thread per worker and 1–4 workers selected from
  physical memory (2 GiB reserved plus 5 GiB per worker; two workers on 16 GiB).
  Direct off-only execution defaults to one worker. Windows uses thread workers for
  MC bootstrap, assessment candidates and T2 replicas; other platforms use processes.

## Selected paper evidence and builds

The current paper selects `runs/h4l-off-test05/evaluation/report`, pinned by
`paper/selected-snapshot.json`, with the local aggregate snapshot at
`var/paper-evidence/test05-20260926/`. Its 80/80 nominal results, 36/36 evaluation
units and 200/200 event-MC bootstrap replicas are numerically valid. Qualification
remains `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, and `primary_claim_eligible=false`.
Historical test01 and synthetic records retain their original meaning and are
not the current manuscript's numerical source. Do not rerun or overwrite test05
for a documentation or manuscript build.

`python paper/scripts/build.py` compiles the committed six PDF figures and four
generated TeX inputs using Python's standard library and a TeX distribution with
REVTeX 4.2, BibTeX and latexmk. The default build does not read runs, snapshots or
the selection file. Output is `paper/latex/main.pdf` and remains ignored.
This multi-file manuscript uses its repository build workflow.

Only an intentional asset refresh uses
`python paper/scripts/build.py --run-name test05`, with local runs, NumPy and
Matplotlib. It verifies the pinned selection before regenerating assets; review
the resulting diff. `paper/scripts/collect_evidence.py` can export a separate
aggregate snapshot to a fresh directory without retraining, refitting, generating
Toys or opening new assessment data. Preserve ignored snapshots and source runs
separately; the committed assets suffice for ordinary compilation.

## Scientific safety

- Process controlled MC or explicitly labelled synthetic events only; never inspect,
  hash, preprocess, score, or plot real data. Do not mix 2020 and 2025 releases.
- `m4l` may be used only as explicitly defined by the versioned H4l protocol.
- Signed `physical_weight` is for physical yields; optimizer weights follow the protocol.
- Keep physical event groups together across split and fold assignments.
- Do not inspect assessment values before the protocol-defined frozen state.
- Do not tune candidates, thresholds, bins, mappings, or protocols after assessment.
- Preserve dataset identity, hashes, protocol seals, checkpoint bindings, and lineage.
- Never overwrite a completed, failed, diagnostic, or otherwise published run.
- Distinguish software tests, synthetic validation, full-MC validation, and platform compatibility checks.
- Preserve the core scope `synthetic_software_defaults_not_physics_validation`.
  Automatic P0/T1 `contract_checked` materials do not establish independent
  numerical validation, physical applicability or confirmatory eligibility.
- Finite-MC bootstrap ranges are conditional on fixed networks; five-seed ranges
  are not confidence intervals. Artificial marginal CRN coupling is not physical
  event pairing. Independent coverage and allocation sensitivity remain separate
  evidence requirements; narrower nominal intervals alone do not establish a gain.

## Change discipline

Before editing, inspect `git status --short` and preserve unrelated or untracked
user work. Keep scientific rules in protocols and domain services, not CLI code.
Update tests, schemas, examples, and documentation when a contract changes.
Generated data, models, diagnostic plots, runs, evidence snapshots, caches, build
outputs, environment directories, and package metadata must not be committed.
The paper's already tracked PDF figures and generated TeX inputs are deliberate
publication assets; refresh them only against the pinned evidence and review the
diff. Preserve the tracked environment definitions and snapshots.

Use Unix-style LF line endings for all text files in this repository. Do not
introduce CRLF line endings.

Run focused tests appropriate to the change before the full suite. For document-only
edits, verify links, command flags, source identities and scientific qualifications;
do not launch data acquisition or scientific runs solely to refresh prose. Report
exactly which checks and evidence levels were and were not verified.
