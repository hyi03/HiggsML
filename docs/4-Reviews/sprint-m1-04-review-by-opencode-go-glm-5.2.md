# Sprint M1-04 Document Review

| Field | Value |
|---|---|
| **Review target** | `neural/docs/sprint-m1-04.md`, `neural/docs/development-protocol-v1.md` |
| **Review type** | Document review (pre-implementation) |
| **Reviewer** | opencode-go / glm-5.2 |
| **Date** | 2026-09-02 |
| **Authority sources** | `AGENTS.md`, `neural/AGENTS.md`, `neural/docs/FR-001-adversarial-mlp-refactor.md`, `neural_adversarial_mlp_refactor_design.md`, current `neural/` implementation |
| **Sprint status** | Pre-implementation — all task checkboxes unchecked, all listed source files absent |

---

## 1. Executive Summary

The Sprint M1-04 document and its self-contained Development Protocol V1 are
**scientifically sound, internally consistent, and faithful to FR-001 R4/R6/R7**
and the confirmed refactor design. The qualification rules, tie-break logic,
OOF contract, held-out test isolation strategy, and artifact schema all match
the authoritative sources without relaxation.

No **Critical** defects were found. The review identified two **High** findings
both related to scientific-data-safety enforcement gaps that the documents
describe intentually but do not fully pin down, and several **Medium/Low**
clarity and consistency issues that are actionable before implementation begins.

All missing source files (`folds.py`, `qualification.py`, `development.py`,
`plots.py`), missing protocol YAML blocks (`folding`, `working_points`,
`qualification`, `final_fit`, `development_artifacts`), missing CLI
`develop` subcommand, and missing tests (`test_folds.py`,
`test_qualification.py`, `test_development_run.py`) are **expected
pre-implementation gaps**, not defects — the Sprint explicitly tasks M1-04
with creating them.

---

## 2. Scope and Methodology

### 2.1 Documents reviewed as the M1-04 target

| File | Lines | Role |
|---|---:|---|
| `neural/docs/sprint-m1-04.md` | 154 | Sprint definition: goals, scope, work packages, acceptance, verification |
| `neural/docs/development-protocol-v1.md` | 175 | Self-contained implementation protocol: input binding, folds, OOF, metrics, qualification, final fit, artifacts, tests |

### 2.2 Verification sources consulted

| Source | Purpose |
|---|---|
| `AGENTS.md` (root) | Repository-wide scientific safety, change discipline |
| `neural/AGENTS.md` | Neural project scope, MC-only, exit codes, verification |
| `neural/docs/FR-001-adversarial-mlp-refactor.md` | FR-001 R1–R7 requirements, acceptance criteria |
| `neural_adversarial_mlp_refactor_design.md` | Confirmed design: §7 data contract, §8 MLP, §9 OOF/qualification, §10 artifacts, §12 tests |
| `neural/docs/sprint-m1-03.md` | Dependency verification — M1-03 completion status |
| `neural/docs/sprint-m1-05.md` | Boundary verification — test-opening scope |
| `neural/config/adversarial_mlp_protocol_v1.yaml` | Current sealed protocol YAML (128 lines, no M1-04 blocks) |
| `neural/src/training/config.py` | Protocol loader with `_EXPECTED` strict-equality dict |
| `neural/src/training/trainer.py` | M1-03 single-fold primitive (`train_fold`) |
| `neural/src/training/dataset.py` | `validate_development_frame`, `build_validated_fold` |
| `neural/src/training/network.py` | Classifier/Adversary/GRL (9 228 params) |
| `neural/src/training/losses.py` | BCE, adversarial CE, mass bins, bin weights |
| `neural/src/artifacts/manifest.py` | `sha256_file`, `json_bytes`, `peak_memory_bytes` |
| `neural/src/artifacts/transaction.py` | `RunTransaction` (allowed-root, non-overwrite) |
| `neural/src/cli/train.py` | Current CLI (bare parser, no subcommands) |
| `neural/src/domain/splitting.py` | Preprocess split (blake2b, mod 10) |
| `neural/tests/` | Existing M1-03 test suite |

### 2.3 Review constraints

- **MC-only enforcement**: verified that neither document authorizes reading,
  hashing, preprocessing, scoring, or plotting real data.
- **Held-out test isolation**: verified that neither document authorizes
  decoding, materializing, or using held-out test feature values in any
  development decision path.
- **Pre-implementation distinction**: missing code is a defect only if the
  Sprint claims it already exists or does not task M1-04 with creating it.

---

## 3. Claim Verification Summary

### 3.1 Dependency claims — verified

