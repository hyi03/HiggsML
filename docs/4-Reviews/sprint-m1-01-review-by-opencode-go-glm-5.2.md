# Sprint M1-01 / FR-001 Document Review Report

- **Reviewer:** opencode-go / glm-5.2
- **Review date:** 2026-09-01
- **Review type:** Document review (target documents and source code were not modified)
- **Target documents (reviewed as one Sprint document target):**
  - `neural/docs/FR-001-adversarial-mlp-refactor.md`
  - `neural/docs/sprint-m1-01.md`
- **Sources of truth:**
  - `AGENTS.md` (repository root)
  - `neural_adversarial_mlp_refactor_design.md` (repository root — the **currently modified working-tree version**, per the review task; see §2.1)
- **Reference documents inspected where relevant:**
  - `neural/README.md`
  - `neural/osx.yml`, `neural/win.yml`
  - `neural/docs/sprint-m1-02.md` … `neural/docs/sprint-m1-06.md` (impact check only, not review targets)

---

## 1. Executive Summary

`FR-001` and `sprint-m1-01` correctly capture the scientific intent of the approved adversarial-MLP refactor design: strict MC-only data boundary, ROOT SHA-256 input binding, forbidden classifier features (`m4l`, identifiers, provenance, weights), fixed 15-feature input, preregistered λ candidates and qualification thresholds, explicit one-time `open-test`, fail-closed behavior, immutable/non-overridable run directories, and the educational (non-ATLAS) framing required by root `AGENTS.md`. No Critical scientific-safety violations were found.

However, the review identified **three High-severity findings, all in the environment-name and lock-file contract**, that block sprint sign-off: the documents fix the Conda environment as `higgsml-neural` and the lock file as `conda-lock.yml`, while the **currently modified approved design** fixes the environment name as `pytorch` with two platform locks `osx.yml` (osx-arm64 authority) and `win.yml` (win-64 development/test). The repository already contains `neural/osx.yml` and `neural/win.yml`, both matching the design's version baseline exactly, and `neural/README.md` already documents the correct contract. The wrong contract originates in `FR-001` (its "最小验证方式") and propagates into `sprint-m1-01` and, unchecked, into all six sprint documents (`sprint-m1-02` … `sprint-m1-06`).

