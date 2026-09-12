# Sprint M1-01 代码评审（gpt-5.6-sol）

评审范围：`src/research/sample_efficiency_protocol.py`、`config/research_sample_efficiency_protocol_v1.json`、`tests/research/test_sample_efficiency_protocol.py`、`tests/research/test_sample_efficiency_characterization.py`，并对照 FR-SE-01 的规范字段表和 `docs/sw-dev/artifact-schema.md` §7。范围仅限 M1 纯元数据契约；M2 事件子集执行、M5/M6 统计执行器、run/manifest receipt 验证和科学预注册均为明确延后项。

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Info | Correctness | **F-00** — `sample_efficiency_protocol.py` 全文件及对应测试/模板 | 未发现需要修改的当前范围缺陷。实现对 freeze 和 overlay 执行严格根键及嵌套键校验，拒绝 bool 伪数值、非有限值、无序/重复列表和未知算法；重算 base/freeze digest、registry candidate、表示列表及 noninferiority margin/source；区分 manifest artifact ID 与 payload SHA；缺 freeze 按 FR 抛出 `ResearchError(status="compact_candidate_not_frozen")`，其 `exit_code` 为 3。模板把未批准科学值保留为必填 `null` 并由普通 loader 拒绝，且模块没有事件读取、claim、run 发布或统计执行路径。 | `test_sample_efficiency_protocol.py` 覆盖 defensive copy、canonical digest、所有对象层级的缺失/未知字段、重复 JSON key、schema/binding/seed/control/candidate 篡改、模板拒绝和明确错误语义；`test_sample_efficiency_characterization.py` 固定旧协议 digest、旧 candidate key、参数量及 train-only 拟合/完整 validation 行为。主任务提供的验证结果为 focused 156 passed、full 644 passed（332.23s）及 `pip check` clean。 | 当前 M1 实现可进入 review-confirm。后续实现 M2/M5/M6 时，应按既定边界另行评审 receipt trust-chain、population independence、统计估计量和 runtime 状态发布；本评审结果不覆盖这些延后能力，也不构成 ARM64 authority 或 scientific numerical validation。 |

评审限制：本次为静态、边界化复核；没有重复运行主任务已经完成的测试，也没有读取事件数据或执行任何实验。图索引尚未包含新模块，因此新文件以直接源码读取为准。
