# Sprint M1-05 Review Report

- **Reviewer:** opencode-go / kimi-k2.7-code
- **Review date:** 2026-09-02
- **Review type:** Document review
- **Target documents:**
  - `neural/docs/sprint-m1-05.md`
  - `neural/docs/test-opening-protocol-v1.md`
  - `neural_adversarial_mlp_refactor_design.md`（仅 M1-05 / test-opening 相关章节）
- **Source of truth:**
  - `neural/docs/FR-001-adversarial-mlp-refactor.md`
  - `AGENTS.md`（仓库根目录）
  - `neural/AGENTS.md`

## Executive Summary

`neural/docs/test-opening-protocol-v1.md` 是一份 fail-closed、审计完备的一次性 held-out MC test-opening 规范。它正确要求了：development run 资格与产物绑定必须在 claim 之前完成；test feature 解码必须在原子 claim 之后；claim 使用 `O_CREAT|O_EXCL` 且永不删除；冻结模型、scaler、threshold 只能用于评分而不得调用任何训练/阈值选择路径；结论仅能为 `test_reproduced` 或 `test_nonreproduction`；两种结论均 exit 0 且不触发反馈循环。

`neural/docs/sprint-m1-05.md` 准确地把协议拆分为可执行的工作包、任务清单、验收标准与验证命令，范围边界清晰，明确排除了无单独授权时运行权威 `open-test`。

`neural_adversarial_mlp_refactor_design.md` 中 §6.3 与 §10.2 对 test-opening 的描述与协议基本一致，但 §10.2 的 test run 产物树缺少 `config.yaml`，与 Test-opening Protocol V1 §7 不一致。

**总体结论：** M1-05 目标文档在科学安全、授权诚实、claim/test-decode 顺序、冻结阈值评价、MC-only 边界和 terminal-receipt 耐久失败语义方面均与 `FR-001`、`AGENTS.md` 及已完成的 M1-04 产物保持一致。发现的 issues 均为低风险或澄清级，不影响文档作为实现基线的可用性。

## Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Info | Correctness / Security | `neural/docs/test-opening-protocol-v1.md` §1、§2、§3 | 授权诚实性与 MC-only 边界表述正确。`authorization-reference` 仅作为外部授权的审计引用，软件不伪称能自行证明用户批准；test-opening 需要 eligible frozen development run 与另行明确授权；所有输出只能称为 educational/technical demo。 | 协议 §1："`authorization-reference` 只保存外部批准的审计引用，不是密码学证明，也不能由软件自行判断用户是否真实批准。" §1 同时明确无单独授权不得运行权威 `open-test`。 | 无需修改。实现时必须在 CLI 与 manifest 中原样保留该审计语义。 |
| Info | Correctness | `neural/docs/test-opening-protocol-v1.md` §2、§3 | Pre-claim / test-decode 顺序与原子 claim 语义正确。全部 development/preprocess/artifact/hash 校验在 claim 前完成；claim 以 `O_CREAT|O_EXCL` 原子创建；任何 terminal 或 `claimed` 状态永久拒绝重试；硬崩溃保留 `status=claimed, terminal_receipt=false` 且不可重试。 | 协议 §2 步骤 1–7 均在尝试 claim 前执行；§3 明确要求 `O_CREAT|O_EXCL`、`state/` 目录检查、"claim 创建后永不删除"、"硬崩溃/断电可能留下 `status=claimed, terminal_receipt=false`，该状态明确表示结果未知且仍永久不可重试"。 | 无需修改。实现时确保 claim 创建与 terminal receipt 更新均使用同目录临时文件加 `os.replace`，不得先删除 claim。 |
| Info | Correctness | `neural/docs/test-opening-protocol-v1.md` §4、§5、§6 | Test-only reader 与冻结评价路径正确。Test 特征解码仅在 claim 后发生；reader 先按 `split` 路由再解析 test 行；评分只使用 `weights_only=True` 加载的冻结 model/scaler/working points，不得调用 trainer/optimizer/scaler fit/threshold selection。 | 协议 §4 描述 split-first 路由；§5 要求 `torch.load(..., map_location="cpu", weights_only=True)`、`eval()`、冻结 scaler 与 finite `[0,1]` sigmoid score；§6 禁止在 test 上重新选择或调整 threshold。 | 无需修改。实现时通过 spy/poison 测试证明训练与阈值选择路径未被调用。 |
| Info | Correctness / Risk | `neural/docs/test-opening-protocol-v1.md` §6 | 空选中背景下的 KS 保守规则正确且 fail-closed。若冻结 threshold 在 test 上选中的背景绝对权重和为零，achieved background efficiency 固定为 `0.0`，KS 保守记为 `1.0`，结论为正常的 `test_nonreproduction`，且禁止在 test 上降低 threshold 制造非空样本。 | 协议 §6："若某个冻结阈值在 test 上选中的背景绝对权重为零，则 achieved background efficiency 固定为 `0.0`，该工作点的 KS 保守记为 `1.0`；这属于正常的 `test_nonreproduction`，不是 input binding 错误，也不得在 test 上降低阈值以制造非空样本。" | 无需修改。建议在 `test_metrics.json` 中同时记录 sentinel reason，如 `"empty_selected_background"`，避免下游把 `KS=1.0` 误解为实际最大分离。 |
| Info | Correctness / Risk | `neural/docs/test-opening-protocol-v1.md` §7、§8 | Terminal-receipt 耐久失败语义严谨。正常 test run 已发布后，若 terminal receipt 的 `os.replace` 或 durable directory flush 失败，命令返回 exit 4，development state 保持 `claimed`/indeterminate 且永久不可重试，已发布的 test run 不得覆盖或删除，且软件不得谎报为完整成功。 | 协议 §7："若正常 test run 已原子发布、但 terminal state replace 或 durable directory flush 随后失败，则命令返回 exit 4；现存 state 按 `claimed`/indeterminate 永久不可重试，已经发布的 test run 也不得覆盖或删除。软件不得把该状态谎报为完整成功。" | 无需修改。实现时确保 POSIX 使用 `dir.fsync()`，Windows 使用等价的 `FlushFileBuffers`/`FlushFile` 语义，并在 CLI 中给出明确的 partial-success 提示。 |
| Info | Consistency | `neural/docs/test-opening-protocol-v1.md` §8、`neural/AGENTS.md` §"Stable process exit codes" | 稳定退出码与 `neural/AGENTS.md` 完全一致，且对 qualification refusal（5）与 input binding（3）做了符合 test-opening 语义的映射。 | 协议 §8 列出 `0/2/3/4/5/70`；与 `neural/AGENTS.md` 表格逐条对应；§7 进一步明确 terminal-receipt durability 失败也归入 exit 4。 | 无需修改。CLI 实现必须按此映射返回退出码。 |
| Info | Requirement / Scope | `neural/docs/sprint-m1-05.md` §3、§4、§9 | Sprint 范围与风险控制正确覆盖了所有 frozen M1-05 约束：eligible/完整/未开启 run 才能开启一次 test；test 结果不反馈到训练/阈值/候选决策；无单独授权不得运行权威 held-out test；禁止 `--force`、`--retry` 或科学参数覆盖。 | Sprint §3 纳入范围明确列出一次性 test-opening、冻结评价、审计收据、claim/篡改/重复调用测试；§4 排除权威 test 实际开启、按 test 结果重训/调参、真实数据或 sideband；§9 明确禁止 `--force`、`--retry`、科学参数覆盖。 | 无需修改。实现与 CLI smoke 必须遵守这些排除项。 |
| Low | Consistency / Layout | `neural_adversarial_mlp_refactor_design.md` §10.2 vs `neural/docs/test-opening-protocol-v1.md` §7 | 设计文档的 test run 产物树未列出 `config.yaml`，与 Test-opening Protocol V1 §7 的正常布局不一致。 | 设计 §10.2 列出 `artifacts/`、`predictions/`、`plots/`，未含 `config.yaml`；协议 §7 正常布局为 `config.yaml`、`artifacts/test_metrics.json`、... | 更新设计 §10.2，使其与协议 §7 一致，明确 test run 顶层包含 `config.yaml`（记录 development run、protocol、authorization reference 等快照）；或显式声明协议 §7 为 M1-05 布局的唯一来源。 |
| Low | Consistency / Clarity | `neural/docs/test-opening-protocol-v1.md` §2 vs `FR-001-R6`、`neural/AGENTS.md` | 允许的输出根目录描述方式与 FR-001 及项目运行约定略有差异。协议说"位于当前工作目录的 `runs/` allowed root 下"，而 FR-001-R6 要求"位于允许的 `neural/runs/` 根下"，`neural/AGENTS.md` 要求从 `neural/` 运行命令。 | 协议 §2："`development-run` 与 `run-dir` 均必须位于当前工作目录的 `runs/` allowed root 下"；FR-001-R6："输出目录必须位于允许的 `neural/runs/` 根下"。 | 在协议 §2 增加一句说明：命令按 `neural/AGENTS.md` 从 `neural/` 运行，因此当前工作目录的 `runs/` 即 `neural/runs/`；或显式将 allowed root 指向 `neural/runs/`。 |
| Low | Clarity | `neural/docs/test-opening-protocol-v1.md` §2 步骤 6 | 原 preprocess run 的路径解析规则"relative `runs/...` 相对 root parent"表述不够清晰，容易误实现为相对于 repository root 之外的位置。 | 协议 §2 步骤 6："preprocess run 使用同一 `runs/` 根：absolute 必须 contained；relative `runs/...` 相对 root parent，其他 relative path 相对 root，最终再次验证 resolved containment。" | 明确"root parent" 指 allowed-root 的父目录（即从 `neural/` 运行时），`runs/...` 相对 `neural/` 解析，其他相对路径相对 `neural/runs/`；并给出示例。 |
| Low | Security / Clarity | `neural/docs/test-opening-protocol-v1.md` §1、§3、§7 | `authorization-reference` 将被持久化到不可变的 claim 与 test manifest，但协议未明确提醒该引用必须是公开可审计标识，不得包含敏感凭证。 | 协议 §1 称 authorization reference 为 "non-empty-audit-reference"；§3 与 §7 要求记录该值。 | 在 §1 增加安全提示：authorization reference 应仅为公开可审计的外部授权标识（如工单号、审批单 ID），不得包含密码、API key、token 或其他敏感信息；并建议扩大 obvious credential 模式检测（case-insensitive `secret`、`private_key` 等）。 |
| Low | Risk / Clarity | `neural/docs/test-opening-protocol-v1.md` §7、§8 | Terminal-receipt durability 失败返回 exit 4 时，协议未定义 CLI 日志/stdout 应如何向用户和审计表达"部分发布"状态。 | 协议 §7 只要求"返回 exit 4"、"软件不得把该状态谎报为完整成功"，未给出输出格式。 | 在 §8 CLI 小节补充：exit 4 时 CLI 必须输出稳定提示，如 `"test run published at <path>, but terminal receipt durability failed; exit 4; manual audit required"`，并确保 test run manifest 的 `boundaries` 不设置 `terminal_receipt_persisted=true`。 |
| Low | Documentation | `neural/docs/test-opening-protocol-v1.md` §3、§7 | Terminal receipt 的成功/失败 JSON schema 未完整枚举，尤其是成功 receipt 是否保留 development manifest SHA、authorization reference 等初始 claim 字段不够明确。 | 协议 §3 列出初始 claim 字段；失败 receipt 列出字段；成功 receipt 只列出 status、test manifest SHA、完成时间和 `test_features_opened=true`。 | 在 §3 或 §7 增加 terminal receipt 的完整字段表（或 JSON schema），明确成功 receipt 必须保留 development manifest SHA、resolved logical test run path、authorization reference，并追加 test manifest SHA、completed time、`test_features_opened=true`。 |
| Low | Test / Maintainability | `neural/docs/sprint-m1-05.md` §5.1、§5.2 | Sprint 任务清单当前全部为未勾选状态（pre-implementation 占位），实现后需要回填证据。 | Sprint §5.1 与 §5.2 中所有任务为 `[ ]`。 | 实现关闭 Sprint 时必须补充：勾选已完成任务、附加验证命令输出摘要、说明是否仅运行 fixture-only smoke、是否未运行权威 `open-test`、receipt 示例路径。 |