| Sprint M1-04 claim | Verification | Status |
|---|---|---|
| M1-03 completed deterministic single-fold training primitive | `trainer.py:train_fold` exists (255 lines); M1-03 §10 records "130 passed, 1 skipped" | **Confirmed** |
| M1-02 preprocess manifest/schema frozen | M1-03 §2 confirms "M1-02 已完成并冻结预处理 schema"; `config.py` enforces 29-column `_OUTPUT_COLUMNS` | **Confirmed** |
| FR-001 R4, R6, R7 | Protocol V1 covers all R4 (folds, OOF, qualification), R6 (artifacts, hashes), R7 (tests) requirements | **Confirmed** |
| Development Protocol V1 is self-contained | Protocol covers input binding, folds, OOF, metrics, qualification, final fit, artifacts, tests — no external spec needed | **Confirmed** |

### 3.2 Scientific safety claims — verified

| Claim | Verification | Status |
|---|---|---|
| Held-out test not in any development decision | Protocol V1 §2 two-stage reader; §7 no-eligible prohibits test artifacts; Sprint §5.3 spy/fixture test | **Consistent** |
| Test feature tokens not decoded to numeric values | Protocol V1 §2: "held-out test feature token 不得被解码为数值、物化进 DataFrame/array/tensor" | **Consistent** |
| Physical isolation, not just metric-layer filtering | Sprint §9: "Development 数据加载层必须物理隔离 test 行读取" | **Consistent** |
| Working points only from development OOF background | Protocol V1 §6: "只在 OOF label=0 上确定 threshold" | **Consistent** |
| No relaxation of AUC/KS/efficiency thresholds | Protocol V1 §7: "门槛比较不使用 epsilon" | **Consistent** |
| MC-only, no real data | Both documents repeatedly affirm MC-only; no real-data path authorized | **Consistent** |
| Windows/synthetic not authoritative | Protocol V1 §1; Sprint §7: "Windows/synthetic 不替代 locked native osx-arm64 权威 gate" | **Consistent** |
| `m4l` not a classifier feature | Protocol YAML `forbidden_features` includes `m4l`; design §8.1: "不对 m4l 做分类器输入变换" | **Consistent** |
| 15 features only | Protocol YAML `features` lists exactly 15; `forbidden_features` lists 14 excluded columns | **Consistent** |

### 3.3 FR-001 R4 cross-reference — fully covered

Every FR-001 R4 requirement is addressed by Development Protocol V1 with
equal or greater precision. See §6.1 of this report for the item-by-item
mapping.

---

## 4. Findings

| # | Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|---|
| F1 | High | Security | `development-protocol-v1.md` §2 (lines 23–31) | Two-stage reader is described as the implementation approach but is not explicitly mandated as the **sole sanctioned entry point** for loading preprocess output into the development pipeline. If an implementer or test bypasses it (e.g., `pandas.read_csv` on the full gzip), test feature values would be materialized in memory before `validate_development_frame` (line 154) rejects the test rows — a violation of "Development may not read held-out test feature values" (`neural/AGENTS.md`). | Protocol says "实现使用两阶段 reader" (implementation uses two-stage reader) but does not say "no other code path may load preprocess output." Existing `validate_development_frame` (`dataset.py:154`) rejects test splits but only after the DataFrame is already materialized. | Add an explicit statement that the two-stage development reader is the only sanctioned code path for loading preprocess output into any development component, and that `ValidatedDevelopment` may only be constructed through it. Require a test that verifies no alternative path can produce a `ValidatedDevelopment` containing test-row feature values. |
| F2 | High | Consistency | `development-protocol-v1.md` §9 (lines 149–150) vs `neural/src/artifacts/manifest.py:29` | Protocol V1 specifies JSON artifacts use "compact separators、排序 key (sorted keys)" but the existing `json_bytes` helper uses `indent=2` and does not sort keys. If the existing helper is reused for `qualification.json` / `working_points.json`, the output will not match the Protocol's serialization spec, breaking hash reproducibility. The Protocol also does not clarify whether `manifest.json` itself uses the same compact format or the existing indented format. | `manifest.py:29`: `json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)` — no `sort_keys`, no compact separators. Protocol §9: "JSON 使用 UTF-8、排序 key、compact separators、终止换行，禁止 NaN/Infinity." | Either (a) add a separate `compact_json_bytes` helper for M1-04 JSON artifacts with `sort_keys=True, separators=(",", ":")`, or (b) update the Protocol to explicitly state which JSON files use compact format and which use indented format. Ensure the manifest's own format is specified. |
| F3 | Medium | Clarity | `sprint-m1-04.md` §3 (lines 39–40) vs `neural/src/training/config.py:47–89` | Sprint says to add and seal `folding`, `working_points`, `qualification`, `final_fit`, `development_artifacts` blocks in the YAML, but does not mention that `config.py:_EXPECTED` (the strict-equality dict) must also be extended with these blocks. Without updating `_EXPECTED`, `_strict_equal(raw, _EXPECTED)` at `config.py:152` will reject the updated YAML due to extra keys. | `config.py:152`: `if not _strict_equal(raw, _EXPECTED): raise InputBindingError("sealed adversarial MLP protocol changed")`. `_EXPECTED` (lines 47–89) does not contain the five new blocks. | Add an explicit implementation note in Sprint §3 or Protocol V1 §3 that `_EXPECTED` in `config.py` must be extended with the exact new block contents, and that the loader's strict-equality check will reject the YAML otherwise. |
| F4 | Medium | Clarity | `development-protocol-v1.md` §9 (lines 146–147) | `fold_metrics.csv` row schema is ambiguous. "每行是一个 `(target_lambda, fold_index, epoch)`，其余列 exact 使用 M1-03 epoch fields，并附 `fold_seed`、`best_epoch`、`best_validation_weighted_auc`" could mean (a) one row per epoch with fold-level summary fields repeated on every row, or (b) a separate summary section. The placement of `best_epoch` and `best_validation_weighted_auc` (fold-level summaries) on per-epoch rows is unusual. | Protocol §9 line 146: "每行是一个 `(target_lambda, fold_index, epoch)`" (per-epoch rows); line 147: "并附 `fold_seed`、`best_epoch`、`best_validation_weighted_auc`" (fold-level summaries appended). | Clarify whether summary fields are repeated on every epoch row or only on the best-epoch row. Specify the exact column order for `fold_metrics.csv` as done for `oof_scores.csv.gz` in §5. |
| F5 | Medium | Requirement | `development-protocol-v1.md` §2 (lines 17–18) vs `neural/src/artifacts/transaction.py:36–46` | Protocol requires input-run path validation including "无 symlink/reparse-point 穿越" (no symlink/reparse-point traversal). The existing `RunTransaction._validate_target` only checks output run directories (`commonpath`, existence); it does not validate input runs or check for symlinks/reparse points. The Protocol does not specify whether to extend `RunTransaction` or create a new input-binder component. | `transaction.py:36–46`: `_validate_target` checks `os.path.commonpath` and `run_dir.exists()` for the output directory only. Protocol §2 requires symlink/reparse-point checks on the **input** run. | Specify in Protocol V1 §2 whether the input-run validation is a new component (e.g., `InputBinder`) or an extension of `RunTransaction`. Add symlink/reparse-point detection logic (`Path.resolve()`, `os.path.islink()`) to the input binding validation path. |
| F6 | Medium | Consistency | `sprint-m1-04.md` §3 (line 33) vs `neural_adversarial_mlp_refactor_design.md` §5 (lines 112–119) | Sprint introduces `neural/src/training/development.py` as a new module, but the design doc's module structure (§5) lists `dataset.py`, `network.py`, `losses.py`, `folds.py`, `trainer.py`, `qualification.py`, `test_opening.py` — not `development.py`. | Sprint §3: "`neural/src/training/development.py` 与 development-only input reader". Design §5: no `development.py` in the tree. | Either (a) update the design doc's §5 structure to include `development.py`, or (b) add a note in the Sprint explaining that `development.py` is a new module introduced by M1-04 to orchestrate the development pipeline, and that the design doc's structure is indicative. |
| F7 | Medium | Clarity | `sprint-m1-04.md` §3 (line 31) | Sprint lists `trainer.py` among involved files but does not specify what changes (if any) are needed. The existing `trainer.py:train_fold` is the M1-03 single-fold primitive. Protocol V1 §8 describes a final fit (full-development, fixed-epoch, no-early-stop) that may require new trainer functionality. | Sprint §3: "`neural/src/training/folds.py`、`qualification.py`、`trainer.py`". Protocol §8: "以 seed 42 重新初始化...恰好训练 `final_epochs`；不创建 validation、AUC checkpoint 或 early stopping." | Clarify whether `trainer.py` will be modified (e.g., adding a `train_final` function) or is listed as a dependency only. If modified, specify the changes: final-fit function, full-development data loading, no-early-stop path, final scaler fitting. |
| F8 | Low | Clarity | `development-protocol-v1.md` §4 (line 52) | Hash payload spec says "base-10 source_entry ASCII without sign/leading zero". For `source_entry=0`, the representation is "0", which could be misread as violating the "no leading zero" rule. The spec is technically correct (zero is represented as the single digit "0") but could benefit from explicit clarification. | Protocol §4: "base-10 source_entry ASCII without sign/leading zero". No example for `source_entry=0`. | Add a known-vector test case for `source_entry=0` (payload = `source_sample || 0x00 || b"0"`) and clarify that "without leading zero" means no redundant leading zeros (e.g., "007" → "7"), not that the digit "0" itself is excluded. |
| F9 | Low | Documentation | `development-protocol-v1.md` §6 (lines 87–90) | Threshold determination algorithm (stable descending sort, cumulative `abs(physical_weight)`, first `>= target * total`, full-tie preservation) is precise but complex. A worked numeric example would aid implementer verification and hand-calculation test construction. | Protocol §6: "按 score 降序稳定排序，累加 `abs(physical_weight)`，取 cumulative 第一次 `>= target * total` 的 score". Protocol §10 requires "inclusive full-tie thresholds...手算" (hand calculation). | Add a small worked example with 5–6 background events, concrete scores and weights, showing threshold selection and achieved efficiency exceeding target due to ties. |
| F10 | Low | Clarity | `development-protocol-v1.md` §2 (line 21) | Protocol says input preprocess protocol/config is "以 hash 引用" (referenced by hash) but does not explicitly state that the hash algorithm is SHA-256. It is implied by context (SHA-256 is used throughout) but not stated. | Protocol §2: "输入 preprocess protocol/config 与本次 development manifest 以 hash 引用". Protocol §2 also: "每个已声明文件 SHA-256 完整" (SHA-256 for files). | Explicitly state that the protocol/config hash reference is SHA-256 of the file payload bytes, consistent with the file-level SHA-256 used elsewhere. |
| F11 | Low | Consistency | `development-protocol-v1.md` §8 (line 119) vs `neural_adversarial_mlp_refactor_design.md` §8.5 (lines 330–333) | Protocol V1 specifies seed 42 for the final fit. The design doc §8.5 specifies "Base random seed | 42" and "每个 fold 使用 `seed = 42 + fold_index`" but does not explicitly state the final fit seed. The Protocol's specification is a reasonable narrowing (final fit uses base seed, not a fold seed). | Protocol §8: "以 seed 42 重新初始化完整 9,228 参数模型和 AdamW". Design §8.5: no explicit final-fit seed. | Update the design doc §8.5 or §9.4 to explicitly state the final-fit seed (42) for consistency, or add a cross-reference note in the Protocol. |
| F12 | Low | Clarity | `development-protocol-v1.md` §5 (line 73) vs §6 (lines 83–84) | OOF CSV includes `physical_weight` (signed) but not `abs(physical_weight)` as a separate column. Efficiency and KS require `abs(physical_weight)`; AUC requires `train_weight`. The implementer must compute `abs(physical_weight)` from the signed column. While the Protocol §6 is clear about which weight to use, the OOF file does not include a pre-computed absolute-weight column. | Protocol §5 columns: `physical_weight, train_weight`. Protocol §6: "效率与 KS：使用 `abs(physical_weight)`"; "AUC：`sample_weight=train_weight`". | Consider adding a note that `abs(physical_weight)` for efficiency/KS is derived as `abs` of the `physical_weight` column in the OOF file, and that the implementer must not accidentally use `physical_weight` (signed) or `train_weight` (normalized) for efficiency/KS. |
| F13 | Low | Clarity | `development-protocol-v1.md` §2 (line 23) | "完整文件 bytes 可为完整性校验和 gzip 路由而顺序流过" (full file bytes can stream through for integrity check) could be misread as allowing full test-row decoding. The distinction between streaming bytes through a hash function and decoding tokens into numeric values is technically sound but could be clearer. | Protocol §2 line 23: "完整文件 bytes 可为完整性校验和 gzip 路由而顺序流过". Line 24: "held-out test feature token 不得被解码为数值". | Add an explicit clarifying sentence: "Computing the canonical CSV content SHA-256 by streaming decompressed bytes through a hash function does not constitute decoding test feature tokens into numeric values, provided no token is parsed, typed, or materialized." |
| F14 | Info | Documentation | `sprint-m1-04.md` §10 (line 154) | "交付结论" (delivery conclusion) is a placeholder: "待实施、评审确认和验证后填写". | Sprint §10: "待实施、评审确认和验证后填写". | Expected for a pre-implementation document. No action needed until Sprint completion. |
| F15 | Info | Consistency | `development-protocol-v1.md` §9 (lines 130–144) vs `neural_adversarial_mlp_refactor_design.md` §10.1 (lines 395–396) | Design doc includes `state/test_opening.json` in the development run directory; Protocol V1 §9 omits it. This is correct — M1-04 does not implement test-opening (M1-05 scope), and Protocol V1 §7 explicitly prohibits creating placeholder files interpretable as test-opening eligibility. | Protocol §9 artifact list: no `state/` directory. Design §10.1: `state/test_opening.json`. Protocol §7: "不得创建...test artifact 或可被 M1-05 解释为 test-opening 资格的占位文件". | No action needed — Protocol correctly scopes M1-04. The design doc's `state/test_opening.json` is for the complete system post-M1-05. |
| F16 | Info | Consistency | `sprint-m1-04.md` §3 (line 44) vs `neural/docs/FR-001-adversarial-mlp-refactor.md` R1 (line 45) | Sprint narrows `xgboost/src` use to "文档期行为核对" (documentation-period behavior checking). FR-001 R1 says "旧工程只可作为行为比对与只读数据来源" (behavior comparison and read-only data source). The Sprint's wording is narrower, which is allowed (`neural/AGENTS.md`: "may narrow their rules but never relax them"). | Sprint §3: "旧 `xgboost/src` 只用于文档期行为核对". FR-001 R1: "旧工程只可作为行为比对与只读数据来源". | Consistent narrowing. No action needed. |
| F17 | Info | Consistency | `development-protocol-v1.md` §3–4 (lines 38–55) vs `neural/src/domain/splitting.py:8`, `neural/src/config.py:134` | Fold assignment uses SHA-256 (mod 5); preprocess split uses blake2b (mod 10). Different hash functions and moduli for different purposes (5-fold CV assignment vs train/val/test splitting). No conflict. | Protocol §3: `algorithm=sha256_identity_v1`, modulo 5. `splitting.py:8`: `hashlib.blake2b(..., digest_size=8)`, modulo 10. | No action needed — different operations. Consider adding a one-line note in Protocol §3 that the fold-assignment hash is distinct from the preprocess split hash to prevent implementer confusion. |
| F18 | Info | Requirement | `sprint-m1-04.md` §2 (lines 14–16) | Sprint lists "FR-001 R4、R6、R7" as dependencies but does not reference `preprocess-protocol-v1.md` for the input binding contract details (manifest schema, 29-column schema, SHA-256 verification). | Sprint §2: references FR-001 R4/R6/R7 and Development Protocol V1. Protocol V1 §2 references "M1-02 成功发布且不可变的 preprocess run". | Add a reference to `preprocess-protocol-v1.md` in Sprint §2 for the input binding contract details (manifest schema, file SHA-256, canonical CSV content hash). Minor documentation improvement. |
| F19 | Info | Test | `development-protocol-v1.md` §10 (line 171) vs `neural/tests/unit/test_dataset.py:89–98` | Protocol requires poison tests covering 5 components: test feature decoder, validator, trainer, metric, and plot. The existing M1-03 test only covers the validator layer (`test_forbidden_test_split_is_refused_before_other_column_access`). M1-04 must extend poison coverage to all 5 components. | Protocol §10: "poison test row 证明 test feature decoder、validator、trainer、metric 与 plot 从未收到 test 值". `test_dataset.py:89`: tests validator only. | Pre-implementation. Ensure M1-04 poison tests cover all 5 components: (1) two-stage decoder, (2) `validate_development_frame`, (3) `train_fold`/final fit, (4) AUC/KS/efficiency metrics, (5) plot generation. |
| F20 | Info | Consistency | `development-protocol-v1.md` §7 (lines 105–107) vs `neural/docs/FR-001-adversarial-mlp-refactor.md` R4 (line 78) | Protocol V1's tie-break definition (compare all eligible candidates against max AUC, not pairwise) is a precise clarification of FR-001 R4's "若绝对差不超过 1e-6 时选择较小 lambda". The Protocol explicitly prevents transitivity issues in chained ties. This is a correct narrowing. | Protocol §7: "先取 eligible candidate 的最大 AUC `best_auc`；只在选择层使用 `abs(candidate_auc - best_auc) <= 1e-6`...这一定义避免相邻链式 tie 的非传递结果". FR-001 R4: "绝对差不超过 1e-6 时选择较小 lambda". | No action needed — Protocol correctly narrows the tie-break definition. |

