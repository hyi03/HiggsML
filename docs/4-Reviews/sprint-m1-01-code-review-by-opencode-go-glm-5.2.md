# Sprint M1-01 / FR-001 Implementation Code Review Report

- **Reviewer:** opencode-go / glm-5.2
- **Review date:** 2026-09-01
- **Review type:** Code review (implementation review; no implementation, test, doc, or lock file was modified — this report is the only file written)
- **Reviewed implementation (Sprint M1-01 scope):**
  - `neural/pyproject.toml`, `neural/environment.yml`
  - `neural/AGENTS.md`, `neural/README.md`
  - `neural/src/config.py`, `neural/src/cli/preprocess.py`, `neural/src/cli/train.py`
  - `neural/src/artifacts/transaction.py`
  - `neural/tests/unit/test_package_contract.py`, `neural/tests/unit/test_transaction.py`, `neural/tests/integration/test_cli_help.py`
  - Directory skeleton and `.gitkeep` files (`config/`, `data/`, `runs/`, `tests/fixtures/`, `tests/golden/`, `src/` subpackages)
  - Existing `neural/osx.yml` and `neural/win.yml` — checked only for environment-contract consistency (not review targets for content beyond that)
- **Sources of truth (requirements):**
  - `neural/docs/FR-001-adversarial-mlp-refactor.md` (v1.1, confirmed)
  - `neural/docs/sprint-m1-01.md`
  - `docs/4-Reviews/sprint-m1-01-review-confirm.md` (decision table is binding follow-up)
  - `AGENTS.md` (repository root)
  - `neural_adversarial_mlp_refactor_design.md` (§5, §6, §11, §13 阶段 1)
- **Out of scope, per task:** all M1-02…M1-06 functionality (ROOT reading, preprocessing science, training, OOF, qualification, test-opening, manifest schema, artifact SHA-256, gzip canonical hashing) is **not** treated as missing M1-01 scope.

---

## 1. Executive Summary

The M1-01 skeleton is well built and behaves correctly in every executed check. On the win-64 development platform (Conda env `pytorch`, installed from `win.yml`): the full test suite passes (8/8), `pip check` is clean, both `higgsml-preprocess --help` and `higgsml-train --help` exit 0 with stable `usage:` lines, exactly two console entry points are published, a static AST guard proves `src/` never imports `xgboost`, and the run transaction verifiably refuses existing targets, path escape, and equal-to-root targets, publishes atomically, and writes failure receipts. Exit codes 0/2/3/4/5/70 are defined consistently in `neural/AGENTS.md`, `README.md` §3, and `src/config.py`. `xgboost/` and all tracked files are untouched; no scientific processing or training results are claimed anywhere.

One **High** finding blocks a clean sign-off of the sprint's environment deliverable: **`neural/environment.yml` omits `conda-lock` from the design §11 baseline**, while both frozen locks were solved from an env file that *did* declare it (both locks install `conda-lock 4.0.2`, and the `pytorch` env created from `win.yml` contains it). As a result, the `metadata.content_hash` recorded in `osx.yml`/`win.yml` no longer matches the committed `environment.yml` — proven by recomputing the hashes with conda-lock 4.0.2: the committed file hashes to different values, while adding unpinned `conda-lock` reproduces the recorded hashes **exactly**. This violates sprint §5.1 (「从设计第 11 节基线创建 `environment.yml`，并核对现有 `osx.yml` 与 `win.yml` 的直接依赖版本」) and review-confirm decisions #5/#17 (「`environment.yml` 需描述同一直接依赖集合」), and makes the README §1.5 regeneration flow a silent-drift hazard.

Two **Medium** findings: the usage/transaction exit-code test paths expected by review-confirm #13 are not covered (no test asserts exit code 2), and `neural/runs/`/`neural/data/` contents have no ignore rules, risking future commits of run outputs against root `AGENTS.md`. The remaining findings are Low (transaction TOCTOU and nested-target edge cases, orphaned staging dirs, untested transaction guard paths, unaddressed 「统一日志」 goal, duplicated dependency pins) and Info (deferred exit-code wiring, stub semantics, test fidelity, packaging notes, scope interpretations, and a positive verification summary).

**Verdict: conditionally approvable.** All sprint §6 acceptance criteria pass on the development platform, and no scientific-safety constraint is violated. The High environment-contract inconsistency must be corrected (one-line fix, verified below) before M1-02 relies on the environment contract or anyone regenerates the locks; the two Medium items should land with or before M1-02.