## Detailed Assessment

### 1. 科学安全与 MC-only 边界

三份目标文档均严格限定在 MC-only 范围，未引入真实数据、sideband 或控制区。`test-opening-protocol-v1.md` §1 明确 `open-test` 仍需"用户针对某个权威 development run 的另行明确授权"，且 fixture 测试中使用的 `synthetic-fixture-only` 不得解释为权威授权。这与 `neural/AGENTS.md` "Development may not read held-out test feature values. Test opening requires an eligible frozen development run and separate explicit user authorization" 完全一致。

`test-opening-protocol-v1.md` §4 的 split-first reader 保证 test feature token 在 claim 前不被数值解码；§5 的 `weights_only=True` 模型加载避免 pickle 反序列化风险；§6 的 frozen threshold 评价禁止任何训练或超参数调整。这些设计均满足 `FR-001` R5 与 R3 的安全要求。

### 2. 决策完整性与正确性

协议 §2 的 7 步 pre-claim 顺序覆盖了 output target、development run containment、manifest schema/status、artifact SHA-256、config/qualification/working_points/scaler/model payload 绑定、preprocess run 回溯、claim 文件存在性检查。该顺序保证"任一 development artifact 任一字节变化会在 test 读取前被发现并拒绝"（Sprint §6）。

协议 §3 的 claim/receipt 状态机包含 `claimed`、`test_reproduced`、`test_nonreproduction`、`failed_after_claim`，并区分"test 未读"与"claim 后评价失败"，满足 Sprint §5.1 的测试要求。