---

## 5. Detailed Analysis of Key Findings

### 5.1 F1 — Two-stage reader sole entry point (High, Security)

**The concern.** `neural/AGENTS.md` states: "Development may not read held-out
test feature values." Protocol V1 §2 describes a two-stage reader that:
- Stage 1: only locates and decodes the header and each row's `split` token;
- Stage 2: only parses all 29 columns for `split=train|validation` rows;
- `split=test` rows are only counted and skipped;
- test feature tokens must not be decoded, materialized, or routed to any
  downstream component.

This is a strong and correct design. However, the Protocol says "实现使用两阶段
reader" (implementation uses two-stage reader) — this describes the approach but
does not explicitly mandate it as the **only** sanctioned code path. The existing
`validate_development_frame` (`dataset.py:148`) accepts a `pd.DataFrame` and
rejects rows where `split` is not `train` or `validation` (line 154). If an
implementer or test loads the preprocess CSV directly with `pandas.read_csv`,
all rows (including test) are materialized into a DataFrame before
`validate_development_frame` rejects the test rows. At that point, test feature
**values** have already been read into memory — a violation of the AGENTS.md
constraint, even though the values are subsequently rejected.

**Why it matters.** The existing M1-03 test
(`test_forbidden_test_split_is_refused_before_other_column_access`,
`test_dataset.py:89–98`) proves that the *validator* refuses test splits before
accessing other columns. But this test operates on an already-constructed
`pd.DataFrame` — it does not prove that the *reader* never materialized test
feature values into that DataFrame. The two-stage reader prevents
materialization; the validator only prevents downstream use. Both layers are
needed.