Additional Medium findings concern the missing win-64 lock deliverable (which makes the Sprint's own verification commands non-executable on the declared development platform), a README-regression risk in the Sprint's step 5, the untracked provenance of the existing locks (`metadata.sources: [environment.yml]` with no `environment.yml` in the repository), a requirements-traceability gap in `FR-001` R1 (the root cause of the naming drift), and missing normative traceability to root `AGENTS.md`.

**Verdict: not approvable for implementation as written.** The scientific content is sound; the environment/lock contract must be re-baselined against the modified design in `FR-001` first, then cascaded to all six sprint documents.

**Findings count:** 0 Critical · 3 High · 4 Medium · 3 Low · 3 Info.

---

## 2. Environment-Name and Lock-File Contract Check

This section performs the check explicitly requested by the review task: the environment-name and lock-file contract of the target documents against the **currently modified** approved design.

### 2.1 What "currently modified" means (evidence)

`git diff -- neural_adversarial_mlp_refactor_design.md` shows the working-tree design has an **uncommitted, deliberate change of the environment contract** relative to the last commit:

| Contract element | Old design (committed, `2ae1cbc`/`92a68a3`) | Currently modified design (source of truth) |
|---|---|---|
| Conda environment name | `higgsml-v2` | `pytorch` |
| Lock files | single `conda-lock.yml` | `osx.yml` (osx-arm64 authority) + `win.yml` (win-64 dev/test) |
| Target platforms | `osx-arm64` only | `osx-arm64` authority + `win-64` development/test |
| Package layout | `src/higgsml_v2/`, entry points `higgsml_v2.cli.*:main` | `src/`, entry points `src.cli.preprocess:main`, `src.cli.train:main` |

Design §11 (L413) now states: 「独立环境名称固定为 `pytorch`。`environment.yml` 声明跨平台直接依赖，`osx.yml` 锁定权威 `osx-arm64` 环境，`win.yml` 锁定 `win-64` 开发与测试环境。」 with install/verify commands `conda-lock install --name pytorch osx.yml` (L435) and a Windows PowerShell block using `conda-lock install --name pytorch win.yml` (L443).

The target documents were **not re-baselined against this modification**: they adopt the *new* `src/` layout (FR-001 L9 `neural/src/`; Sprint L30 `neural/src/cli/`, `neural/src/config.py`, `neural/src/artifacts/transaction.py`) but the *old* lock filename `conda-lock.yml`, and an environment name `higgsml-neural` that matches **neither** the old (`higgsml-v2`) **nor** the new (`pytorch`) design.

### 2.2 Contract comparison

| Contract element | Modified design (§5 L88–90, §6 L139–145, §11 L413–446) | `neural/README.md` | Repository state | `FR-001` | `sprint-m1-01` | Assessment |
|---|---|---|---|---|---|---|
| Conda env name | `pytorch` (fixed) | `pytorch` (§1.1 L13) | n/a (name assigned at install) | `higgsml-neural` (L133–135) | `higgsml-neural` (L49; §7 L92–99) | **Mismatch** |
| Authority lock | `osx.yml` (osx-arm64) | `osx.yml` (L18) | `neural/osx.yml` exists; all direct-dependency versions equal design §11 baseline | `conda-lock.yml` (L133) — no such file | `conda-lock.yml` (L29, L55, L92) | **Mismatch** |
| Dev/test lock | `win.yml` (win-64) | `win.yml` (L19) | `neural/win.yml` exists; same direct-dependency versions as `osx.yml` | not mentioned | not mentioned; §5.1 delivers only an `osx-arm64` lock | **Omission** |
| Direct-dep spec | `environment.yml` | `environment.yml` (§1.5 L85–101) | absent from repo; both locks declare `metadata.sources: [environment.yml]` | not mentioned | deliverable (L55) | Partial |
| Install/verify commands | `conda-lock install --name pytorch osx.yml` / `win.yml`; `conda run -n pytorch …` (L435–437, L443–445) | same (L38–44, L66–80) | n/a | `conda-lock install --name higgsml-neural conda-lock.yml`; `conda run -n higgsml-neural …` (L133–135) | identical to FR (L92–99) | **Mismatch** |
| Package layout / entry points | `src/` with `src.cli.preprocess:main`, `src.cli.train:main` | n/a | n/a | `neural/src/` (L9) | `neural/src/cli/`, `neural/src/config.py`, `neural/src/artifacts/transaction.py` (L30) | Aligned |

### 2.3 Lock-content verification against the design baseline

Both existing lock files were inspected and **match design §11's verified baseline exactly** (design L415–430):

| Package | Design §11 baseline | `neural/osx.yml` | `neural/win.yml` |
|---|---|---|---|
| Python | 3.12.13 | 3.12.13 | 3.12.13 |
| NumPy | 2.5.1 | 2.5.1 | 2.5.1 |
| pandas | 3.0.5 | 3.0.5 | 3.0.5 |
| PyYAML | 6.0.3 | 6.0.3 | 6.0.3 |
| uproot | 5.7.5 | 5.7.5 | 5.7.5 |
| scikit-learn | 1.9.0 | 1.9.0 | 1.9.0 |
| matplotlib | 3.11.1 | 3.11.1 | 3.11.1 |
| mplhep | 1.3.2 | 1.3.2 (pip-managed) | 1.3.2 (pip-managed) |
| awkward | 2.12.0 | 2.12.0 | 2.12.0 |
| vector | 1.8.1 | 1.8.1 | 1.8.1 |
| tqdm | 4.70.0 | 4.70.0 | 4.70.0 |
| PyTorch | 2.7.1 CPU | 2.7.1 `cpu_generic` | 2.7.1 `cpu_mkl` |
| pytest | unpinned | 9.1.1 | 9.1.1 |

(Each lock additionally pins three pip-managed packages: `mplhep`, `mplhep-data`, `uhi`.)

**Conclusion of the contract check:** the existing `osx.yml`/`win.yml` pair is a faithful, already-verified implementation of the modified design's environment contract. `FR-001` and `sprint-m1-01` reference a lock file that does not exist and an environment name that contradicts the design; if implemented as written, M1-01 would create a *second, divergent* environment contract, orphan the verified locks, and (via Sprint §8 step 5) rewrite the currently correct `neural/README.md`.

---

## 3. Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Consistency / Reproducibility | `FR-001` 最小验证方式 (L133–135); `sprint-m1-01` §5.1 (L49), §7 (L92–99) | Conda environment name `higgsml-neural` contradicts the fixed name in the currently modified approved design. It matches neither the old design (`higgsml-v2`) nor the modified design (`pytorch`), and diverges from the already-correct `neural/README.md`. | Design §11 L413 「独立环境名称固定为 `pytorch`」 (git diff: `higgsml-v2` → `pytorch`); `neural/README.md` §1.1 L13 「Conda 环境名称：`pytorch`」; `FR-001` L133 `conda-lock install --name higgsml-neural conda-lock.yml`; Sprint L49 「固定 `higgsml-neural` 环境」; every §7 command uses `-n higgsml-neural` | Replace every `higgsml-neural` occurrence with `pytorch` in `FR-001` and all six sprint documents; add the fixed environment name to `FR-001` R1 so sprints inherit it normatively instead of re-inventing it. |
| High | Consistency / Verification | `FR-001` L133; `sprint-m1-01` §3 (L29), §5.1 (L55), §7 (L92) | Lock file named `conda-lock.yml` does not exist in the repository and is not the modified design's contract. The design specifies `osx.yml` (osx-arm64 authority) + `win.yml` (win-64 dev/test), and the repository already contains verified `neural/osx.yml` and `neural/win.yml` whose direct-dependency versions match design §11 exactly (see §2.3). Every install/verify command in both documents is therefore non-executable as written. | Design §5 tree L89–90 (`osx.yml`, `win.yml`) and §11 L413, L435, L443; repo contains `neural/osx.yml` (content_hash `b1362e…`, platform `osx-arm64`) and `neural/win.yml` (platform `win-64`); `FR-001` L133 and Sprint L29/L55/L92 reference `conda-lock.yml` | Replace all `conda-lock.yml` references with the design's two-lock contract; change the Sprint §5.1 deliverable to 「创建 `environment.yml`，并按设计重新生成/校验 `osx.yml` 与 `win.yml`」; update §7 to the design §11 commands for both platforms. |
| High | Completeness / Executability | `sprint-m1-01` §3 (L29), §5.1 (L55), §7, §9 (L111) | The Sprint omits the win-64 lock (`win.yml`) that the modified design added for the development/test platform. The Sprint delivers only an `osx-arm64` lock, but development and testing are declared to happen on win-64 (`neural/README.md` §1.1; this review was itself performed on a win-64 host). `conda-lock install` resolves the *current* platform's solution from the lock; an osx-arm64-only lock has no win-64 solution, so the Sprint's own verification commands cannot run where the Sprint will be implemented. | Design §11 L440–446 (Windows PowerShell block: `conda-lock install --name pytorch win.yml`, `conda run -n pytorch python -m pip check`, `conda run -n pytorch python -m pytest -q`); Sprint §5.1 L55 「创建 `environment.yml` 与 `osx-arm64` `conda-lock.yml`」 (win-64 lock absent from §3 and §7); §9 L111 treats non-osx-arm64 hosts as lock-generation/review only, which predates the two-lock design | Add `neural/win.yml` to §3 and §5.1 deliverables; add the design §11 win-64 install/verify commands to §7; reword §9 to state that win-64 runs are sanctioned development verification (without claiming exact equivalence to the ARM64 authority run), consistent with design L448. |
| Medium | Change control / Regression risk | `sprint-m1-01` §8 step 5 (L107) | The Sprint instructs updating `neural/README.md`'s install and smoke commands to match the Sprint's own commands. The README currently documents the *correct* design contract (`pytorch`, `osx.yml`/`win.yml`, §1.5 regeneration flow); executing step 5 with the Sprint's current §7 commands would regress the README away from the approved design. | Sprint L107 「更新 README 的安装与 smoke 命令」 vs. Sprint §7 (`higgsml-neural`, `conda-lock.yml`); README §1.1 L13–19, §1.3 L38/L44, §1.5 L85–101 | Re-scope step 5: update the README only to the design §11 contract (adding M1-01's smoke commands under env `pytorch`), and add an acceptance check that README, FR, Sprint, and design agree on the environment contract before the Sprint is closed. |
| Medium | Completeness / Audit trail | `sprint-m1-01` §5.1 (L55); `neural/osx.yml` L16/L23 and `neural/win.yml` metadata; `neural/README.md` L7 | The existing locks were generated from an `environment.yml` that is not present in the repository (both locks declare `metadata.sources: [environment.yml]`). The Sprint plans to create `environment.yml` and a *new* lock without stating how the existing `osx.yml`/`win.yml` and their `content_hash` are reconciled — risking an orphaned authority lock or a silent change of locked versions. | `osx.yml` L16 `content_hash: osx-arm64: b1362e69…`, L23 `sources: [environment.yml]`; no `environment.yml` anywhere in the repo (glob verified); README L7 「`osx.yml` 与 `win.yml` 已生成；阶段 1 仍需交付用于重新生成锁文件的 `environment.yml`」; README §1.5 requires reviewed regeneration and verification in a fresh environment | Add an explicit M1-01 task: author `environment.yml` from design §11's baseline; regenerate both platform locks; verify the resulting direct-dependency versions equal the design baseline and that both locks install and pass `pip check`/pytest in fresh environments; treat the regenerated locks as reviewed replacements for the current files, never ad-hoc edits. |
| Medium | Requirements traceability (root cause) | `FR-001` R1 (L39), 影响范围 (L29) | `FR-001` encodes only the `osx-arm64` environment and never states the full two-lock/two-platform contract (fixed env name `pytorch`; `osx.yml` authority; `win.yml` dev/test) from the modified design. Because the FR is the declared requirement source for sprints m1-01…m1-06 (L152), sprints cannot inherit the correct contract from it — the direct cause of the three High findings. | FR L39 「工程必须可通过锁定的 `osx-arm64` Conda 环境安装和运行」; design §11 two-platform contract; all six sprint docs use `higgsml-neural`/`conda-lock.yml` (verified by search across `neural/docs/`) | Update `FR-001` R1, 影响范围, and 最小验证方式 to carry the complete environment contract: fixed name `pytorch`, `environment.yml` + `osx.yml` + `win.yml`, the role of each platform, and the design §11 commands. Then re-derive the affected sections of all six sprint documents. |
| Medium | Scientific safety / Traceability | `FR-001` preamble & 高层要求 (L91–98); `sprint-m1-01` §1, §3 (L31) | Neither document normatively cites the repository-wide scientific-safety constraints of root `AGENTS.md` (no real-data training; no `m4l`/identifier/provenance/weight features; frozen-run immutability; no relaxation of preregistered criteria; educational framing). The Sprint lists `neural/AGENTS.md` as a deliverable without specifying that it must encode these constraints. | Root `AGENTS.md` L5–6 「These instructions apply to the entire repository」 and §Scientific Safety L41–54; `FR-001` states MC-only/educational intent (L19, L123–129) but never cites `AGENTS.md`; Sprint L31 includes `neural/AGENTS.md` with no content requirements | Add a normative reference to root `AGENTS.md` in `FR-001`'s 高层要求; specify in Sprint §5.1 that `neural/AGENTS.md` must restate the design §3.3 safety constraints plus the root `AGENTS.md` rules (MC-only, forbidden features, immutable runs, fail-closed, educational framing) so they bind all subsequent sprints. |
| Low | Scope clarity | `sprint-m1-01` §3 (L29–31) vs §5.1 (L53) | §3's directory list is a subset (`src/cli/`, `src/config.py`, `src/artifacts/transaction.py`) while §5.1 requires 「创建设计规定的目录骨架与 `.gitkeep`」 — the full design §5 tree including `src/domain/`, `src/preprocessing/`, `src/training/`, `config/`, `tests/` subfolders, `data/`, `runs/`. Whether M1-01 creates the complete skeleton is ambiguous. | Sprint L53 「创建设计规定的目录骨架与 `.gitkeep`」; design §5 L83–133 full tree; Sprint §3 lists only part of the paths | State explicitly whether M1-01 creates the complete design §5 skeleton (with `.gitkeep` placeholders) or enumerate exactly which directories are deferred to which sprint, so later sprints do not re-litigate the layout. |
| Low | Missing specification | `sprint-m1-01` §5.2 (L71), §6 (L80–86); design §13 阶段 1 (L494–500) | The Sprint requires 「统一日志、异常退出码」 and 「稳定退出码」, but no exit-code contract (values and semantics) is defined anywhere in the Sprint or the design. Later sprints, CI, and the fail-closed philosophy depend on these values — including whether normal terminal states such as `no_eligible_candidate` (FR R4, L66) exit as success or a dedicated code. | Sprint L71 「实现两个 CLI 的 parser、`--help` 和稳定退出码」; design L497 mentions 「日志、异常退出码」 without enumerating codes; FR L66 defines `no_eligible_candidate` as a normal terminal state with no exit-code mapping | Define the exit-code table in M1-01 (e.g., in `neural/AGENTS.md` or a short spec: 0 success; distinct codes for usage errors, input binding/hash failure, transaction failure, unexpected errors; and the mapping for declared normal terminal states), and cover it in the CLI smoke tests. |
| Low | Scope precision | `sprint-m1-01` §3 (L25) | 「R1、R6 的基础部分」 is not enumerated. R6 spans run-directory immutability, allowed-root containment, config snapshot/metrics/predictions/plots/manifest publication, SHA-256, gzip canonical-content hashing, and failure receipts; §5.2 covers only the transaction basics, leaving the deferred boundary to the reader's inference. | Sprint L25 「FR-001 …：R1、R6 的基础部分」; §5.2 L63–78 (directory creation, atomic publish, failure receipt, path-escape rejection); FR R6 L76–82 | Enumerate the R6 sub-requirements in scope for M1-01 (non-overwrite, allowed-root containment, atomic publish, failure receipts) and name the deferred ones (manifest schema, SHA-256, gzip canonical hash, full artifact set) together with their target sprint. |
| Info | Packaging risk | design §6 (L142–145); `sprint-m1-01` §5.1 (L54, L60) | The modified design's entry points import from a top-level package literally named `src` (`src.cli.preprocess:main`), which is unconventional and collision-prone. `FR-001` (L40) names only the two programs; the Sprint defers module paths to the design (L60 「精确匹配设计」), so the M1-01 packaging task will have to configure setuptools for a package named `src`. | Design L143–144; FR L40; Sprint L54, L60 | Have the M1-01 entry-point test assert the exact specs from design §6 (both names and module paths); if packaging a top-level `src` package causes discovery or collision problems, raise it with the design owner for a design-level decision rather than silently deviating in `pyproject.toml`. |
| Info | Positive | `FR-001` throughout; `sprint-m1-01` §1–§4, §6 (L85–86) | Scientific-safety and scope intent is correctly inherited and, where stated, matches the design and root `AGENTS.md`: MC-only boundary with SHA-256-bound ROOT inputs (FR L46, L102–103), forbidden features fail-closed (L55, L144), preregistered λ set and thresholds with no post-hoc relaxation (L62–65, L129), `open-test` not authorized by document existence (L153), immutable runs (L78, L98), and the Sprint's explicit 「尚未声称任何科学处理或训练结果」 (L86). | FR R2–R7, 不纳入范围 L123–129, 失败与降级 L115–121, 备注 L152–154; Sprint §4 L33–41, §6; design §3.2–3.3; root `AGENTS.md` §Scientific Safety | Preserve these constraints verbatim when applying the environment-contract corrections; do not couple the naming fix to any change of scientific rules. |
| Info | Positive / Verified | `neural/osx.yml`, `neural/win.yml` vs design §11 (L415–430) | Both existing lock files already match the design §11 version baseline exactly (Python 3.12.13, NumPy 2.5.1, pandas 3.0.5, PyYAML 6.0.3, uproot 5.7.5, scikit-learn 1.9.0, matplotlib 3.11.1, mplhep 1.3.2, awkward 2.12.0, vector 1.8.1, tqdm 4.70.0, PyTorch 2.7.1 CPU; see §2.3), and `neural/README.md` already documents the correct two-lock `pytorch` contract including the reviewed regeneration flow (§1.5). | Lock inspection performed during this review (§2.3); README §1.1–§1.5 | Treat the existing locks as the authority baseline: M1-01's `environment.yml` should reproduce them (same direct dependencies, ideally the same `content_hash`) rather than re-solving to newer versions; only regenerate through the README §1.5 review flow. |

