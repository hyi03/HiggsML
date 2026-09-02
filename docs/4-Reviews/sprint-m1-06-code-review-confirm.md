# Sprint M1-06 Code Review Confirm

## Reviewed Inputs

- `docs/4-Reviews/sprint-m1-06-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-06-code-review-by-opencode-go-glm-5.2.md`
  （configured GLM primary 不可用，由 `deepseek/deepseek-v4-flash` fallback 完成）
- `.gitignore`、`neural/README.md`、`neural/docs/sprint-m1-06.md`
- `neural/docs/runbook.md`、`neural/docs/artifact-schema.md`
- `neural/docs/m1-06-verification-evidence.md`、`neural/docs/final-technical-report.md`
- `neural/src/preprocessing/authority.py`、相关 protocol、tests 与 M1-05 baseline `85b67d1`

## Overall Conclusion

两份 review 均确认没有科学安全越界、真实数据接触、held-out test 开启或 authority 证据冒充；全部
Windows/synthetic 结果也被独立复验。Gate orchestration 自动化覆盖缺口成立，应以 test-only 方式补齐，
不改变 `neural/src` 或 sealed YAML。文档确实把 `run_authority_gate` 的范围写得过宽，应改为其真实读取
面：批准 lineage、29 列逐表比较、summary counts/duplicates 和 baseline-bound cutflow；新 run manifest
完整性是独立审计项。

不接受新增第三个产品 CLI、runner 或本 Sprint 内修改 frozen authority source。文档评审确认已经明确
选择现有 application function 的固定直接调用，且 authority 执行前必须保持 `neural/src` 和两个 sealed
YAML 相对 M1-05 byte-identical。真实的操作风险通过 test-only orchestration coverage、精确 path preflight、
failure guidance 和文档纠偏处理。

## Decision Table

| No. | Severity | Type | Review Source | Comment | Decision | Evidence and Reason | Follow-up |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Risk | Kimi 1 | 新增 version-controlled authority runner/module entry | Partial | 手工调用风险真实，但 document review confirm 已明确“不新增第三产品 CLI，直接调用 application function”；新增 runner 也是未经批准的新操作接口 | 保持两个 console entry points；加强 runbook cwd/path/exit preflight，不新增 runner |
| 2 | Medium | Test | Kimi 2 | `run_authority_gate` orchestration 未被测试调用 | Accept | 现有 tests 只覆盖 platform、lineage contract 与 table comparator，确实不能提前发现 gate glue/evidence write 回归 | 新增 test-only synthetic orchestration test；monkeypatch authority platform/外部 compare dependencies，不读取任何外部/真实数据；断言 evidence 与 exclusive create |
| 3 | Low | Correctness | Kimi 3 | `xb` duplicate 产生未映射 `FileExistsError` | Partial | 直接 Python application call 不属于两个 product CLI 的 stable-exit adapter；修改 `src` 会破坏 M1-05 scientific freeze，但未映射失败需在操作层明确 | Test 固定 exclusive-create 行为；runbook 规定 duplicate/partial/non-table exit 都是 blocker，保留旧 evidence，换全新 path 前先审计，不在本轮改 `src` |
| 4 | Low | Risk | Kimi 4 | hard-coded protocol path 缺 optional injection | Reject | `repository/neural/config/preprocess_protocol_v1.yaml` 是本版 gate 的刻意 sealed contract；允许注入/改名会扩大 authority 输入面，且与固定 protocol locator 不一致 | 在 runbook/artifact schema 明确 hard-coded reviewed path；不增加参数 |
| 5 | Low | Risk | Kimi 5 | Gate 不强制 runs containment/symlink | Partial | 实现级 enforcement 缺口真实，但当前文档门批准的是固定 direct call，source 必须 frozen；runbook 仅有原则还可更精确 | 增加执行前 Python resolved containment、ordinary path、evidence absent 检查；任一失败停止 |
| 6 | Low | Consistency | Kimi 6 | 静态 audit regex 漏 dotted import | Accept | `xgboost[\\/]+src` 确实不匹配 `xgboost.src`，当前 no-match 不能覆盖该形态 | 改为覆盖 dot/slash/backslash 和 `from/import xgboost`，重跑并更新 evidence |
| 7 | Low | Clarity | Kimi 7 | Full suite 的 `synthetic_mc` 混入一个 skipped source-only probe | Accept | 该 external-table test 未执行数据读取，但分类说明可更精确 | 在 evidence full-suite row 说明 executed tests 为 synthetic/source contracts，skipped external locator 属 `source_only` 且非 pass |
| 8 | Low | Documentation | Kimi 8 | Preprocess manifest 表首行误名 `identity` | Accept | 该行是 top-level header/status，与 `mc_summary.identity` 冲突 | 改名为 `header` |
| 9 | Low | Risk | Kimi 9 | Freeze 未覆盖 CLI、golden test、untracked | Partial | 从 `neural/` 执行的 `src` 已包含 `src/cli/*`，所以 CLI 漏检论据不成立；untracked `src` 确实不进入 `git diff`。Golden test 不参与 authority runtime，不应伪装为 scientific byte gate | 保持 `src` + sealed YAML byte freeze；新增针对这些 path 的 untracked status 检查；不把 test 文件混入 scientific freeze |
| 10 | Medium | Test | GLM 1 | Gate orchestration zero coverage | Accept | 与 Kimi 2 同一核心事实，但 GLM 强调 authority host 首次暴露成本，成立 | 同 No.2；新增测试后 focused/full suite 重跑 |
| 11 | Medium | Risk | GLM 2 | One-liner 无 stable error semantics | Partial | `FileExistsError` 风险成立；新增 runner/修改 source 与已确认边界和 byte freeze 冲突 | 文档明确 preflight、unexpected exit/manual audit/不可复用；本轮不改 source/entry points |
| 12 | Low | Risk | GLM 3 | Gate 缺 containment、absence 与 protocol injection | Partial | Containment/absence 需加强；protocol injection 会放宽 sealed locator，不接受 | 增加 resolved containment/ordinary/absence preflight；明确 protocol path 固定，不注入 |
| 13 | Low | Consistency | GLM 4 | 文档误称 gate 验证新 run manifest/canonical hashes | Accept | `run_authority_gate` 不读取新 run `manifest.json`，只读取 table、summary、cutflow；现有措辞过度 | Sprint/runbook/schema 分开描述 gate 与 preprocess manifest audit，删除不实 gate scope |
| 14 | Low | Clarity | GLM 5 | §6 的 19 features 低估 29-column surface | Accept | `compare_tables` 遍历全部 `protocol.output_columns`（29） | 改为“29 canonical columns，其中 19 model-candidate features” |
| 15 | Low | Risk | GLM 6 | Freeze 对 untracked 与 test/CLI 漏检 | Partial | Untracked 风险成立；`src` 已覆盖 CLI，golden test 不是 runtime scientific bytes | 与 No.9 相同，增加 scoped untracked audit，不扩大 scientific byte definition |
| 16 | Low | Clarity | GLM 7 | Audit regex 漏 dotted import | Accept | 与 Kimi 6 一致且有直接 regex 证据 | 与 No.6 相同，更新命令与实际 evidence |
| 17 | Low | Consistency | GLM 8 | §4 lineage 项目计数歧义 | Accept | §7.1 表内四项已含 golden table，另有 baseline manifest；原句可能被读成六项 | 明列五项：identity manifest/table、enrichment manifest、baseline manifest、r3 table |
| 18 | Info | Correctness | 两份 review | Taxonomy/header、本地证据与 blocked 状态 | Accept | Review 独立复验 `23 passed`、`227 passed, 2 skipped`、pip/help/freeze/ignore/audit；blocked/test-not-run 状态正确 | 应用 taxonomy/header 文档修订；保留 authority blocker 和未提交状态 |