**Recommendation.** Add to Protocol V1 §2 an explicit statement that:
1. The two-stage development reader is the sole sanctioned code path for
   loading preprocess output into any development component.
2. `ValidatedDevelopment` objects may only be constructed through this reader.
3. A test must verify that no alternative loading path can produce a
   `ValidatedDevelopment` containing (or having read) test-row feature values.

### 5.2 F2 — JSON serialization spec vs existing helper (High, Consistency)

**The concern.** Protocol V1 §9 specifies: "JSON 使用 UTF-8、排序 key、compact
separators、终止换行，禁止 NaN/Infinity" (JSON uses UTF-8, sorted keys,
compact separators, trailing newline, no NaN/Infinity). The existing
`manifest.py:json_bytes` uses:

```python
json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
```

This produces indented JSON (not compact) and does not sort keys. If M1-04 reuses
this helper for `qualification.json` and `working_points.json`, the output will
not match the Protocol's serialization spec. This breaks hash
reproducibility — the SHA-256 of a compact+sorted JSON file differs from the
SHA-256 of an indented+unsorted one.

**Recommendation.** Either add a separate `compact_json_bytes` helper
(`sort_keys=True, separators=(",", ":")`) for M1-04 JSON artifacts, or update
the Protocol to specify which format each JSON file uses. The Protocol should
also clarify whether `manifest.json` itself uses the compact format or the
existing indented format.