---

## 4. Detailed Observations

### 4.1 Correctness checks that passed (FR-001 vs design)

The following quantitative and rule-level claims in `FR-001` were cross-checked against the design and are **consistent**:

- MC baseline counts: Higgs 187,128 / ZZ 11,976 / total 199,104 / development 159,395 / test 39,709 (FR L25 ↔ design §2 table).
- ROOT input SHA-256 values for DSID 345060 and 363490 (FR L102–103 ↔ design §7.1).
- 19 model-candidate features + non-model fields incl. `m4l`, `split`, signed `physical_weight`, normalized `train_weight`, canonical identity (FR L49–50 ↔ design §7.3).
- Fixed 15-feature classifier input (DropTop4 + Angular5), forbidden `lep3_pt`/`lep4_pt`/`mZ1`/`mZ2` (FR L54 ↔ design §7.3).
- Adversary: background-only classifier logit input, 11 fixed `m4l` bins, GRL (FR L57 ↔ design §8.3–8.4).
- Preregistered λ set `{0.00, 0.05, 0.10, 0.20, 0.50}`; AUC ≥ 0.80; KS ≤ 0.10 at three working points; signal efficiency strictly above ZZ efficiency; tie-break ≤ 1e-6 → smaller λ; `no_eligible_candidate` terminal state; final model on full development with epoch = median of five fold best epochs, no re-early-stopping, no test reads (FR L62–67 ↔ design §9).
- One-time `open-test` subcommand with atomic claim, receipts, frozen model/thresholds, `test_reproduced`/`test_nonreproduction` only (FR L69–74 ↔ design §6.3, §10.2).
- Gzip canonical CSV content hash in addition to file hash (FR L80 ↔ design §7.4).
- Test-design coverage requirements (FR R7 ↔ design §12).