## Accepted/Partial Action Plan

1. 先增加一个 test-only `run_authority_gate` orchestration/exclusive-create 测试，不改 `neural/src`、两个
   sealed YAML 或 product entry points。
2. 纠正 gate scope、29-column 表述、lineage 枚举和 manifest header 名称。
3. 加强 runs resolved containment/evidence absence、unexpected exit/manual audit、untracked scientific
   path 和 dotted-import audit；重跑实际静态证据。
4. 重跑 focused test、full pytest、pip check、两个 help 和 `git diff --check`，只记录实际结果。
5. M1-06 仍停在 authority environment preflight；required authority gates 未通过时不得提交。

## Final Status

**Accepted revisions applied; authority closure blocked.** Accept/Partial 动作已应用：增加 test-only gate
orchestration/exclusive-create coverage，纠正 gate scope/29-column/header/lineage 表述，并加强 resolved
path、untracked path、unexpected exit 与 dotted-import audit。最终本地验证为 `228 passed, 2 skipped`，
`pip check`、两个 CLI help、expanded static audit 与 `git diff --check` 均通过；frozen `neural/src` 和两个
sealed YAML 相对 `85b67d1` 仍 byte-identical。

Authority host 仍不可用，M1-06 必须继续以 blocked/uncommitted 终态停止；不得运行 `open-test`。

## Post-review Owner Override

2026-09-02，用户在获知 authority preflight blocker、`228 passed, 2 skipped` 本地证据和全部未运行边界后，
明确要求“不要求 test，完成 M1-06，并提交”。该决定覆盖本确认文档原有的 commit blocker：允许
authority environment/full-data preprocess/golden/development/test-opening 保持 `blocked`/`not_run` 时
关闭并提交 M1-06。

此 override 不改变 review finding、证据状态或科学约束；不得宣称 authority verification，不得执行
`open-test`，也不得接触真实数据。