协议 §6 的 reproduction predicates 与 development qualification 保持一致（AUC `>=0.80`、三个 KS `<=0.10`、signal efficiency 严格大于 achieved background efficiency），并且已显式要求"每个预期 test identity 恰好产生一次 finite `[0,1]` score、发布行数与两处 manifest count exact 相等且 schema/order/hash 完整"，弥补了早期版本中 prediction completeness 未与结论谓词直接绑定的不足。

### 3. 保守的空选中背景 KS 规则

协议 §6 对"冻结 threshold 在 test 上空选中背景"的处理是科学上安全的选择：

- achieved background efficiency 固定为 `0.0`，符合空集的数学极限；
- KS 保守记为 `1.0`，确保该工作点必然不满足 `KS <= 0.10`，从而结论为 `test_nonreproduction`；
- 明确禁止在 test 上降低 threshold 来人为制造非空样本，防止 peeking。

该规则不会触发重训、阈值调整或错误地标记为 input binding 失败。建议在 `test_metrics.json` 的 reasons 中增加 `empty_selected_background` sentinel，以便审计人员区分这是空样本 sentinel 而非真正的最大分离。

### 4. 授权诚实与 Claim 语义

协议对 `authorization-reference` 的处理体现了授权诚实：它仅作为外部审批的审计引用，不是密码学证明，软件也不得自行判断用户是否真实批准。命令行不提供 `--force`、`--retry`、threshold 或模型覆盖选项，防止实现层绕过授权。

Claim 文件固定在 development run 的 `state/test_opening.json`，使用 `O_CREAT|O_EXCL` 保证唯一性；任何 terminal state 或硬崩溃遗留的 `claimed` 状态均永久拒绝重试。`state/` 目录的创建与验证步骤已在当前修订版中补充，解决了早期版本中目录并发创建语义不明确的问题。

### 5. Terminal-Receipt 耐久失败语义

协议 §7 对 terminal-receipt durability 失败的处理是本轮修订的重点改进之一：