### 4.2 Sprint ↔ design stage-1 alignment

`sprint-m1-01` correctly maps to design §13 阶段 1 (L494–500): package skeleton, locked environment, two stub CLIs, logging/exit codes, non-overridable run transactions, import guard against `xgboost/src`, and `--help` acceptance. The Sprint's TDD ordering (§8: tests first) and its "no science claims" acceptance line (L86) are appropriate. The only structural misalignment is the environment/lock contract (findings 1–3) and the deferred-boundary precision items (Low findings).

### 4.3 Propagation impact (why the FR must be fixed first)

Search across `neural/docs/` confirms the `higgsml-neural` + `conda-lock.yml` contract appears not only in the two target documents but in **all six sprint documents** (e.g., `sprint-m1-06` L「`conda-lock install --name higgsml-neural conda-lock.yml`」 and full-pipeline CLI commands; `sprint-m1-02`…`m1-05` pytest/CLI commands). Since `FR-001` 备注 (L152) declares the splits and their order, the correction must be made once in `FR-001` (R1, 影响范围, 最小验证方式) and then cascaded mechanically to `sprint-m1-01`…`sprint-m1-06`. Fixing only `sprint-m1-01` would leave the series internally inconsistent.

### 4.4 Scientific safety and scope (AGENTS.md compliance)