**Findings count:** 0 Critical · 1 High · 2 Medium · 6 Low · 8 Info.

---

## 2. Verification Performed (win-64 development platform)

All commands were executed during this review from `neural/` in the `pytorch` environment installed from `win.yml`. Per `neural/AGENTS.md`, this is development verification only — **no authority (osx-arm64) claim is made**, and none was found in the deliverables.

| Check | Command / method | Result |
|---|---|---|
| Full test suite | `conda run -n pytorch python -m pytest -q` | **8 passed** in 0.30s |
| Dependency consistency | `conda run -n pytorch python -m pip check` | **No broken requirements** |
| CLI smoke (preprocess) | `conda run -n pytorch higgsml-preprocess --help` | rc 0, `usage: higgsml-preprocess [-h]` |
| CLI smoke (train) | `conda run -n pytorch higgsml-train --help` | rc 0, `usage: higgsml-train [-h]` |
| Usage-error exit code | `main(['--bogus'])` via `python -c` | argparse error, **exit code 2** |
| Entry points | `pyproject.toml` + installed scripts + `pip show higgsml-neural` | exactly `higgsml-preprocess`, `higgsml-train`; editable install present |
| xgboost isolation | AST guard test + manual review of `src/` | no `xgboost` imports; test passes |
| Transaction semantics | unit tests + direct probes in a temp directory | atomic publish, existing/outside/equal-to-root rejection, failure receipt, `abort_without_receipt`, double-publish rejection all behave correctly; nested-target publish fails with raw `FileNotFoundError` and orphans staging (see findings) |
| Lock ↔ env contract | package/version extraction from both locks; content-hash recomputation with conda-lock 4.0.2 (`conda_lock.src_parser.make_lock_spec` + `conda_lock.content_hash.compute_content_hashes`) | all shared pins match; **`conda-lock` present in locks, absent in `environment.yml`; content hashes do not match the committed file** (§3) |
| Env contents vs lock | `conda list -n pytorch` | `conda-lock 4.0.2` installed from the lock but not declared in `environment.yml` |
| Repo immutability | `git status --porcelain` | only untracked `docs/` and `neural/`; no tracked file modified; `xgboost/` untouched |

---

## 3. Environment / Lock Contract Check (High finding detail)

### 3.1 Direct-dependency comparison

| Direct dependency | design §11 baseline | `environment.yml` | `osx.yml` | `win.yml` |
|---|---|---|---|---|
| Python | 3.12.13 | 3.12.13 | 3.12.13 | 3.12.13 |
| NumPy | 2.5.1 | 2.5.1 | 2.5.1 | 2.5.1 |
| pandas | 3.0.5 | 3.0.5 | 3.0.5 | 3.0.5 |
| PyYAML | 6.0.3 | 6.0.3 | 6.0.3 | 6.0.3 |
| uproot | 5.7.5 | 5.7.5 | 5.7.5 | 5.7.5 |
| scikit-learn | 1.9.0 | 1.9.0 | 1.9.0 | 1.9.0 |
| matplotlib | 3.11.1 | 3.11.1 | 3.11.1 | 3.11.1 |
| mplhep | 1.3.2 | 1.3.2 (pip section) | 1.3.2 (pip-managed) | 1.3.2 (pip-managed) |
| awkward | 2.12.0 | 2.12.0 | 2.12.0 | 2.12.0 |
| vector | 1.8.1 | 1.8.1 | 1.8.1 | 1.8.1 |
| tqdm | 4.70.0 | 4.70.0 | 4.70.0 | 4.70.0 |
| PyTorch | 2.7.1 CPU | 2.7.1 | 2.7.1 (`cpu_generic`) | 2.7.1 (`cpu_mkl`) |
| pytest | unpinned | unpinned | 9.1.1 | 9.1.1 |
| **conda-lock** | **listed (L429)** | **absent** | **4.0.2** | **4.0.2** |

