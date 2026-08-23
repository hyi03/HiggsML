# DSID 363490 Training Report Checkpoints

## Task 7 — DSID 363490 runtime: preprocessing pass, training input failure (2026-08-11)

The initial empty preprocessing wrapper result was corrected by controller
read-only inspection: PID `18044` was still running and later naturally
published the complete baseline. The full test gate passed (`479 passed in
22.81s`); baseline hashes, full-read manifest, cutflow, finite scientific
values, aggregate weights, identities, and the predeclared DSID 363490
viability gate all passed (11,976 selected; folds 1,882--1,955; test 2,373).
The exact one-time training command then failed before output claim/model fit:
the generic all-numeric-column finite check rejects four 363490-only auxiliary
normalization columns (`xsec`, `kfac`, `filteff`, `sum_of_weights`) which are
non-finite, despite finite features/mass/physical weights. No retry, code
change, new run name, plot claim, or training refusal check was made. Per the
user's Plan A scope override, frozen 700600 external validation/refusal was
not run. Historical protected paths remain SHA-256 unchanged; `FEATURES` is
still 14 fields without `m4l`; no real-data score/window artifact was created.
See `.superpowers/sdd/2026-08-11-dsid-363490-training/task-7-report.md`.

## Task 1 — Canonical ROOT Input Profiles and External Normalization

Completed 2026-08-11 without staging, committing, branching, reading event data, or using the network.

### Commands and results

RED:

```text
.venv/bin/python -m pytest tests/test_input_profiles.py tests/test_io.py tests/test_weights.py -q
ERROR tests/test_input_profiles.py
ModuleNotFoundError: No module named 'src.input_profiles'
1 error in 0.12s
```

This was expected: the test-first profile contract imported the not-yet-created `src.input_profiles` module.

GREEN:

```text
.venv/bin/python -m pytest tests/test_input_profiles.py tests/test_io.py tests/test_weights.py -q
31 passed in 0.06s
```

Required legacy regression:

```text
.venv/bin/python -m pytest tests/test_input_profiles.py tests/test_io.py tests/test_weights.py tests/test_preparation.py -q
71 passed in 0.44s
```

### Changed-file SHA-256

```text
b52582c49fbbed1bb08eab5a5baec9bc8008fa8d83763b2d8bdd25358136103a  src/input_profiles.py
e7ddcaf0523c6d543bf091724bb9cbfb042e3af5a8809bd380e03111188f5e5e  src/io.py
361758cc6dc32c4647b37be7765be4e0b16edd29e73f16d268c8c78e7cfab058  src/weights.py
1aa9df33a02356e78ebb09332778c8e30a4f354d13b91907930f68af4dd3123b  tests/test_input_profiles.py
cab6ee17491378f8a97abaab2c1491deaa6c9b3836a263c6e3d6f99b9661fc65  tests/test_io.py
3d37868faf38d0756a0fdbcbbd22259a8f9999d22f1bd1337820bc0fc2c58379  tests/test_weights.py
```

## Task 2 — Configurable Good-Lepton and Enhanced Selection

Completed 2026-08-11 without staging, committing, branching, reading event
data, or using the network.

RED evidence:

```text
.venv/bin/python -m pytest tests/test_selection.py tests/test_selection_cutflow.py tests/test_preparation_pipeline.py -q
26 failed, 52 passed in 0.50s
```

GREEN evidence:

```text
.venv/bin/python -m pytest tests/test_selection.py tests/test_selection_cutflow.py tests/test_preparation_pipeline.py tests/test_features.py tests/test_pairing.py -q
102 passed in 0.40s

.venv/bin/python -m pytest tests/test_cutflow.py -q
13 passed in 0.21s
```

The enhanced path performs stage-by-stage raw-object filtering without mutating
events, uses its own expanded cutflow tuple, and limits reconstruction to the
final four good leptons. Legacy configs retain their old stage tuple. Pipeline
profile resolution, canonical quality branch loading, and external
normalization handling were added.

Changed-file SHA-256:

```text
322df4c7972ca4d4b23305cebb4d0c4e4f66b1faac3074724b09a8980ab49686  src/selection.py
a44aeb260e6bb1ffa74e01ce19253b41eb7cb9c348bba70502f94a093c6dd6bb  src/pipeline.py
3bb1be85a5bcb62c08f8a9063286e14609a08973779c9d64d1c1535ae6c1bacb  tests/test_selection.py
86ac037c8bd7bf6860b60dbf707e54f5d52637147514ad8130c081bbff25ab5c  tests/test_selection_cutflow.py
f1376f3670cce035ab9fb40fb6b8bbf09835fc12444007de7336c77264ec8a88  tests/test_preparation_pipeline.py
```

Concern: no load-bearing blocker; real ROOT processing remains later-task scope.

## Task 3 — Per-Sample Configuration and Immutable Preprocessing

Completed 2026-08-11 without staging, committing, branching, reading event
data, or using the network. The task-scoped pre-snapshot was retained.

RED:

```text
.venv/bin/python -m pytest tests/test_prepare_script.py tests/test_manifest.py -q
7 failed, 24 passed in 0.35s
```

The intended failures exposed the missing per-sample input-profile wiring and
pre-ROOT-I/O normalization validation, plus the absent per-sample manifest
provenance interface.

GREEN:

```text
.venv/bin/python -m pytest tests/test_prepare_script.py tests/test_manifest.py tests/test_summary.py tests/test_preparation.py -q
92 passed in 0.35s

.venv/bin/python -m pytest -q
439 passed in 16.55s
```

The isolated configuration pins Higgs 345060 to Release-22 ROOT normalization,
ZZ 363490 to Open Data 2020 official metadata normalization, and data to the
Release-22 profile. The manifest records each effective profile/tree/unit/source
and the complete enhanced selection; no 1.3 correction is recorded.

Changed-file SHA-256:

```text
0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320  config/dsid363490.yaml
b3d5a4628daf4d2ad473d5a8b374ae5adea6f2047e227640e597c577599e3bcf  scripts/prepare_demo.py
85d43124f8415e5b3ef873090bd962bb753fdee19e7415f04564e2c797604c39  src/provenance.py
363a94eada05547e6583285117cc17742a612f935da61a01aaa3faaea13beb85  tests/test_prepare_script.py
441b8ad00cb4b08cb9d392907f512369cd04a8d7034991a82b97eea22e62c3e9  tests/test_manifest.py
```

Independent task review: approved with no blocking, important, or minor
findings. Concern: no real ROOT data was read or processed.

## Task 6 — Download and Inspect the Real DSID 363490 ROOT

**Blocked before acquisition on 2026-08-11.** Both the sandbox and an approved
unrestricted retry of the required official CERN HTTPS `curl` command exited
with DNS error 6 (`Could not resolve host: atlas-opendata.web.cern.ch`) after
the configured retries. No `.part` or final artifact exists, and both target
paths were confirmed absent and not symlinks before and after the attempts.

The prescribed EOS fallback cannot run here: `xrdcp`, `xrdfs`, and `root` are
unavailable. Consequently no DSID/tree/branch/normalization validation,
checksum, promotion, preprocessing, or training was performed. The complete
pre/post protected file inventory, with SHA-256 values and the failure evidence,
is recorded in `.superpowers/sdd/2026-08-11-dsid-363490-training/task-6-report.md`.
All protected file records were identical before and after; `data_events` was
not decompressed or inspected.

## Task 6 — Corrected CERN Record 15005 Acquisition (completed)

The preceding Task 6 DNS blocker concerned a superseded, incorrect URL. With
the corrected official source
`https://opendata.cern.ch/record/15005/files/mc_363490.llll.4lep.root`, fresh
preflight and protected inventories succeeded. Sandbox DNS failed as expected;
the approved retry of the same URL downloaded one temporary file successfully.