No violations of root `AGENTS.md` §Scientific Safety were found: the documents exclude real data entirely (FR L125), keep `m4l`/identifiers/provenance/weights out of the classifier (FR L55, L144), treat frozen runs and `xgboost/` as immutable (FR L33, L98, L148), require explicit separate authorization for `open-test` (FR L71, L153; AGENTS.md L51–52), and preserve the educational/technical-demo framing (FR L19; AGENTS.md L53–54). The gap is traceability, not content (Medium finding 7).

---

## 5. Review Verdict and Required Actions

**Verdict:** `FR-001` + `sprint-m1-01` are scientifically sound and correctly scoped for a skeleton sprint, but **not approvable for implementation as written** due to the environment/lock contract contradictions against the currently modified approved design.

Required actions before implementation, in order:

1. **Fix `FR-001` first** (root cause): R1, 影响范围, and 最小验证方式 must carry the design §11 contract — env name `pytorch`, `environment.yml` + `osx.yml` + `win.yml`, both platforms' install/verify commands.
2. **Cascade to all six sprint documents** (`sprint-m1-01`…`sprint-m1-06`): replace `higgsml-neural` → `pytorch`, `conda-lock.yml` → `osx.yml`/`win.yml`; add the win-64 lock deliverable and verification path to `sprint-m1-01` §3/§5.1/§7; reword §9.
3. **Re-scope Sprint §8 step 5** so the README update preserves (rather than regresses) the correct two-lock `pytorch` contract.
4. **Add the lock-provenance task**: deliver `environment.yml`, regenerate both locks through the README §1.5 review flow, and verify the locked versions still equal the design §11 baseline.
5. **Add traceability**: normative `AGENTS.md` reference in `FR-001`; content requirements for `neural/AGENTS.md` in the Sprint; an exit-code table; explicit R6 sub-requirement enumeration.

No modifications were made to the target documents, the design, or any source code; this review report is the only file written.

---

*End of review report.*
