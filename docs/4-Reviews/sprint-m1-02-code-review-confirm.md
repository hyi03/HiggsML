# Sprint M1-02 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-02-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-02-code-review-by-opencode-go-glm-5.2.md`
- `neural/docs/preprocess-protocol-v1.md`
- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- `neural/docs/sprint-m1-02.md`
- 当前 M1-02 实现与测试变更

**Review Date**

- 2026-09-01

## Overall Conclusion

两份评审的主要结论有代码、协议和 synthetic probe 支撑。当前实现的领域公式、MC-only
边界、canonical serialization 与 transaction 基础结构可保留，但尚不能按原样接受：协议
密封、坏输入 fail-closed、artifact schema、failure receipt、ROOT 资源释放、权威 gate runner
与协议 §9 测试覆盖均需在 M1-02 内修订。

以下决定不授权读取真实数据、held-out test 或执行 `open-test`。权威 full-data gate 仍只能在
锁定的原生 `osx-arm64` 环境执行；本机修订完成后仍必须记录
`authoritative_gate_not_run`，不得宣称全量等价已证明。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Correctness | `Kimi K-01` | loader 未密封 branch、29 列、split、serialization、ZZ normalization 与 sliding-Z2 | Accept | 协议 §1 要求 YAML 完整转录且漂移 fail closed；mutation probe 已证明多项篡改可被接受 | 在 YAML 补齐冻结字段，并在 `load_preprocess_protocol` 对全部冻结结构和值 exact 校验；加入逐字段 mutation tests。 |
| 2 | High | Requirement | `Kimi K-02` | manifest 缺少 `counts.per_sample`、`schema.dtypes`、`software.packages` | Accept | 协议 §8.3 明确要求这些字段；success-path probe 证明当前缺失 | 补齐 manifest schema，并以已安装的项目依赖版本生成稳定 `packages` 映射。 |
| 3 | Medium | Requirement | `Kimi K-03` | `mc_summary.identity` 缺少 legacy duplicate 元数据 | Partial | 字段确为 §8.2 必需，但把权威常量 `2/4` 无条件写入 synthetic run 会制造错误证据 | 从当前 selected 表按 legacy 三元组计算 `legacy_duplicate_groups/rows`；权威 runner 再 exact 断言 `2/4`。 |
| 4 | Medium | Audit | `Kimi K-04` | failure receipt 只在异常自带 exit code 时记录 code/time | Accept | `RunPathError` 与 `RuntimeError` probe 均缺 `exit_code`、`failed_at_utc`，违反 §8.3 | transaction 对所有失败写时间，并按异常映射 3/4/70；同步覆盖 publish failure。 |
| 5 | Medium | Correctness | `Kimi K-05` | split 算法硬编码且未与 YAML 密封 | Accept | `splitting.py` 与 YAML 可独立漂移 | 保留简单的冻结实现，但 loader 必须 exact 验证 split block，并用 literal vectors 固定行为。 |
| 6 | Medium | Requirement | `Kimi K-06` | YAML 缺 sliding-Z2 冻结参数 | Accept | 协议 §3.2 明确要求保存但 v1 不启用 | 增加 `min_mode=fixed` 和五个 sliding 字段，loader exact 校验，cutflow 从协议读取 `min_mode`。 |
| 7 | Medium | Test | `Kimi K-07` | selection、Angular5、ROOT rejection、split、serialization、publication 测试不足 | Accept | 协议 §9 将这些列为必须覆盖，现有 32 tests 未覆盖大部分边界 | 增加 synthetic-only 参数化单元/集成测试，覆盖 §9 明列的边界与失败路径。 |
| 8 | Low | Correctness | `Kimi K-08` | CSV string token 可能被自动 quoting | Accept | 协议 §6.3 要求 enum-only 且禁止特殊字符；当前 writer 未验证 enum | 在 serialization 前 exact 校验 `split/source_sample` 枚举与 CSV 安全字符；保留 `csv.writer` 作为确定性编码器。 |
| 9 | Low | Maintainability | `Kimi K-09` | CLI allowed root 绑定源码目录，wheel 安装时错误 | Accept | console script 可从非 editable 安装运行，`__file__` 不代表工作项目 | 将默认 allowed root 定义为 `Path.cwd()/runs`；CLI 仍不提供科学或 run-root override。 |
| 10 | Low | Maintainability | `Kimi K-10` | `SelectionConfig.v1()` 重复冻结阈值 | Accept | production 已从 protocol 构造配置，`v1()` 仅给测试造成第二份常量 | 删除 production `v1()`；测试通过已加载 protocol 或局部 helper 构造。 |
| 11 | Low | Requirement | `Kimi K-11` | `peak_memory_bytes` 恒为 null | Partial | §8.3 要求字段且 Sprint 要记录峰值；但 `tracemalloc` 不是进程 RSS，不能冒充权威峰值 | 增加跨平台进程峰值 RSS helper，无法测量时 fail closed 或明确不发布成功 manifest；为 helper 加测试。 |
| 12 | Info | Safety | `Kimi K-12` | 无 `xgboost/src` runtime 依赖且保持 MC-only | Accept | package-contract tests 与代码检查支持该结论 | 保持现有边界，并在新增 gate runner 中仅以只读 artifact locator 使用 legacy 路径。 |
| 13 | Info | Verification | `Kimi K-13` | 缺外部 artifact 时正确记录 authority gate 未运行 | Accept | golden test 使用 `authoritative_gate_not_run` skip；本机无批准表 | 保持此状态，禁止把 Windows/synthetic 结果替代 ARM64 gate。 |
| 14 | Info | Test | `Kimi K-14` | 当前 synthetic suite 为 32 passed, 1 skipped | Accept | 两位 reviewer 独立得到相同结果 | 修订后重新运行 focused/full suite；旧结果只作为修订前基线。 |
| 15 | High | Correctness | `GLM F-01` | 非有限 lepton 数值被静默转成 selection drop | Accept | 协议 §1、§3.2 要求非有限值 exit 3；probe 已复现 NaN/inf 被丢行 | 在任何 stage 比较前验证所有数值字段有限，异常统一转 `InputBindingError`；加入 NaN/inf tests。 |
| 16 | High | Correctness | `GLM F-02` | `lep_n`/数组长度/缺字段被当作 allowed-type drop | Accept | 协议 §2.3 明确 array shape/schema mismatch 必须失败 | 新增 event schema validator，缺字段、非整数 `lep_n`、长度不一致均 raise `InputBindingError`。 |
| 17 | High | Requirement | `GLM F-03` | protocol loader 对 luminosity、列序、branch、normalization、split、serialization、golden path 绑定不全 | Accept | 七个 mutation probe 均加载成功，直接违反冻结协议 | 与第 1 项合并实施 exact sealed contract，并增加 forbidden legacy-column assertions。 |
| 18 | High | Requirement | `GLM F-04` | summary 缺 legacy duplicate facts | Accept | 协议 §5.2/§8.2/§7.2 均要求记录并 gate | 按第 3 项动态计算；synthetic duplicate fixture 与 authority expected `2/4` 分开验证。 |
| 19 | High | Requirement | `GLM F-05` | 无可执行 authoritative gate runner | Accept | 当前 golden test 只校验 table hash，未验证 lineage、谓词、counts/cutflow | 实现只读 `osx-arm64` gate 模块：先验证五个批准 lineage hash，再执行 exact/float 比较并输出证据；非权威环境只能明确 skip/refuse。 |
| 20 | High | Test | `GLM F-06` | tests 未覆盖协议 §9 大量边界和 publication success path | Accept | 评审枚举与现有 tests 对照属实 | 补足 selection 边界、pairing tie、Angular5 退化、split literal、run-level determinism、manifest-last 等 synthetic tests。 |
| 21 | Medium | Audit | `GLM F-07` | 非 binding 异常 failure receipt 缺 code/time | Accept | 与第 4 项相同结论但 probe 覆盖 4/70 两条路径 | 合并实施并新增 transaction unit tests。 |
| 22 | Medium | Consistency | `GLM F-08` | split/serialization/normalization 字段为 dead config | Partial | 科学行为可由代码固定；风险来自 YAML 未校验，不要求运行时动态解释 YAML | loader exact 校验这些字段；runtime 继续使用小型固定实现，测试证明实现与 sealed literals 等价。 |
| 23 | Medium | Requirement | `GLM F-09` | manifest 缺 dtypes/per-sample/packages，峰值为空 | Accept | 与第 2、11 项证据一致 | 合并补齐 schema、counts、packages 与真实 peak RSS。 |
| 24 | Medium | Consistency | `GLM F-10` | YAML 缺 sliding-Z2、entry counts、lineage chain | Accept | 均为协议 §2.1、§3.2、§7.1 冻结内容 | 全部转录并密封；reader 完整读取后 exact 校验 expected entry count。 |
| 25 | Medium | Test | `GLM F-11` | ROOT missing/extra/source_entry/channel mismatch/read error 无测试 | Accept | reader 有 fail-closed 分支但现有 suite 未覆盖 | 用 runtime-generated micro-ROOT 分别覆盖每条 rejection，断言 `InputBindingError`/exit 3。 |
| 26 | Low | Maintainability | `GLM F-12` | CLI allowed root 假设 repo editable checkout | Accept | 与第 9 项一致 | 合并改为当前工作目录下 `runs/`，并加入 cwd 行为测试。 |
| 27 | Low | Maintainability | `GLM F-13` | uproot handle 未关闭导致 Windows 文件锁 | Accept | reviewer 的 temp cleanup 已实际触发 `PermissionError` | 用 context manager/finally 确保 generator 完成、异常或 close 时都释放 ROOT handle；加文件可删除测试。 |
| 28 | Low | Maintainability | `GLM F-14` | CLI 吞掉 unexpected traceback | Accept | `configure_logging()` 后 catch 分支没有 logging | 对 3/4 记录简明错误，对 70 使用 `logger.exception`；不向 stdout 泄漏数据内容。 |
| 29 | Low | Correctness | `GLM F-15` | scientific invariant 使用可被 `-O` 移除的 assert | Accept | `features.py` 的 pairing assert 在 optimized mode 失效 | 改为显式 `InputBindingError`，并加无 pairing indices 单元测试。 |
| 30 | Low | Maintainability | `GLM F-16` | integration test 有未使用的 `replace` import | Accept | 文件中无调用 | 删除 import。 |
| 31 | Low | Requirement | `GLM F-17` | 零 selected sample 会失败但协议未说明 | Partial | 两个绑定 full samples 的 approved counts 均非零，继续发布空样本会掩盖截断/规则错误 | 保留 fail-closed，并在协议/YAML 完整 entry-count 与 authority count 约束中明确 bound sample 不得空。 |
| 32 | Low | Performance | `GLM F-18` | scalar pipeline 估算 full run 约 54 分钟 | Reject | Sprint 没有性能 SLO；评审也确认一次性 authority run 可接受，向量化会扩大科学等价风险 | M1-02 不做向量化；权威 run 记录 wall/peak 后若实际不满足运维需要，再单独设计优化。 |
| 33 | Info | Risk | `GLM F-19` | read-stage efficiency convention 未在协议钉死 | Accept | §8.1 只列字段，gate 会比较浮点；当前空样本已被拒绝，因此 read efficiency 应恒 1.0 | 在协议与 cutflow test 明确非空绑定样本 read-stage `efficiency_previous/read=1.0`。 |
| 34 | Info | Risk | `GLM F-20` | strict extra-branch rejection 只能在 authority inputs 验证 | Accept | 这是协议 §2.3 明确 fail-closed 规则，不是实现缺陷 | 保持 strict 行为；用 synthetic extra-branch test 验证机制，真实 profile 只留给 ARM64 gate。 |
| 35 | Info | Documentation | `GLM F-21` | README/FR/Sprint/design 与实现边界一致 | Accept | 文档明确 golden、run-config、artifact 和 not-run 状态 | 修订后只更新实际完成证据，不改变安全边界。 |
| 36 | Info | Test | `GLM F-22` | `"data" not in ...` 是弱 MC-only 断言 | Accept | substring 不能证明 enum/schema 契约 | 改为 exact source_sample/label 集合，并断言五个 legacy normalization columns 不存在。 |
| 37 | Info | Test | `GLM F-23` | golden 缺失时 skip 行为正确 | Accept | 当前 skip 原因精确为 `authoritative_gate_not_run` | 保持，并由新 gate runner 增加 platform/lineage refusal tests。 |

