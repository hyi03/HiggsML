# Sprint M1-06 Verification Evidence

## 1. 当前结论

截至 2026-09-02，技术执行停在 `authority_environment_preflight`。当前主机是 Windows/AMD64，不是
locked native `osx-arm64`；因此 authority environment restore、full-data preprocess/golden 和完整
development OOF 尚未运行。用户随后明确表示“不要求 test，完成 M1-06 并提交”，接受这些验证项保持
`blocked`/`not_run` 并豁免其作为本 Sprint 的 closure/commit gate。该豁免只允许交付关闭，不会把
Windows/synthetic 结果升级为 authority evidence。

未获得针对具体 eligible frozen development run 的单独 `open-test` 授权；其正确状态为 `not_run`，
且不是 M1-06 closure blocker。

## 2. Evidence 字段

| 字段 | 允许值 |
|---|---|
| `status` | `passed`、`failed`、`blocked`、`not_run`、`not_applicable` |
| `method` | `static`、`automated`、`preprocess`、`development`、`test_opening` |
| `platform` | `windows-amd64`、`osx-arm64`、`not_applicable` |
| `data_scope` | `source_only`、`synthetic_mc`、`full_mc`、`held_out_mc` |
| `authority` | `true`、`false` |

## 3. 本地非权威证据

执行目录均为 `D:\code\HiggsML\neural`；日期为 2026-09-02。

| Evidence | Status | Method | Platform | Data scope | Authority | 命令与实际结果 |
|---|---|---|---|---|---|---|
| platform/environment probe | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `conda run -n pytorch python -c ...` exit 0；Windows/AMD64、Python 3.12.13、PyTorch 2.7.1、threads 8；ambient deterministic flag 为 false，训练入口自身的 deterministic 行为由测试覆盖 |
| local `osx.yml` bytes observation | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `Get-FileHash -Algorithm SHA256 osx.yml` exit 0；SHA-256 `f54522acff344e2644ad8dd03b3a913b6d38fd2e097cfe9a00244748fae84430`；这不是 authority environment restore 证据 |
| reviewed scientific bytes freeze | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `git diff --exit-code 85b67d1 -- src config/preprocess_protocol_v1.yaml config/adversarial_mlp_protocol_v1.yaml` exit 0；执行时 HEAD 为 `85b67d1704815079bb3aa4fe8f1c9a5eba9ece9d` |
| forbidden runtime/locator audit | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `rg -n "xgboost[.\\/]+src|(from|import)\\s+xgboost|full-baseline-2026-08-10|700600" src config` 无命中（rg exit 1 表示 no match）；未扫描数据目录 |
| console entry-point audit | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `rg -n "^\\s*(higgsml-preprocess|higgsml-train)\\s*=" pyproject.toml` 仅命中两个批准入口 |
| local config ignore | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `git check-ignore -v config/preprocess_run.local.yaml` exit 0，命中 `/neural/config/preprocess_run.local.yaml` |
| reviewed-path untracked audit | `passed` | `static` | `windows-amd64` | `source_only` | `false` | `git status --porcelain --untracked-files=all -- src <two sealed YAMLs>` 无输出；配合 byte diff 排除 frozen runtime path 下未跟踪新增文件 |
| resolved run-path preflight rehearsal | `passed` | `static` | `windows-amd64` | `source_only` | `false` | 对三个不存在的 `runs/*-doc-check-20260902` placeholder 执行 containment/`lexists` 和 `git check-ignore`，均 exit 0；未创建目录或读取数据 |
| documented-path audit | `passed` | `static` | `windows-amd64` | `source_only` | `false` | README/runbook/schema/evidence/report、三个 protocol 文档和 example config 均为 regular file |
| dependency consistency | `passed` | `automated` | `windows-amd64` | `source_only` | `false` | `conda run -n pytorch python -m pip check` exit 0：`No broken requirements found.` |
| two help smokes | `passed` | `automated` | `windows-amd64` | `source_only` | `false` | `higgsml-preprocess --help` 与 `higgsml-train --help` 均 exit 0 |
| focused synthetic mechanism suite | `passed` | `automated` | `windows-amd64` | `synthetic_mc` | `false` | 三个 integration modules：`23 passed in 25.37s` |
| authority orchestration contract | `passed` | `automated` | `windows-amd64` | `synthetic_mc` | `false` | `tests/golden/test_preprocess_authority.py`：`4 passed, 1 skipped in 0.79s`；新增测试以 monkeypatch/local synthetic bytes 验证 gate 顺序、evidence 内容与 exclusive-create，不接触外部 table |
| full local suite | `passed` | `automated` | `windows-amd64` | `synthetic_mc` | `false` | 修订前 `227 passed, 2 skipped`；test-only 修订后最终为 `228 passed, 2 skipped in 80.35s`；外部 r3 table 的 skipped locator/hash probe 属 `source_only` 且不是 pass，其余实际执行用例为 synthetic/source contract |
| skip reason confirmation | `passed` | `automated` | `windows-amd64` | `synthetic_mc` | `false` | targeted `-rs`：`53 passed, 2 skipped in 29.24s`，逐项确认 `authoritative_gate_not_run: external r3-ARM64 table is absent` 与 `directory symlinks are unavailable on this platform` |