### 5.3 F3 — `_EXPECTED` update not called out (Medium, Clarity)

**The concern.** The Sprint §3 says to add and seal five new blocks
(`folding`, `working_points`, `qualification`, `final_fit`,
`development_artifacts`) in `adversarial_mlp_protocol_v1.yaml`. The existing
protocol loader (`config.py:144–161`) performs strict equality checking via
`_strict_equal(raw, _EXPECTED)`. The `_EXPECTED` dict (lines 47–89) does not
contain these blocks. Adding new YAML keys without updating `_EXPECTED` will
cause `_strict_equal` to fail (extra keys in `raw`), rejecting the updated
protocol YAML with `"sealed adversarial MLP protocol changed"`.

**Recommendation.** Add an explicit implementation note that `_EXPECTED` in
`config.py` must be extended with the exact contents of the five new blocks.
The Protocol V1 §3 says "loader 继续执行递归 type-strict、mapping-order-strict、
list-order-strict、missing/extra/value mutation rejection" — this implies the
loader must enforce strict checking on the new blocks, but doesn't call out the
`_EXPECTED` update explicitly.

### 5.4 F4 — fold_metrics.csv schema ambiguity (Medium, Clarity)

**The concern.** Protocol V1 §9 says: "fold_metrics.csv 每行是一个
`(target_lambda, fold_index, epoch)`，其余列 exact 使用 M1-03 epoch fields，
并附 `fold_seed`、`best_epoch`、`best_validation_weighted_auc`."

This could mean:
- (a) one row per epoch, with fold-level summary fields (`fold_seed`,
  `best_epoch`, `best_validation_weighted_auc`) repeated on every epoch row;
- (b) one row per epoch for epoch fields, plus a separate summary row.

Option (a) is unusual (repeating summary fields on every row is redundant) but
simpler to parse. Option (b) is cleaner but requires a row-type discriminator.

**Recommendation.** Specify the exact column order for `fold_metrics.csv` as
done for `oof_scores.csv.gz` in §5. Clarify whether summary fields are
repeated on every epoch row or only on the best-epoch row.

---

## 6. Cross-Reference Verification

