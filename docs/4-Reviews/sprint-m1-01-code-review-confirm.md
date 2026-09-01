# Sprint M1-01 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-01-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-01-code-review-by-opencode-go-glm-5.2.md`
- M1-01 implementation files listed by both reports
- `neural/docs/sprint-m1-01.md`
- `docs/4-Reviews/sprint-m1-01-review-confirm.md`
- `neural_adversarial_mlp_refactor_design.md`
- `AGENTS.md`

**Review Date**

- 2026-09-01

## Overall Conclusion

两份评审均确认 package、双 CLI、科学边界和 win-64 聚焦验证已基本满足 M1-01。GLM 通过 content-hash 重算证明 `environment.yml` 缺少未固定版本的 `conda-lock`，属于必须修复的环境契约缺陷；它也复现了嵌套 run path 发布失败并遗留 staging。Kimi 独立指出异常路径可能掩盖原始异常以及 usage/abort 测试缺口。

上述问题均在 M1-01 范围内接受并立即修复。后续应用服务才可观察的退出码 3/4/5/70、真实 CLI 必填参数和动态训练/预处理行为维持延期；不借代码评审扩大到 M1-02 功能。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Reproducibility | GLM H1; Kimi L3 | `environment.yml` 缺 `conda-lock`，与两份 lock content hash 不一致 | Accept | 加入未固定 `conda-lock` 可精确复现两平台已记录 hash | 添加依赖并增加环境/lock 契约测试；不重新求解或编辑 lock。 |
| 2 | Medium | Correctness | Kimi M1; GLM L2/L3 | 发布竞态/异常可能掩盖原异常并遗留 staging | Accept | 直接探针复现嵌套目标 `FileNotFoundError` 与 orphan | staging 放到目标父目录；支持嵌套目标；发布错误转为 `RunPathError`；异常路径保留原始异常并记录发布失败位置。 |
| 3 | Medium | Test | Kimi M2; GLM L4 | `abort_without_receipt` 和事务 guard 路径未测试 | Accept | 公共 API 与 equal-root/double-publish 等语义尚无回归保护 | 添加 abort、equal-root、nested、double-publish 测试。 |
| 4 | Medium | Test | Kimi M3; GLM M1 | usage 退出码 2 未自动测试 | Accept | 手工探针已验证，但 review-confirm #13 要求自动化 | 两个 CLI 加未知参数 rc=2 集成测试。 |
| 5 | Medium | Hygiene | GLM M2 | `neural/data`/`runs` 内容未被 ignore | Accept | 根 AGENTS 禁止提交数据和 run artifacts | 根 `.gitignore` 增加内容忽略并保留 `.gitkeep`。 |
| 6 | Low | Requirement | GLM L5 | Sprint 目标中的统一日志未实现/未跟踪 | Accept | 设计阶段 1 明确日志基础 | 增加最小 `configure_logging`，CLI 在正常执行前配置 stderr 日志；不引入后续业务日志。 |
| 7 | Low | Test | GLM L6 | `pyproject.toml` 与 `environment.yml` pins 可漂移 | Accept | 两处重复声明相同 runtime pins | 添加共享依赖版本一致性测试，允许 pytest/pip/conda-lock 仅存在于环境文件。 |
| 8 | Low | Path safety | Kimi L1 | symlink/大小写路径边界未显式测试 | Partial | `resolve(strict=False)` 已解析现有 symlink；Windows symlink 测试需权限且非稳定 CI 条件 | 本次覆盖 nested/equal-root/parent 语义；未来在有稳定 symlink fixture 的平台补测试。 |
| 9 | Low | Packaging | Kimi L2; GLM I4 | 顶层 `src` 可能与其他 package 冲突 | Reject | 设计与文档确认明确采用 `src.cli.*`，当前安装与 import 已通过 | 保留精确 entry-point/import 测试；真实冲突才回设计门。 |
| 10 | Low | Test | Kimi L4; GLM I7 | 静态 xgboost guard 不覆盖动态 import | Partial | 当前代码没有动态 import，M1-01 只要求静态或运行时保护之一 | 扩展 AST 测试匹配 `import_module("xgboost")`/`__import__` 字面量，不增加运行时 import hook。 |
| 11 | Info | Exit code | GLM I1 | 3/4/5/70 尚未由 stub CLI 映射 | Accept (Deferred) | M1-01 没有对应应用服务和异常类型 | 在拥有真实调用路径的 M1-02/M1-04/M1-05 分别接线并测试。 |
| 12 | Info | CLI | GLM I2 | 空参数调用当前 rc=0 | Accept (Deferred) | M1-01 明确交付两个空 CLI | M1-02 开始为 preprocess 加必填参数；train 在所属 Sprint 增加子命令和必填输入。 |
| 13 | Info | Test | GLM I3 | 自动测试使用 `python -m` 而非已安装脚本 | Reject | entry point 集合已有静态测试，真实脚本已在锁定环境 smoke 通过 | 保留当前快速测试并在 Sprint 验证中继续执行真实脚本 smoke。 |
| 14 | Info | Test infrastructure | GLM I5 | 裸 `pytest` 在未安装 package 时可能失败 | Reject | README 明确先 editable install，并规定 `python -m pytest` | 不增加隐式 sys.path 修改；保持安装后测试的真实使用方式。 |
| 15 | Info | Scope | 两评审正面项 | M1-02 至 M1-06 功能正确缺席，科学边界正确 | Accept | 与 Sprint/FR 和根 AGENTS 一致 | 修复不得引入 ROOT、训练、OOF 或 test-opening 行为。 |

## Needs Immediate Action

- 修复环境 content-hash 来源、事务 nested/异常路径、usage/abort 测试和 artifact ignore。
- 增加最小日志配置、dependency contract 与动态 import 字面量保护。

## Can Be Deferred

- 退出码 3/4/5/70 的真实 CLI 映射。
- 预处理/train 必填参数、symlink 平台测试与任何科学功能。

## Final Status

在立即动作通过聚焦与完整验证后，M1-01 可接受并提交。