Focused synthetic 命令：

```text
conda run -n pytorch python -m pytest -q tests/integration/test_preprocess_micro_root.py tests/integration/test_development_run.py tests/integration/test_open_test_cli.py
```

Full suite 与其他命令见 [`runbook.md`](runbook.md)。两个 local skips 对 Windows development evidence
是已解释边界，但在 authority host 上都必须消失；它们不能视为 authority pass。

最终修订后 `pip check`、两个 help smoke 和 `git diff --check` 再次执行，均 exit 0。

## 4. Authority 与 test-opening gates

| Gate | Status | Method | Platform | Data scope | Authority | 证据/原因 |
|---|---|---|---|---|---|---|
| authority environment restore | `blocked` | `automated` | `osx-arm64` | `source_only` | `true` | 当前执行 host 为 Windows/AMD64；未尝试用 Windows 恢复 `osx.yml` |
| authority zero-skip pytest | `not_run` | `automated` | `osx-arm64` | `synthetic_mc` | `true` | authority environment 未满足 |
| full-data preprocess | `not_run` | `preprocess` | `osx-arm64` | `full_mc` | `true` | 按 preflight 顺序在 host gate 后停止；未读取或 hash 两个 MC ROOT |
| r3-ARM64 comparator | `not_run` | `preprocess` | `osx-arm64` | `full_mc` | `true` | 无新的 authority preprocess run；未生成 comparator evidence |
| complete development OOF | `not_run` | `development` | `osx-arm64` | `full_mc` | `true` | preprocess/golden 前置未通过 |
| alternate qualification branch | `not_applicable` | `development` | `osx-arm64` | `full_mc` | `true` | authority development 未发生；M1-04 synthetic tests 覆盖两种合法终态 |
| authority test-opening | `not_run` | `test_opening` | `osx-arm64` | `held_out_mc` | `true` | 未获得针对具体 frozen run 的单独明确授权；不是 closure blocker |

## 5. Closure decision

- 决策日期：2026-09-02。
- 决策来源：用户明确要求“不要求 test，完成 M1-06，并提交”。
- 接受范围：允许 M1-06 在 authority environment/full-data preprocess/golden/development/test-opening
  均未运行的情况下关闭并提交。
- 不接受的推论：不得把任何 `blocked`/`not_run` 改写为 `passed`，不得宣称 authority/full-data 科学
  复现，且不得据此执行 `open-test`。

## 6. 数据与声明边界

- 未读取、哈希、探测、预处理、评分、绘图或发布真实数据。
- 未打开或读取权威 held-out test，未创建 authority test claim/path。
- 未把 Windows 或 synthetic 证据描述为 full-data/authority 结果。
- 没有实际 authority artifact，因此本文不转录预注册 full-data counts 为运行结果。
- 所有当前结论仅属于 educational/technical demo，不构成 ATLAS 结果、Higgs discovery 或 physics
  measurement。