Before promotion, `uproot` verified the only ROOT TTree is `mini`, it has
`554279` rows, all `channelNumber` values are `363490`, and every Task 1
Open Data 2020 physical branch is present. No per-event normalization metadata
fields exist, so the dedicated configuration's official external metadata is
the source: `1.2564 pb`, `1.0`, `1.0`, and `7538705.808`.

The verified `179082866`-byte artifact has SHA-256
`76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`.
After a second absence/symlink check, it was atomically published with
no-overwrite semantics as `data/raw/zz_363490.root` and set read-only (`0444`);
the `.part` name is absent. The final protected inventory matches the fresh
preflight except for this permitted new ROOT file. No preprocessing, training,
Git operation, or real-data inspection occurred. Full branch and inventory
evidence is in `.superpowers/sdd/2026-08-11-dsid-363490-training/task-6-report.md`.

A final attempt through the in-app browser used the identical official CERN
HTTPS URL. It produced no download event within 120 seconds, and the browser's
URL security policy then refused further inspection or alternate browser
workarounds. The browser session was closed; both the `.part` and final ROOT
paths remain absent.

## Task 7B — Fresh Corrected DSID 363490 Baseline and Training

Fresh r2 preprocessing and MC-only training each ran exactly once after a 480-pass gate. Preprocessing selected 11,976 DSID 363490 rows with split 7,174/2,429/2,373 and exact finite normalization 1.2564/1.0/1.0/7538705.808. Training chose `depth4_child20`, 998 trees, OOF/test AUC 0.885296/0.894054; same-path refusals occurred pre-load with immutable hashes. Seven MC plots show Higgs near 125 GeV and broad inclusive ZZ, but frozen working points visibly sculpt ZZ (OOF KS 0.291/0.408/0.458; test 0.324/0.432/0.473), despite configured warning=false. No selection changed. Full evidence: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-7b-report.md`.

## Task 8A — Feature-tuple parameterization

Task 1 of the mass-sculpting ablation plan is complete under TDD. The model layer now accepts a validated explicit ordered subset of frozen `FEATURES` for CV, final fit, and scoring, while the production CLI continues to score with the default 14 features. Tests lock exact matrix-column order and factory-before-invalid-feature rejection. This also repairs the Task7C reviewer’s stale script scorer seam. Verification: Task7C related 128 passed in 29.79s; Task8A model/CLI/run-contract 128 passed in 29.18s; full suite 489 passed in 36.97s. Immutable r2 inventories are unchanged. Evidence: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-8a-report.md`.

## Task 8B — Development-only mass-sculpting ablation core

Task 2 is complete under strict TDD. It introduces only the sealed study module,
its tests, and a validated public ZZ diagnostic wrapper. The exact 10/8/7
ordered safe-feature profiles are constrained by the frozen feature contract;
development evidence is OOF-only. Eligibility is literal (AUC >= 0.80, all ZZ
KS <= 0.10, signal efficiency strictly above target), and selection resolves
ties by AUC, maximum KS, then name. A recording factory locks test access out
until final selection and proves final test scoring happens once. Verification:
focused 25 passed; related 153 passed; full 499 passed. Task 8A hashes and r2
sentinels remain unchanged. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.

### Task 8C — sealed mass-sculpting ablation workflow

The safe study runner is complete. It binds the immutable Task 4A/4B sources,
loads the MC table only after atomically claiming a fresh output directory,
performs selection on development rows only, and opens held-out test only if a
profile passes the frozen eligibility gates. Publication uses an exact
conditional allowlist, source/output hashes and row counts, failure-terminal
behavior, and a manifest published last. An initial independent review found
one Critical and two Important boundary defects; all were reproduced by RED
tests, repaired, and independently approved. Pre-run full verification was
`535 passed`. Evidence: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-8c-report.md`.

### Task 8D — real DSID 363490 result and version 1.0 terminal

The approved real study completed once at
`runs/mass-ablation-363490-2026-08-11` with terminal result
`no_eligible_profile`. The full-14 reference has OOF AUC `0.885296` but maximum
ZZ KS `0.457954`. The three predeclared simpler profiles give AUC/max-KS
`0.799653/0.344692`, `0.756382/0.171962`, and `0.744706/0.202488`; none meets
both AUC >= 0.80 and all working-point KS <= 0.10. Therefore held-out test was
not opened and no model/test artifacts were produced. Same-path refusal,
manifest/source/output hashes and row counts, and immutable r2/ROOT hashes were
verified. Independent review approved the scientific terminal with one
presentation-only minor (the rightmost plot annotation is clipped). Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8d-report.md`.