## Needs Immediate Action

- 完整密封 YAML 与 loader：samples/branches/counts、selection/sliding-Z2、normalization、split、
  serialization、29 列、golden lineage/paths/tolerances。
- 坏 event schema 与非有限输入一律 exit 3，不得伪装为 selection drop。
- 补齐 summary/manifest/failure receipt schema、真实 peak RSS 与 ROOT handle 生命周期。
- 实现锁定 `osx-arm64` authoritative gate runner，但本机只验证 refusal/skip 和 synthetic
  comparator，不执行 full-data gate。
- 补足协议 §9 的 synthetic-only 单元、集成、transaction、publication 和 golden comparator
  tests。

## Can Be Deferred

- `GLM F-18` 的 vectorization/performance 优化不阻塞 M1-02。
- 实际 full-data gate 运行、wall/peak 证据与全量等价结论必须等待批准 artifact 和锁定原生
  `osx-arm64` 环境；本 Sprint 的本机提交只能交付可执行 gate 与未运行状态。

## Final Status

**Changes required before acceptance.** 最小剩余工作是完成所有 Accept 项与高优先级 Partial
项，重跑 focused/full verification，并继续明确记录 `authoritative_gate_not_run`。只有确认项
修订和验证均通过后，M1-02 才可独立提交；此前不得开始 M1-03。