Platforms (`osx-arm64` / `win-64`), channel (`conda-forge`), `metadata.sources: [environment.yml]`, and the generic `YOURENV` header (accepted as-is per review-confirm #9 — do not hand-edit generated locks) are all consistent. The locks were **preserved, not regenerated** (see §3.2), which respects sprint §5.1's 「不得手工编辑生成 lock」. The single divergence is `conda-lock`.

### 3.2 Content-hash proof

Recomputed with conda-lock 4.0.2 (the version recorded in both locks and installed in the `pytorch` env), emulating `--platform` via `make_lock_spec(..., platform_overrides=[platform])`:

| Input environment file | osx-arm64 hash | win-64 hash |
|---|---|---|
| Recorded in lock metadata | `b1362e69ce7afd0faa1ab18431e273a7b834c64bed2a6aa974fa262d1b76f427` | `ee1d2df82142a610cdcecaaa9c0a43a156391556382fc4e5348de1a81a17ed31` |
| Committed `environment.yml` (as-is) | `db2160ccacb3e09209ac73a300d0a7d03e774a84715414e2566eeed5797259e1` ✗ | `b90b47e4f4448f80cdb51421b259106df9d1f543d03d76756164484927765378` ✗ |
| Committed file **+ unpinned `conda-lock`** | `b1362e69…f427` — **exact match** | `ee1d2df8…ed31` — **exact match** |
| Committed file + `conda-lock=4.0.2` (pinned) | `491473bd…` ✗ | `80a05d8c…` ✗ |

Conclusions, in order of certainty:

1. The frozen locks were generated from an `environment.yml` that declared **unpinned** `conda-lock` (two independent 256-bit hash matches).
2. The committed `neural/environment.yml` therefore **does not describe the same direct-dependency set** that produced the locks, and its content hash differs from what both locks record — conda-lock will treat the locks as stale relative to the declared source, and any README §1.5 regeneration would silently drop `conda-lock` and change both `content_hash` values, drifting from the baseline that review-confirm #5/#17 said to preserve.
3. The `pytorch` env installed from `win.yml` contains `conda-lock 4.0.2` — a package the committed `environment.yml` does not declare, confirming the lock-level dependency is real, not decorative.
4. Adding `- conda-lock` (unpinned) to `environment.yml` is a **verified, exact** restoration of the recorded hashes — the recommended minimal fix (see H1 below).

This follows up the prior document review's expectation (`sprint-m1-01-review-by-opencode-go-glm-5.2.md`, final Info row: `environment.yml` 「should reproduce them (same direct dependencies, ideally the same `content_hash`)」) — the versions were reproduced, but the hash was not.

---

## 4. Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Environment contract / Reproducibility | `neural/environment.yml` L4–19 vs `neural/osx.yml` / `neural/win.yml` `metadata.content_hash`; design §11 L415–430 | `environment.yml` omits `conda-lock` from the design §11 baseline. Both locks were solved from an env file declaring unpinned `conda-lock` (locks install `conda-lock 4.0.2`; the `pytorch` env from `win.yml` contains it), so the committed file no longer describes the same direct-dependency set as the frozen locks, and the locks' recorded `content_hash` no longer matches it. Regenerating per README §1.5 would silently change the locks. | Design §11 L429 lists `conda-lock`; both locks contain `conda-lock 4.0.2` (manager: conda); `conda list -n pytorch` shows it installed. Hash recomputation (§3.2): recorded `b1362e69…`/`ee1d2df8…` vs committed-file `db2160cc…`/`b90b47e4…` (mismatch); committed file + unpinned `conda-lock` reproduces recorded hashes exactly. Violates sprint §5.1 L55 (「从设计第 11 节基线创建 environment.yml，并核对现有 osx.yml 与 win.yml 的直接依赖版本」) and review-confirm #5/#17 (「environment.yml 需描述同一直接依赖集合」). | Add `- conda-lock` (unpinned) to `environment.yml` — verified to restore exact `content_hash` equality with both frozen locks. Alternatively, if `conda-lock` is deliberately excluded from the runtime env, regenerate both locks through the README §1.5 review flow and treat the new locks as the re-baselined authority (never hand-edit). Add a contract test asserting the direct-dependency set of `environment.yml` equals the locks' top-level set, and/or that computed content hashes equal the recorded ones. |
| Medium | Test coverage / Exit-code behavior | `neural/tests/integration/test_cli_help.py` L9–24; `neural/tests/unit/test_transaction.py` (whole file) | The usage and transaction exit-code paths expected by review-confirm #13 (「并测试 usage/transaction 路径」) are not covered: no test asserts that a CLI usage error exits 2 (verified manually only), and transaction failures are tested only as `RunPathError` exceptions, never as process exit codes (codes 3/4/5/70 are unobservable — no CLI wiring exists yet). | Suite = 8 tests: 2 package-contract, 4 transaction unit (exception level), 2 `--help` (rc 0 only). Manual `main(['--bogus'])` → exit 2. Review-confirm #13 follow-up: 「在 neural/AGENTS.md/README 定义 0、2、3、4、5、70 的稳定含义并测试 usage/transaction 路径」 — definitions exist (`neural/AGENTS.md`, `README.md` §3, `src/config.py`), the usage-path test does not. | Add a parametrized subprocess test now asserting rc 2 for bad arguments on both CLIs. When M1-02 wires application services, map exceptions to `ExitCode` (RunPathError→4, binding→3, refusal→5, catch-all→70) and add one CLI-level test per code. |
| Medium | Repository hygiene / AGENTS compliance | `neural/runs/.gitkeep`, `neural/data/.gitkeep`; root `.gitignore` | The skeleton commits `runs/` and `data/` placeholders but adds no ignore rules for their contents; root `.gitignore` ignores only `xgboost/data`, `xgboost/runs`, `xgboost/tmp`. Future run outputs and local ROOT data under `neural/` would be untracked-but-committable, violating root `AGENTS.md` (「Do not commit generated data, run outputs, models, plots…」) and FR R6 run-immutability discipline. | `git check-ignore neural/runs/foo.txt neural/data/foo.root` → no rule matches (only `*.egg-info/` matched in the same invocation); `.gitignore` has `xgboost/data`, `xgboost/runs`, `xgboost/tmp` but no `neural/` entries. | Before the first real run (M1-02), add e.g. `neural/runs/*` + `!neural/runs/.gitkeep` and `neural/data/*` + `!neural/data/.gitkeep` (or ignore the directories and force-add the `.gitkeep` files), mirroring the `xgboost/` pattern. |
| Low | Atomicity / race condition | `neural/src/artifacts/transaction.py` L65–71 (`_publish`) | Check-then-rename TOCTOU: between the `run_dir.exists()` re-check (L68–69) and `path.replace(run_dir)` (L70), another process can create the target. On POSIX, `rename` onto an existing **empty** directory succeeds silently — the one case that violates the never-overwrite contract; on Windows it raises a raw `PermissionError` that is neither `RunPathError` nor mapped to exit code 4. | Code L68–70; `os.replace` semantics (POSIX `rename(2)` replaces an empty-dir target; Windows raises `PermissionError` for an existing directory target). No exclusive-claim primitive is used. Practical risk today is low (unique run ids, single operator). | Wrap the `replace` in try/except `OSError` and re-raise as `RunPathError` (fail-closed with the contract error type). Optionally reserve the name exclusively first (e.g., `os.mkdir(run_dir)` as the atomic claim, then publish into it) or document the residual race in the module docstring. |
| Low | Correctness / error typing | `neural/src/artifacts/transaction.py` L27–37 (`_validate_target`) vs L65–71 | A nested target (`allowed_root/sub/run-001`) passes validation (inside root, does not exist) but its parent directory is never created; publish then fails with a raw `FileNotFoundError`, no failure receipt is written, and the staging directory is orphaned. The API accepts a shape it cannot publish. | Empirical probe (this review, temp dir): constructor accepted `runs/sub/run-001`; `_publish()` raised `FileNotFoundError: [WinError 3] … '<staging>' -> 'runs\sub\run-001'`; staging dir left in place. Design/FR usage is flat `runs/<id>` only (design §6.1–§6.3, §10). | At construction, require `run_dir.parent` to exist and lie under (or be) the allowed root — or restrict targets to one level below the allowed root — raising `RunPathError` otherwise, so the failure type and receipt semantics stay uniform. |
| Low | Cleanup / exception handling | `neural/src/artifacts/transaction.py` L42–63 (`__exit__`), L23–24 (staging creation) | On the failure path, if writing `failure.json` or the subsequent `_publish()` raises, the new exception replaces the original (implicit context chaining only) and the staging directory is left behind. A transaction constructed but never entered also leaks its `.name.uuid.tmp` staging dir (no finalizer; `abort_without_receipt` must be called manually). | `__exit__` L53–62 performs the receipt write and publish unguarded; the constructor eagerly creates the staging dir (L24); only `abort_without_receipt` (L73–77) removes it. | Guard the receipt-write/publish steps, chain and re-raise the original exception, and define cleanup semantics (e.g., remove staging if the receipt itself cannot be written; keep it with a receipt when publish fails). A later sprint may add a startup sweep for orphaned `.*.tmp` dirs under the runs root. |
| Low | Test coverage | `neural/tests/unit/test_transaction.py` L11–47 | Public API `abort_without_receipt` and several guard paths are untested: double publish (`RuntimeError`), target equal to allowed root, publish-after-abort, `BaseException` (e.g., `KeyboardInterrupt`) still publishing a receipt, and staging placement inside the allowed root. All behave correctly today (verified manually during this review) but are not frozen by tests. | The module contains exactly 4 tests (atomic publish, existing target, outside root, failure receipt). Sprint §9 L116: 「事务 API 在后续 Sprint 扩展时必须保持不可覆盖和失败收据语义」 — semantics that only tests can pin down. | Add unit tests for the listed paths before M1-02 extends the transaction (manifest/hash publication will build directly on it). |
| Low | Requirement traceability | `neural/src/` (absent); `neural/docs/sprint-m1-01.md` §5.2 L65; design §13 L497 | 「统一日志」 (unified logging) is named in the work-package goal and in design 阶段 1, but no logging convention or helper exists in the implementation, and no checklist item or deferral note covers it — the goal is silently unaddressed. | Sprint §5.2 目标 L65 「建立统一日志、异常退出码、允许根目录校验和不可覆盖事务」; design L497 「配置源码安装、日志、异常退出码、不可覆盖 run 事务」; no `logging` usage anywhere in `neural/src/` (search verified); the §5.2 task checklist (L69–76) omits logging. | Land a minimal logging setup (logger naming, format, stream convention) together with the first application service in M1-02, or record the deferral explicitly in the sprint documentation so the goal is tracked rather than dropped. |
| Low | Packaging / drift risk | `neural/pyproject.toml` L11–23 vs `neural/environment.yml` L4–19 | The pinned runtime dependencies are manually duplicated between `pyproject.toml` and `environment.yml` with no automated consistency check; a future edit to one file can silently diverge from the other (they are in sync today). | Both files carry identical pins for the 11 shared libraries + mplhep (verified against both locks during this review); no test compares them. | Add a unit test that parses both files and asserts pin equality (allowing `environment.yml`-only tooling such as pytest/pip/conda-lock), turning this class of drift into a test failure. |
| Info | Exit-code behavior (deferred wiring) | `neural/src/config.py` L6–12; `neural/src/cli/preprocess.py` L16–18; `neural/src/cli/train.py` L16–18 | `ExitCode` defines 0/2/3/4/5/70 and 0/2 are observable (SUCCESS return; argparse usage error exits 2 — verified), but 3/4/5/70 have no handler, and an unexpected internal error in `main()` today exits 1 (Python default traceback) rather than 70. Expected for a stub CLI with no run logic. | `main()` bodies only call `parse_args` and return SUCCESS; no try/except mapping exists anywhere in `src/`. | When application services land (M1-02+), wrap `main()` with the exception→`ExitCode` mapping (RunPathError→4, binding→3, refusal→5, unexpected→70) and cover each code with a CLI-level test, per the stable-exit-code table in `neural/AGENTS.md`. |
| Info | CLI behavior (stub semantics) | `neural/src/cli/preprocess.py` L16–18; `neural/src/cli/train.py` L16–18 | Bare invocation (`higgsml-preprocess` with no arguments) currently exits 0 as a silent no-op. Consistent with the sprint's 「两个空 CLI」 goal, but a calling script could mistake rc 0 for "preprocessing ran". | `parse_args(argv)` defines no required arguments; `main()` returns 0 for empty argv (verified). | In M1-02, make `--protocol`/`--run-config`/`--run-dir` (and the train subcommand + its inputs) required so missing arguments exit 2; until then, the stub status is already documented in `README.md` L7. |
| Info | Test fidelity | `neural/tests/integration/test_cli_help.py` L17–18 | The smoke test invokes `python -m src.cli.preprocess --help` rather than the installed `higgsml-preprocess` script; entry-point correctness is covered statically by `test_exact_console_entry_points` instead. The documented `conda run -n pytorch higgsml-preprocess --help` was additionally verified manually during this review and works. | L18 `[sys.executable, "-m", module, "--help"]`; `pyproject.toml` L25–27 scripts; both invocation styles verified working. | Acceptable as-is for M1-01. Once a CI story exists, consider testing the installed scripts directly (skippable when the package is not installed). |
| Info | Packaging (accepted design decision, residual risk) | `neural/pyproject.toml` L29–31; `neural/higgsml_neural.egg-info/top_level.txt` | The top-level importable package is literally named `src` (design §6; review-confirm #14 rejected renaming). Any other editable project exposing a top-level `src` module collides in site-packages. No collision observed in this environment. | `[tool.setuptools.packages.find] include = ["src*"]`; egg-info `top_level.txt` = `src`; review-confirm #14 「按设计实现并增加精确 entry-point/import 测试；实际冲突才回到设计门」 — those exact tests exist (`test_exact_console_entry_points` + importable package). | Keep the exact entry-point/import contract tests; revisit only if a real collision is demonstrated, per the confirm decision. |
| Info | Test infrastructure | `neural/tests/` (no `conftest.py` anywhere under `neural/`) | Tests import `src.*`, which resolves via the editable install or via CWD insertion from `python -m pytest` (the documented command). Bare `pytest` on a fresh checkout without installing the package would fail with ImportError (pytest's prepend import mode inserts `tests/unit`/`tests/integration`, not the project root). | No `conftest.py` in the file tree; README §1.4 installs the package (`pip install --no-deps -e .`) before the test command, so the documented flow is safe; this review's runs used `python -m pytest`. | Acceptable because README installs first. Optionally add an empty root `conftest.py` so `src` is importable under any invocation style. |
| Info | Scope interpretation (skeleton completeness) | `neural/src/domain|preprocessing|training/` (`__init__.py` only); sprint §5.1 L53–54; design §5 L83–133 | The skeleton creates all design §5 directories (with package `__init__.py` and `.gitkeep` in empty dirs) but none of the module files (`four_vectors.py`, `root_reader.py`, `network.py`, `manifest.py`, …). This matches the directory-only reading of 「创建设计第 5 节规定的完整目录骨架…后续模块只建空骨架，不提前实现」 (review-confirm #12); module skeletons are left to their owning sprints. | File tree: `src/domain/__init__.py` etc. with no module files; design §5 tree lists 20+ module files; sprint §4 defers all science modules. | No action needed if the directory-only reading is intended; M1-02+ should create each module's skeleton as it implements it, keeping the design §5 mapping visible. |
| Info | Guard scope | `neural/tests/unit/test_package_contract.py` L20–32 | The xgboost guard is a static AST check of `import xgboost` / `from xgboost…` across `src/**/*.py`; dynamic imports (`importlib.import_module("xgboost")`, `__import__`) would evade it. The sprint allows 「依赖图或导入守卫」 (either), so the requirement is satisfied. | L25–31 match logic covers plain and `from xgboost.*` imports only; no runtime guard (e.g., `sys.modules` block or meta-path hook) exists. | When real I/O and training code exist (M1-02+), consider a runtime guard in integration tests (block `xgboost` imports during test runs) to complement the static check. |
| Info | Positive / Verified | Whole M1-01 implementation | (Verification summary — no defect.) | On win-64 (`pytorch` env from `win.yml`): pytest 8/8 passed; `pip check` clean; both `--help` smokes rc 0 with stable `usage:` lines (explicit `prog=` makes output invocation-independent); exactly two entry points (asserted by test); AST guard passes; transaction verified for atomic publish, existing/outside/equal-to-root rejection, failure receipt, abort, and double-publish rejection; exit-code tables identical in `neural/AGENTS.md`, `README.md` §3, `src/config.py`; both locks' shared direct-dependency versions match; `git status` shows no tracked-file modifications (`xgboost/` untouched); README states M1-01 skeleton status and claims no scientific results. | Preserve these semantics (non-overwrite, failure receipts, two-entry-point contract, exit codes, MC-only wording) when extending in M1-02+. ARM64 authority verification remains unperformed and unclaimed, consistent with `neural/AGENTS.md`. |

---

## 5. Detailed Observations

### 5.1 Run transaction (`src/artifacts/transaction.py`)

The design is fundamentally sound and matches the sprint's R6 subset exactly:

- **Allowed-root containment** (L27–37): both paths are `resolve(strict=False)`-normalized first, so relative paths, `..` segments, and — importantly — **symlink escapes** are resolved before the containment check; `os.path.commonpath` then enforces containment, with the cross-drive `ValueError` (Windows) caught and treated as escape; `run_dir == allowed_root` is explicitly rejected; an existing target — directory *or* file — is rejected. All rejection paths raise the single contract error `RunPathError`.
- **Atomic publication** (L23–24, L65–71): the staging directory `.name.<uuid>.tmp` is created **inside the allowed root**, guaranteeing same-filesystem atomic `replace`; publication is a single rename, so "incomplete publication" is structurally impossible (there is no partial-publish window), which satisfies 「拒绝…不完整发布」 by construction.
- **Failure receipts** (L42–63): any exception inside the `with` block — including `BaseException` subclasses such as `KeyboardInterrupt` — writes `failure.json` (`status`/`error_type`/`message`) and still publishes the run directory, matching 「失败 run 也必须保留失败收据，不得伪装为成功」. `__exit__` returns `False`, so the exception propagates (fail-closed).
- **`abort_without_receipt`** (L73–77): removes only this transaction's unpublished staging dir; idempotent; correctly refuses to act after publish.

The residual weaknesses are the four Low findings: the check-then-rename race (worst case: silent replacement of an empty pre-existing directory on POSIX), the nested-target shape that validates but cannot publish, unguarded receipt-write/publish on the failure path (exception masking + orphaned staging), and the untested guard paths. None of these break the sprint's acceptance criteria; all should be tightened before M1-02 builds manifest/SHA-256 publication on top of this class.

### 5.2 CLI and exit codes

Both CLIs are honest stubs: parse arguments, return `ExitCode.SUCCESS`. The explicit `prog=` names make `--help` output stable across invocation styles (`python -m`, installed script) — the integration test relies on this correctly. The exit-code table (0/2/3/4/5/70) is defined identically in three places (`neural/AGENTS.md`, `README.md` §3, `src/config.py`) and matches sprint §5.2 L74 exactly; codes 0 and 2 are already real (verified: usage error exits 2). Codes 3/4/5/70 and the 70-mapping for unexpected errors necessarily await application services — acceptable for M1-01, tracked as Info findings with concrete wiring guidance.

### 5.3 Packaging and import isolation

`pyproject.toml` publishes exactly the two design §6 entry points with the exact design module paths, pins the same runtime versions as the environment contract, restricts `requires-python` to 3.12 (matching `python=3.12.13`), and configures setuptools to discover only `src*` (tests, config, data, runs are excluded). The static AST guard plus the entry-point equality test satisfy sprint §5.1's isolation requirement; the top-level `src` name is the accepted design decision (review-confirm #14) with its residual collision risk noted as Info. The generated `higgsml_neural.egg-info/` is correctly ignored by the root `.gitignore` (`*.egg-info/`).

### 5.4 Documentation and scientific safety

`neural/AGENTS.md` correctly inherits root `AGENTS.md` (「may narrow… never relax」) and fixes MC-only, forbidden features, weight semantics, development/test isolation, no post-hoc relaxation, frozen-run immutability, the exit-code table, and the educational/technical-demo framing — satisfying sprint §5.1 L58 and review-confirm #6. `README.md` carries the correct `pytorch` + three-file environment contract, both platforms' install/verify commands, `--no-deps` editable install, the reviewed lock-regeneration flow, CLI usage, and the exit-code table — satisfying sprint §8 step 5 (preserve and supplement, not regress). No scientific processing or training capability is claimed anywhere (README L7 status note; sprint §6 L89 「尚未声称任何科学处理或训练结果」 — verified true). The lock files' generic `YOURENV` headers were left untouched, per review-confirm #9.

### 5.5 Environment contract (summary of §3)

Every shared direct dependency matches across design §11, `environment.yml`, `osx.yml`, and `win.yml`; platforms, channels, source metadata, and pip-managed mplhep are consistent; the locks were preserved rather than regenerated (their recorded content hashes prove they predate the committed `environment.yml`). The single divergence — the omitted `conda-lock` — breaks the content-hash binding between the declared direct dependencies and the frozen locks, and is the one item that must be fixed before the environment contract is relied upon further.

---

## 6. Requirement Compliance Matrix (sprint-m1-01)

| Requirement (sprint-m1-01) | Status | Evidence / finding |
|---|---|---|
| §5.1 L54 complete directory skeleton + `.gitkeep` (design §5) | Done | File tree: all design §5 directories present; `.gitkeep` in `config/`, `data/`, `runs/`, `tests/fixtures/`, `tests/golden/`; module files deferred (Info, §4 row 15) |
| §5.1 L55 package metadata, source install, exactly two console entry points | Done | `pyproject.toml` L25–27; `test_exact_console_entry_points` asserts exact design §6 specs; installed scripts verified |
| §5.1 L55 `environment.yml` from design §11 baseline; cross-check `osx.yml`/`win.yml` direct deps, platforms, source metadata; no hand-editing of locks | **Partial — High** | Versions/platforms/sources verified matching; locks preserved (content hash proves pre-existing locks kept, un-hand-edited); but `conda-lock` omitted from baseline → content-hash mismatch (§3, H1) |
| §5.1 L57 static/runtime guard: no `xgboost/src` import | Done (static) | AST guard + test pass (Info, §4 row 16, on dynamic-import scope) |
| §5.1 L58 `neural/AGENTS.md` inheriting root rules, MC-only, forbidden fields, frozen runs, fail-closed, evidence boundary, educational wording | Done | §5.4; all required content present |
| §5.1 test: package importable + entry-point set matches design exactly | Done | Tests pass; import verified via pytest and installed scripts |
| §5.1 test: dependency guard rejects `xgboost/src` | Done | `test_runtime_source_does_not_import_xgboost` |
| §5.2 L69 parser, `--help`, stable exit codes for both CLIs | Mostly done | 0/2 observable and verified; 3/4/5/70 defined but unwired (Info); usage-path test missing (Medium) |
| §5.2 L74 fixed exit-code table 0/2/3/4/5/70 | Done | Identical in `config.py`, `neural/AGENTS.md`, `README.md` §3 |
| §5.2 L75 run dir creation, temp write, atomic publish, failure-receipt foundation | Done | `RunTransaction`; unit tests + manual verification (§2) |
| §5.2 L76 reject existing dirs, outside-root paths, incomplete publication | Done | Existing/outside/equal-to-root rejected; incomplete publication impossible by single-rename design; edge cases Low (TOCTOU, nested target) |
| §5.2 test: CLI help smoke | Done | `test_cli_help` (both programs, rc 0) |
| §5.2 test: non-overwrite, path escape, success publish, failure receipt | Done | 4 unit tests; guard paths untested (Low) |
| §6 acceptance: locked env installable, `pip check` passes | Verified (win-64) | §2; ARM64 authority not claimed, per `neural/AGENTS.md` |
| §6 acceptance: two and only two CLIs' `--help` succeed | Verified | §2 |
| §6 acceptance: tests prove no `xgboost/src` runtime dependency | Verified | §2 |
| §6 acceptance: transaction never overwrites; error paths fail closed | Verified | §2, §5.1 (residual race noted Low) |
| §6 acceptance: no scientific processing or training results claimed | Verified | README L7; CLI stubs; docs wording |
| Review-confirm #5/#17: `environment.yml` describes the same direct-dependency set as the locks | **Not met** | H1 (§3) |
| Review-confirm #13: exit-code definitions + test usage/transaction paths | Partial | Definitions done; usage-path test missing (Medium) |

---

## 7. Review Verdict and Required Actions

**Verdict: conditionally approvable.** The M1-01 implementation meets all of the sprint's own acceptance criteria on the declared development platform, respects every scientific-safety constraint, preserves `xgboost/` and the frozen locks untouched, and provides a correct, tested foundation (non-overwrite transaction, exit-code contract, package isolation) for M1-02+. The one High environment-contract inconsistency must be resolved before the environment contract is relied upon or any lock regeneration occurs.

Required actions, in order:

1. **Fix H1 (one line, verified):** add `- conda-lock` (unpinned) to `neural/environment.yml`, restoring exact `content_hash` equality with both frozen locks; alternatively regenerate both locks through the README §1.5 review flow and re-baseline explicitly. Add a contract test so the direct-dependency set can never silently drift from the locks again.
2. **Close the Medium test gap:** add the usage-error exit-code test (rc 2) for both CLIs, and wire/cover codes 3/4/5/70 as application services arrive in M1-02+.
3. **Close the Medium hygiene gap:** add ignore rules for `neural/runs/` and `neural/data/` contents before the first real run is produced.
4. **Before M1-02 extends `RunTransaction`:** address the Low transaction findings (replace-race error typing, nested-target validation, failure-path exception masking/orphan cleanup) and add the missing guard-path unit tests, so the sprint §9 non-overwrite/failure-receipt semantics stay pinned as the API grows.
5. **Track the deferred items explicitly:** unified logging (sprint §5.2 goal), dependency-pin duplication test, bare-invocation stub semantics — small follow-ups to fold into M1-02.

No implementation, test, documentation, or lock file was modified during this review; verification commands were executed read-only against the existing environment, and this report is the only file written.

---

*End of review report.*