### Task 8B Fix Round 1 — reviewer hardening

The review found and verified two seals missing from the initial core: all four
working-point evidence mappings must have the exact common
`{loose, medium, tight}` keyset, and raw eligible results must not reach test
scoring without selection. Strict RED (6 failed, 7 passed) preceded a minimal
fix: selection issues a frozen private-token certificate, and final scoring
requires it before reading the test split; the canonical keyset gate rejects
missing, extra, or inconsistent evidence. Focused 13 passed, related 157
passed, and full 503 passed. Task 8A and r2 hashes remain unchanged. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.

### Task 8B Fix Round 2 — substitution-proof selected result

Review then established that `dataclasses.replace` could retain the first
certificate while replacing its result with a different eligible profile. A
strict RED reproduced the bypass (1 failed, 12 passed). The minimal fix makes
each private frozen certificate carry the exact selected result and requires
object-identity agreement before any test split access. Focused 13 passed,
related 157 passed, and full 503 passed; Task 8A and r2 sentinels remain
unchanged. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.

### Task 8B Fix Round 3 — non-copyable selected capability

Nested certificate replacement bypassed the Round 2 result binding. Its RED
was reproduced on the sealed frame. An initial capability patch exposed an
unchanged-wrapper clone during the required third-round architecture review, so
the design was hardened with a private non-dataclass, `__slots__`, non-copyable
certificate that binds exactly once to its original wrapper. Post-init and the
final helper check both wrapper and result identities before test access. The
sealed test covers raw, replacement, nested-replacement, and shallow/deep-copy
routes. Focused 13 passed, related 157 passed, and full 503 passed; Task 8A and
r2 sentinels remain unchanged. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.

### Task 8B architecture redesign — atomic test opening

The revised design replaces the capability-token approach altogether. The old
single-result/certificate APIs were removed. Development reporting still uses
the pure selector, while the only test-opening API requires all three exact
predeclared profile results, validates their keys/names/ordered tuples, and
then recomputes selection internally. Invalid maps reject before frame/model
access; no eligible result returns without test access; a selected result is
fit and test-scored once. RED observed the expected missing new API; focused 35
passed, related 163 passed, and full 509 passed. Independent review confirmed
the ordering and no caller-selected path; Task 8A and r2 sentinels are
unchanged. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.

### Task 8B architecture Fix v2 — internal results and fixed gates

The first atomic API still exposed eligibility overrides and caller-supplied
development results. Fix v2 removes both: the sole test-opening call now
accepts only frame, policy, and optional model factory; evaluates the three
canonical profiles itself; applies the fixed gate internally; and returns a
frozen outcome containing all development results, selection, and optional test
evidence. Strict RED showed 5 failures; focused 18 passed, related 162 passed,
and full 508 passed. Revised design/plan, Task 8A hashes, and r2 sentinels are
unchanged except for the documented interface revision. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.

### Task 8B architecture Fix v3 — sealed canonical definition and snapshots

Fix v2 still consulted the public profile mapping at runtime and exposed
evaluator-owned objects through its outcome. Strict RED monkeypatched that
mapping to one/altered profiles and mutated original nested maps/OOF frames;
both leaked. The final implementation closes over the original canonical tuple
at definition time, while preserving the public three-argument signature, and
publishes only frozen map snapshots and defensive table copies. Focused 21
passed, related 165 passed, and full 511 passed. Final review found no runtime
public-mapping or nested-evidence alias; Task 8A and r2 sentinels remain
unchanged. Evidence:
`.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`.