### 6.1 FR-001 R4 item-by-item mapping

| FR-001 R4 requirement | Protocol V1 section | Match |
|---|---|---|
| Merge train+validation into development | §2: "development 行合并原 train 与 validation" | Exact |
| Stable 5-fold by canonical identity | §3–4: SHA-256 identity hash, mod 5 | Exact |
| No cross-fold/split identity duplication | §4: "每个 identity exact 属于一个 validation fold" | Exact |
| Only pre-registered λ={0.00,0.05,0.10,0.20,0.50} | §4: "按 protocol lambda 顺序" (YAML: `target_lambdas`) | Exact |
| Same fold reuses init seed and batch order | §4 + design §8.5: fold_seed = 42 + fold_index | Exact |
| Complete, finite, exactly-once OOF per row | §5: "恰好产生一个 validation score" | Exact |
| Weighted AUC, 3 working-point KS, signal/background efficiency | §6 | Exact |
| AUC >= 0.80 | §3: `auc_minimum=0.80`; §7: "AUC >= 0.80" | Exact |
| 3 KS <= 0.10 | §3: `ks_maximum=0.10`; §7: "loose/medium/tight KS 各 <= 0.10" | Exact |
| Signal efficiency strictly > achieved background | §3: `signal_efficiency_strictly_greater=true`; §7: strict `>` | Exact |
| Multiple eligible → highest AUC, 1e-6 tie → smaller λ | §7: best_auc-relative 1e-6 tie-break | Exact (narrowed) |
| No eligible → `no_eligible_candidate`, no model, no test | §7: exit 0, no model/scaler/test artifact | Exact |
| Eligible → full-development fit, median epoch, no re-early-stop | §8: median of 5 best_epoch, fixed epochs, no early stopping | Exact |
| No test feature reading during final fit | §8: "不创建 validation、AUC checkpoint 或 early stopping" + §2 isolation | Exact |

### 6.2 FR-001 R6 (artifacts) mapping

| FR-001 R6 requirement | Protocol V1 section | Match |
|---|---|---|
| Non-overwrite run directories | §9: `RunTransaction` allowed-root, non-overwrite | Exact |
| Output within `neural/runs/` root | §9: allowed-root | Exact |
| Config snapshot, metrics, predictions, plots, manifest, SHA-256 | §9 artifact schema | Exact |
| Gzip: file hash + canonical CSV content hash | §5: "gzip file SHA-256 与解压 canonical CSV content SHA-256" | Exact |
| Manifest: protocol, input, output, software, git, platform, counts, schema, deterministic, performance | §9: "input/protocol/config/output hashes、schema/counts...deterministic environment、wall time、peak memory" | Exact |
| Failed runs preserve failure receipt | §9: "异常终止...保留 failure receipt" | Exact |

### 6.3 FR-001 R7 (tests) mapping

| FR-001 R7 requirement | Protocol V1 §10 | Match |
|---|---|---|
| Preprocess, training, golden, integration, CLI, smoke tests | §10 covers training (M1-04 scope) | Covered |
| Model I/O shape, parameter count, GRL gradient, background restriction, weight normalization, fold scaler leakage, qualification, test-opening rejection | §10: fold hash, OOF integrity, AUC/KS/efficiency, tie-break, 5×5 complete, final fit, 3 terminal states, poison tests | Covered |
| README, environment, run manual, artifact schema, tech report | Sprint §3 docs (deferred to M1-06 per design §13) | Out of M1-04 scope |

### 6.4 Exit code consistency

| Terminal state | Protocol V1 | `neural/AGENTS.md` exit code | Match |
|---|---|---|---|
| Eligible or no-eligible | §7: exit 0 | 0 = "Success or declared normal scientific terminal state" | Exact |
| Input binding failure | §9: `InputBindingError` | 3 = "Input, schema, hash, or protocol binding failure" | Exact |
| Run-path failure | §9: run-path error | 4 = "Run-path or transaction failure" | Exact |
| Internal error | §9: internal error | 70 = "Unexpected internal error" | Exact |

---

## 7. Pre-Implementation Status Summary

The following items are **expected gaps** — the Sprint M1-04 explicitly tasks
M1-04 with creating them. They are listed here for completeness and are **not**
defects.

### 7.1 Missing source files (to be created in M1-04)

| File | Sprint reference | Design doc reference |
|---|---|---|
| `neural/src/training/folds.py` | Sprint §3, §5.1 | Design §5 |
| `neural/src/training/qualification.py` | Sprint §3, §5.2 | Design §5 |
| `neural/src/training/development.py` | Sprint §3 | **Not in design §5** (see F6) |
| `neural/src/artifacts/plots.py` | Sprint §3, §5.3 | Design §5 |

