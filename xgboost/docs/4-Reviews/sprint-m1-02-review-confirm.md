# Sprint M1-02 Document Review Confirm

**Reviewed Inputs**

- `docs/3-Plan/sprint-m1-02.md`
- `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-glm-5.2.md`
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `docs/3-Plan/sprint-m1-01.md`
- `AGENTS.md`

**Review Date**

- 2026-09-02

## Overall Conclusion

两份评审均确认 M1-02 的 MC-only、Angular19、development/test 物理分离和不访问真实数据
边界正确。文档可在应用下表的 Accept/Partial 项后进入实施。评审指出的核心缺口是输出
schema、ROOT 输入前后绑定、验证边界和可复现的微型 fixture；这些修订不改变 selection、
权重、split 或任何冻结科学规则。

Kimi 关于“发布 CSV 不得包含 `m4l`、identity、weight”的意见只部分成立：这些字段不得
进入 19 项模型特征，但设计要求分文件发布不改变原行内容，后续 KS、权重和身份审计又
必须使用这些 metadata。因此本次固定 metadata schema，并用模型特征 allowlist 保证它们
不会进入模型，而不是从 CSV 删除。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Requirement | Kimi H1 | Manifest 未明确绑定代码和软件环境 | Accept | FR-001 R7 要求绑定 protocol、配置、代码、软件、输入、输出、schema、计数和哈希 | 在 Sprint 验收和实现任务中加入 Git/代码身份与软件环境记录，沿用 M1-01 manifest schema 约束，不把依赖哈希误写成唯一允许形式 |
| 2 | High | Risk | Kimi H2; GLM L-2 | Golden authority 和预注册容差来源未明确 | Accept | `sprint-m1-01.md` §5.1 与 `tests/golden/test_refactor_characterization.py` 已冻结同平台 exact 和 `rtol=atol=1e-12` 分类 | 在 §5.1 显式引用已有 authority 和常量，禁止本 Sprint 重定义或观察结果后放宽 |
| 3 | High | Requirement | GLM H-1 | Development/test 输出的精确 schema 和行归属未固定 | Accept | 设计 §8.3 要求只改变存储边界、不改变 split 归属或行内容；旧 MC 行还保留 `runNumber`、原始/官方 normalization 审计值、`label`、`split`、两类权重、identity 和 `m4l` | 固定两份 CSV 的有序 schema 为 19 项特征，再加 `m4l`、`label`、`split`、`physical_weight`、`train_weight`、`channelNumber`、`eventNumber`、`runNumber`、`mcWeight`、`xsec`、`kfac`、`filteff`、`sum_of_weights`，并明确 development=train+validation、test=test bucket |
| 4 | High | Correctness | Kimi H3 | 要求从发布 CSV 删除 `m4l`、identifier、weight 等 forbidden columns | Partial | AGENTS/FR 禁止这些字段成为模型特征，不禁止其作为 metadata；M1-03 的 KS/权重和 M1-04 identity 校验需要它们 | 增加精确 header 与模型特征 allowlist/forbidden-feature 测试；不从 CSV 删除必要 metadata |
| 5 | High | Test | GLM H-2 | M1-01 延后的 ROOT 输入替换检测在 M1-02 未落项 | Accept | 设计 §8.1/§11 要求读取前后验证常规文件状态与内容记录；protocol 要求 regular-file、no-symlink、SHA-256 | 增加读取前 stat/SHA-256、读取后复验、manifest 记录，以及 mid-run replacement、symlink、非普通文件拒绝测试 |
| 6 | Medium | Requirement | Kimi M1; GLM I-2 | CLI 未明确覆盖真实数据输入拒绝 | Accept | FR-001 R2 不定义真实数据输入类型，protocol 只允许 345060/363490 | 除 pipeline 负例外增加 CLI fail-closed 用例，确保在 ROOT 内容处理前拒绝不在协议中的真实数据/DSID 配置 |
| 7 | Medium | Consistency | Kimi M2 | Domain 与 preprocessing 对 stable split 的职责不清 | Accept | 哈希 split 是纯 deterministic domain 行为，但 protocol 解释、逐行应用、分文件发布和 manifest 属于 preprocessing | 在计划中固定 `src/domain/` 负责纯 split 函数，`src/preprocessing/` 负责按 protocol 调用、分区和记录 authority |
| 8 | Medium | Maintainability | Kimi M3 | 暂留旧文件可能让新主链误导入真实数据或通用 predict | Accept | M1-05 才删除历史文件，但 FR-001 要求新入口从 M1-02 起没有真实数据输入面 | 增加新入口 import graph/模块 allowlist 测试，拒绝向旧 real-data、plotting、generic-predict 路径的依赖 |
| 9 | Medium | Verification | GLM M-1 | 完整 suite 已有 211 个历史失败，字面全绿门不可执行 | Accept | M1-01 已记录 `776 passed, 211 failed, 2 skipped`，失败来自 Windows/POSIX、symlink 权限和缺冻结 run | 在 §7 预注册 M1-02 门：专项必须全绿；完整 suite 不得新增失败、扩大失败集合或出现 M1-02 归因失败；M1-05/M1-06 再收敛到全绿 |
| 10 | Medium | Documentation | GLM M-2 | 权威 ROOT count/cutflow 等价未安排也未声明缺失门 | Accept | 设计阶段 3 要求三类证据，但本 worktree 没有权威 ROOT/冻结 run；FR 允许 fixture-only 完成但不得冒充权威复现 | 在风险和交付中列出 345060/363490 冻结参考计数及未执行边界，禁止读取真实数据或既有冻结 run 补证 |
| 11 | Medium | Test | GLM M-3 | 微型 ROOT fixture 和 CLI smoke 不够具体 | Accept | 两个 profile 分别使用 `analysis`/GeV 与 `mini`/MeV，且需要覆盖两个 DSID、质量分支、三种 split 和 identity | 增加 fixture builder 任务与覆盖矩阵；专项测试直接执行 CLI application service/console 入口并断言输出，不依赖仓库内持久 fixture 或真实 ROOT |
| 12 | Medium | Test | GLM M-4 | `-k` 过滤依赖未来测试命名，可能静默漏测 | Accept | M1-01 已采用显式测试路径避免收集歧义 | 将 §7 改为 M1-02 新测试文件的显式列表，文件创建后按实际等价路径更新，不使用宽泛 `-k` 作为唯一门 |
| 13 | Low | Correctness | Kimi L1 | 双文件“原子发布”的失败语义不明确 | Accept | M1-01 `ArtifactTransaction` 已规定 staging、no-clobber、失败 receipt 和 publish 终态 | 明确所有文件、双重哈希和 manifest 在 staging 完成后整体 promote；失败只保留 failure receipt，不发布部分成功 manifest |
| 14 | Low | Documentation | Kimi L2; GLM L-1 | §10 缺少评审、验证和提交证据清单 | Accept | FR-001 与 Sprint workflow 要求每 Sprint 四类证据闭环 | 预填文档评审、代码评审、验证、环境/边界和 commit 索引小节，交付时填实际值 |
| 15 | Info | Traceability | Kimi Info | 前置依赖没有批准设计的可点击相对链接 | Accept | 批准设计是 FR 和 Sprint 的控制性来源 | 在 §2 添加设计文件相对链接 |
| 16 | Low | Consistency | GLM L-3 | 未说明 preprocessing protocol v1 是沿用还是扩展 | Accept | M1-01 已冻结 v1；输出布局由批准设计 §8.3 规定，不需要静默改变科学 protocol | 声明本 Sprint byte-for-byte 消费 v1，不增改其内容；输出 schema 在代码和测试中固定，未来 protocol 变更必须升版 |
| 17 | Info | Process | GLM I-3 | M1-02 plan 与证据必须进入本 Sprint commit | Accept | 当前 plan 未跟踪，per-Sprint commit 是 FR-001 证据链的一部分 | 在 §10 commit 清单中明确只 stage M1-02 plan/reviews/implementation，保留 M1-03～M1-06 未跟踪 |

## Needs Immediate Action

- 应用 1-17 的文档修订；其中第 4 项按 metadata/model-feature 边界部分接受。
- 完成精确 schema、输入读取前后绑定、split ownership、原子发布与 fixture/CLI 证据。
- 预注册完整 suite 的历史失败边界，并声明权威 ROOT 验证未执行。

## Can Be Deferred

- 权威 345060/363490 ROOT 的事件数与 cutflow 复现只能在具备对应输入且另有授权的环境执行；
  本 Sprint 不读取工作区真实 ROOT、真实数据或既有冻结 run。
- 历史执行面物理删除由 M1-05 完成；M1-02 先用 import/CLI 边界证明新主链不依赖它。

## Final Status

文档在上述修订落地后接受，可自动进入 Sprint M1-02 实施，无需再次人工确认。
