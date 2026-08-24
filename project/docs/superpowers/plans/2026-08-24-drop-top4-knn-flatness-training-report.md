# Drop-top-four kNN flatness training execution report

## Scope and frozen constraints

This report records the single authorized MC-only production attempt at
`runs/decorrelation-drop-top4-363490-2026-08-24`. The run used Git commit
`b95d07a3954407b90197f9efdd240b3a3ecda988`, the frozen input run
`runs/full-baseline-363490-2026-08-11-r2`, and
`config/decorrelation_training_drop_top4.yaml`. The output path date remains
`2026-08-24` as frozen, although execution occurred on 2026-08-25 in the
Asia/Shanghai timezone.

The production CLI was invoked exactly once in this task, only after the fresh
path and verification gates below passed. It failed, so it was not rerun into
the path. No protected real-data input was accessed, inventoried, hashed,
copied, or scored.

Those command-count, fresh-path, hash-command, test-command, and
protected-input-negative statements are controller/implementer execution
records. The committed Git diff records the report, but cannot independently
reconstruct or prove those runtime events or negative-access assertions.

Exact production command (one invocation):

```bash
.venv/bin/python -m scripts.run_decorrelation_training \
  --input-run runs/full-baseline-363490-2026-08-11-r2 \
  --config config/decorrelation_training_drop_top4.yaml \
  --run-dir runs/decorrelation-drop-top4-363490-2026-08-24
```

The command exited `1`. The run directory birth time was
`2026-08-25T05:36:50+0800`, and `failure.json` was written at
`2026-08-25T06:23:52+0800`, an observed filesystem interval of 47 minutes 2
seconds. The terminal traceback was:

```text
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/scripts/run_decorrelation_training.py", line 324, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/scripts/run_decorrelation_training.py", line 97, in main
    artifacts = build_decorrelation_artifacts(outcome, sources.config)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/scripts/run_decorrelation_training.py", line 181, in build_decorrelation_artifacts
    "oof_scores": _wide_oof_audit(results),
                  ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/scripts/run_decorrelation_training.py", line 245, in _wide_oof_audit
    raise ValueError("candidate OOF audit identity must be unique")
ValueError: candidate OOF audit identity must be unique
```

The traceback was preceded by repeated instances of this non-terminal warning:

```text
/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/sklearn/utils/validation.py:2820: UserWarning: X has feature names, but NearestNeighbors was fitted without feature names
  warnings.warn(
```

## Verification

Fresh focused verification before production:

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training.py tests/test_decorrelation_training_plots.py tests/test_decorrelation_training_run.py tests/test_run_decorrelation_training_script.py tests/test_manifest.py -q
```

Exit code `0`; complete output:

```text
........................................................................ [ 58%]
...................................................                      [100%]
123 passed in 28.61s
```

Fresh full verification before production:

```bash
.venv/bin/python -m pytest -q
```

Exit code `0`; complete output:

```text
........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
........................................................................ [ 44%]
........................................................................ [ 52%]
........................................................................ [ 61%]
........................................................................ [ 70%]
........................................................................ [ 79%]
........................................................................ [ 88%]
........................................................................ [ 96%]
..........................                                               [100%]
818 passed in 57.91s
```

Pre-production `git diff --check` exited `0` in less than 0.01 seconds with no
stdout or stderr.

Fresh final full verification after writing the report:

```bash
.venv/bin/python -m pytest -q
```

Exit code `0`; complete output:

```text
........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
........................................................................ [ 44%]
........................................................................ [ 52%]
........................................................................ [ 61%]
........................................................................ [ 70%]
........................................................................ [ 79%]
........................................................................ [ 88%]
........................................................................ [ 96%]
..........................                                               [100%]
818 passed in 58.26s
```

The following final `git diff --check` exited `0` in less than 0.01 seconds
with no stdout or stderr.

After inserting the preceding evidence, a still later fresh completion suite
was run:

```bash
.venv/bin/python -m pytest -q
```

Exit code `0`; complete output:

```text
........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
........................................................................ [ 44%]
........................................................................ [ 52%]
........................................................................ [ 61%]
........................................................................ [ 70%]
........................................................................ [ 79%]
........................................................................ [ 88%]
........................................................................ [ 96%]
..........................                                               [100%]
818 passed in 58.34s
```

Step 5 static evidence was rerun from the clean reviewed head before this fix
round. The prescribed placeholder/real-data-name `rg -n` audit exited `1` with
exact output `<empty>`; for `rg`, exit `1` means no matching line, not command
failure. `git diff --check` exited `0` with exact output `<empty>`, and
`git status --short` exited `0` with exact output `<empty>`.

After the documentation edits, the same prescribed `rg -n` audit again exited
`1` with exact output `<empty>`, and `git diff --check` again exited `0` with
exact output `<empty>`. The following `git status --short` exited `0` with this
exact expected documentation-only output:

```text
 M docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md