### 7.2 Missing protocol YAML blocks (to be added and sealed in M1-04)

| Block | Protocol V1 §3 | Current YAML status |
|---|---|---|
| `folding` | `count=5`, `algorithm=sha256_identity_v1`, mod 5 | Absent |
| `working_points` | `loose=0.50, medium=0.20, tight=0.10` | Absent |
| `qualification` | `auc_minimum=0.80`, `ks_maximum=0.10`, strict >, `auc_tie_atol=1e-6` | Absent |
| `final_fit` | full-development scaler, seed 42, median epoch, no early stop | Absent |
| `development_artifacts` | exact output schemas from §9 | Absent |

### 7.3 Missing CLI subcommand (to be implemented in M1-04)

| Subcommand | Sprint §3, §7 | Current `cli/train.py` |
|---|---|---|
| `higgsml-train develop` | `--input-run`, `--protocol`, `--run-dir` | Bare parser, no subcommands (24 lines) |

### 7.4 Missing tests (to be created in M1-04)

| Test file | Sprint §7 | Protocol V1 §10 |
|---|---|---|
| `tests/unit/test_folds.py` | §7 focused verification | Fold hash, reorder stability, coverage, contamination |
| `tests/unit/test_qualification.py` | §7 focused verification | AUC/KS boundaries, strict efficiency, tie-break |
| `tests/integration/test_development_run.py` | §7 focused verification | 5×5 complete, 3 terminal states, poison, CLI |

### 7.5 Existing M1-03 primitives (verified present, not modified)

| File | Function | Sprint dependency |
|---|---|---|
| `trainer.py` | `train_fold`, `validate_checkpoint`, `lambda_for_epoch` | §2: "M1-03 已完成确定性单 fold 训练原语" |
| `dataset.py` | `validate_development_frame`, `build_validated_fold`, `FoldLocalScaler` | §5.1 fold/OOF building |
| `network.py` | `AdversarialMLP`, `Classifier`, `Adversary`, GRL | §5.3 final model |
| `losses.py` | BCE, adversarial CE, mass bins, bin weights | §5.2 metrics |
| `config.py` | `TrainingProtocol`, `load_training_protocol`, `_EXPECTED` | §3 protocol seal (needs update, see F3) |
| `transaction.py` | `RunTransaction` | §5.3 artifact publication |
| `manifest.py` | `sha256_file`, `json_bytes`, `peak_memory_bytes` | §5.3 manifest (needs compact JSON, see F2) |

---

## 8. Risk Assessment

| Risk | Mitigated by | Residual concern |
|---|---|---|
| Test feature leakage via direct pandas load | Protocol V1 §2 two-stage reader; Sprint §9 physical isolation | Reader not mandated as sole entry point (F1) |
| Test feature leakage via poison values | Protocol V1 §10 poison tests (5 components) | Existing tests only cover validator (F19) |
| Threshold/qualification float tolerance drift | Protocol V1 §7: "门槛比较不使用 epsilon"; tie-break only at selection layer | None — precisely specified |
| OOF contamination by test identity | Protocol V1 §5: "test identity...均失败" | Pre-implementation — test not yet written |
| Final fit overfitting without early stopping | Protocol V1 §8: median epoch from fold-best; OOF already frozen | By design — risk accepted, quality judged by OOF |
| Protocol YAML mutation after results | `config.py` strict-equality loader | `_EXPECTED` must be updated for new blocks (F3) |
| Hash irreproducibility from JSON formatting | Protocol V1 §9: compact, sorted keys | Existing `json_bytes` doesn't match (F2) |
| Symlink/reparse-point traversal of input run | Protocol V1 §2: path validation | Existing `RunTransaction` doesn't check input (F5) |
| Relaxing rules after seeing results | `neural/AGENTS.md`: "Do not relax...after seeing results" | None — documents are pre-implementation |

---

## 9. Conclusion

The Sprint M1-04 document and Development Protocol V1 are **well-constructed,
scientifically sound, and ready for implementation**. The qualification rules,
OOF contract, tie-break logic, held-out test isolation strategy, and artifact
schema faithfully implement FR-001 R4/R6/R7 without relaxation. The two
High findings (F1, F2) are about enforcement precision and serialization
consistency — both are addressable with small document clarifications before
implementation begins. No document defect could lead to test data leakage or
rule relaxation if the Protocol is implemented as written; the findings
strengthen the existing safety design by making implicit guarantees explicit.

**Recommendation:** Address F1–F7 before implementation begins. F8–F13 are
minor clarifications that can be addressed during implementation. The Sprint is
cleared for implementation pending resolution of the High findings.