- 正常 test run 已原子发布，但 receipt 的 `os.replace` 或 directory flush 失败 → exit 4；
- development state 保持 `claimed`/indeterminate，永久不可重试；
- 已发布的 test run 不得覆盖或删除；
- 软件不得谎报为完整成功。

这避免了"test run 存在但审计收据丢失"被误报为成功。实现时应注意 POSIX 与 Windows 的 durable flush 差异，并在 CLI 输出中明确提示 partial publish，以便操作员进行人工审计。

### 6. 产物绑定与冻结阈值评价

协议 §7 的 test run 产物布局明确：test metrics、scores、ROC、mass-sculpting 图和 manifest；scores CSV 的列顺序、行排序、双 SHA-256（gzip file 与 canonical CSV content）均做了 deterministic 规定。manifest 最后写入并覆盖除自身外所有发布文件的 size/SHA-256，与 M1-04 `RunTransaction` + manifest-last 模式一致。

冻结模型评价路径（§5–§6）要求严格：使用 fresh `AdversarialMLP` 加载 classifier/adversary state，`eval()` 后只用冻结 scaler transform 15 features，输出 finite `[0,1]` sigmoid score；工作点 threshold 与 target 来自 development 已冻结的 selected candidate，不得在 test 上重新选择或调整。

### 7. 稳定退出与 CLI

退出码映射与 `neural/AGENTS.md` 完全一致：`0` 为正常 terminal status，`2` 为 argparse usage，`3` 为 input/schema/hash/binding 失败，`4` 为 run-path/transaction 失败，`5` 为 qualification/test-opening refusal，`70` 为 unexpected internal error。CLI 日志限制为阶段、terminal status 与 run path，不得输出 test row/value/identity/score，符合安全要求。

### 8. 可执行验收测试

Sprint §7 的验证命令来自 `neural/AGENTS.md` 并补充了 fixture-only CLI smoke，明确"不得在无单独授权时指向权威 development run"。§9 最小测试门覆盖无资格、artifact 篡改、路径穿越、并发竞争、硬崩溃模拟、poison row、frozen model/scaler/threshold spy、manifest-last 等场景，足以在实现后证明机制正确性。

唯一需要注意的是：Sprint §7 中 `tests/integration/test_open_test_cli.py` 的文件名应确保与实现阶段实际创建的测试模块一致；若采用不同命名，需在 Sprint 关闭前同步。

## Conclusion

`test-opening-protocol-v1.md` 与 `sprint-m1-05.md` 构成了 M1-05 的一份**科学上合理、实现上可行、安全上 fail-closed** 的基线文档。它们与 `FR-001` R5/R6、两级 `AGENTS.md` 以及已完成的 M1-04 产物保持一致。

本次评审重点关注的三个方面均得到满足：

1. **空选中背景 KS 规则**：协议采用保守 sentinel（KS=1.0、efficiency=0.0），结论为正常 `test_nonreproduction`，并禁止 threshold 调整。
2. **Authorization-reference hygiene**：协议明确 reference 仅作审计、拒绝明显 credential 形式、不提供 `--force`/`--retry`。
3. **Terminal-receipt durability failure**：协议明确定义了 receipt replace/directory flush 失败时的 exit 4、indeterminate state、不可覆盖 output 与禁止谎报成功。

发现的 issues 均为**低风险/澄清级**，集中在：

1. 设计文档 §10.2 缺少 `config.yaml`；
2. 输出根目录与 preprocess `input_run` 路径解析的表述可更清晰；
3. Authorization reference 的安全提示与 credential 模式可加强；
4. Terminal-receipt durability 失败时的 CLI 提示与 receipt schema 可进一步具体化；
5. Sprint 任务清单需在实现后回填证据。

文档评审阶段建议接受上述澄清后作为实现基线。实现阶段必须严格遵守：不运行权威 `open-test`、不读取真实数据、不修改 development artifact、不在 test 上训练或选择阈值，并在最终验证后补充 Sprint §10 的交付结论。

本评审仅基于源文档与源代码进行一致性检查，未读取、哈希、预处理、评分、绘图或发布任何真实数据，也未执行 `open-test` 或解码 held-out test 值。