```

## Source hashes

Fresh-output gate:

```bash
test ! -e runs/decorrelation-drop-top4-363490-2026-08-24
```

Exit code `0` in less than 0.01 seconds with no stdout or stderr.

The exact approved two-file hash command was run before production and again
after the failure:

```bash
shasum -a 256 runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz
```

Both executions exited `0` and produced the same complete output:

```text
10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8  runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json
1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e  runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz
```

## Candidate OOF results

No immutable candidate table was published. The prescribed extraction command
was still run exactly:

```bash
.venv/bin/python -c "import pandas as pd; p='runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/candidate_results.csv'; print(pd.read_csv(p).to_string(index=False))"
```

Exit code `1`; complete output:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 873, in read_csv
    return _read(filepath_or_buffer, kwds)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 300, in _read
    parser = TextFileReader(filepath_or_buffer, **kwds)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 1645, in __init__
    self._engine = self._make_engine(f, self.engine)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 1904, in _make_engine
    self.handles = get_handle(
                   ^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/common.py", line 930, in get_handle
    handle = open(
             ^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/candidate_results.csv'
```

The prescribed working-point extraction command was also run exactly:

```bash
.venv/bin/python -c "import pandas as pd; p='runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/working_point_metrics.csv'; print(pd.read_csv(p).to_string(index=False))"
```

Exit code `1`; complete output:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 873, in read_csv
    return _read(filepath_or_buffer, kwds)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 300, in _read
    parser = TextFileReader(filepath_or_buffer, **kwds)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 1645, in __init__
    self._engine = self._make_engine(f, self.engine)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/parsers/readers.py", line 1904, in _make_engine
    self.handles = get_handle(
                   ^^^^^^^^^^^
  File "/Users/xuhongyi/Code/HiggsML/.worktrees/drop-top4-knn-flatness/project/.venv/lib/python3.12/site-packages/pandas/io/common.py", line 930, in get_handle
    handle = open(
             ^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/working_point_metrics.csv'
```

Consequently, no CSV values exist to copy or interpret.

## Terminal decision

Production terminal status: `failed`.

There is no terminal selection value and no terminal `test_opened` value. Both
are unavailable because `selection.json` and `study_manifest.json` were never
published. They must not be inferred from partial computation or the failure
location.

The prescribed JSON extraction command was run exactly:

```bash
.venv/bin/python -c "import json,pathlib; p=pathlib.Path('runs/decorrelation-drop-top4-363490-2026-08-24'); s=json.loads((p/'artifacts/selection.json').read_text()); m=json.loads((p/'artifacts/study_manifest.json').read_text()); print(json.dumps({'selection':s,'outputs':sorted(m['outputs']),'software':m['software'],'sources':m['sources']},indent=2,sort_keys=True))"
```

Exit code `1`; complete output:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/xuhongyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/pathlib.py", line 1027, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/xuhongyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/pathlib.py", line 1013, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/selection.json'
```

The exact full-precision failure JSON is:

```json
{
  "error_type": "ValueError",
  "message": "candidate OOF audit identity must be unique",
  "status": "failed"
}
```

Its SHA-256 is
`f705815394cf50f50838a53b1287db3846a97bbbcd287130d579ffac3f4ebd4c`.

## Conditional test evidence

No immutable held-out-test evidence was published. It is not scientifically
valid to claim either that the held-out test was opened or that it remained
closed: the software failed after the training outcome returned but before the
terminal selection and manifest were written. No test values are reported or
used to alter selection.

## Artifact inventory

The exact failed-path inventory is:

```text
.terminal.failed/
artifacts/
failure.json
model/
plots/
predictions/
```

Only `failure.json` is a regular file; all listed directories are empty. The
file is 115 bytes and has mtime `2026-08-25T06:23:52+0800`. The terminal-failure
marker is an empty directory with the same mtime.

The failed run has no manifest, so manifest-newer-than-artifacts and the
selected/no-selection conditional allowlist cannot be satisfied or evaluated
as successful terminal-run checks. The inventory instead matches a software
failure terminal shape. An independent path-name audit over this exact output
directory returned no forbidden real-data-name matches.

## Remaining limitations

- The production study is a software failure, not a flatness-study scientific
  result.
- Candidate and working-point full-precision values are unavailable because
  their immutable CSV artifacts were not published.
- Terminal selection and `test_opened` are unavailable and must not be
  reconstructed from partial in-memory computation.
- The specific duplicate OOF identity or identities are not persisted in the
  failure artifact, so this report does not diagnose which rows caused the
  invariant failure.
- The authorized path is terminally failed and must never be rerun or reused.
- The Git diff alone cannot independently establish one production invocation,
  pre-run path absence, execution of the recorded tests and hash checks, or the
  protected-input negative; those remain controller/implementer execution
  records preserved in this report.
