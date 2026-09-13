# H4l 软件需求

科学数值与角色边界由 `config/protocols/` 中的版本化协议定义。本文件记录长期有效的软件约束。

| ID | 要求 | 当前状态 |
|---|---|---|
| DATA-01 | 所有产品路径必须 MC-only，拒绝真实数据和无法绑定的数据成员。 | 已实现 |
| DATA-02 | 调用必须显式选择受控 dataset；不同 release 不得重标记、混训或共享反馈。 | 已实现 |
| DATA-03 | 输入必须绑定文件身份、字节摘要、profile、协议和上游 artifact。 | 已实现 |
| DATA-04 | 同一物理 `event_group_id` 不得跨角色、split 或 fold。 | 已实现 |
| SAFE-01 | `m4l` 只能按 H4l 协议的共同条件规则使用；身份、来源、角色和权重字段不得进入模型输入。 | 已实现 |
| SAFE-02 | Assessment 在冻结前不可读，且不得用于模型、阈值、分箱、映射或协议调整。 | 已实现 |
| SAFE-03 | 完成、失败和诊断 run 均不可覆盖；重复 assessment 受协议预算约束。 | 已实现 |
| API-01 | 唯一 package 为 `higgsml`，唯一 console entry 为 `higgsml`。 | 已实现 |
| API-02 | CLI 只负责适配；科学逻辑由可测试的服务实现。 | 已实现 |
| API-03 | YAML/JSON 严格拒绝未知、缺失、重复和错误类型字段。 | 已实现 |
| PHY-01 | 数据准备必须执行协议绑定的 H4l 重建、选择、表示与权重计算。 | 已实现；完整 MC 审计待完成 |
| PHY-02 | 支持 mass-only、decay7、engineered19、lab-extension 和显式矩阵元表示。 | 已实现 |
| MODEL-01 | 候选、结构、损失、随机种子、checkpoint 与诊断必须进入协议或产物绑定。 | 已实现 |
| CAL-01 | 条件 CDF 的总体、权重语义、网格、ties 和映射身份必须冻结。 | 已实现 |
| INF-01 | 模板记录 signed yield、sumw2、事件组统计、modifier 和共同分箱。 | 已实现 |
| INF-02 | 推断记录 likelihood、区间、注入点、随机种子、预算和失败状态。 | 已实现 |
| ART-01 | 阶段采用 staging、原子发布和 manifest-last，成功与失败证据互斥。 | 已实现 |
| ART-02 | Artifact 记录配置、dataset、协议、lineage、SHA-256、软件和平台。 | 已实现 |
| QA-01 | 合成测试覆盖角色隔离、绑定、事务、拒绝路径和数值契约。 | 已实现 |
| QA-02 | 软件、合成、完整 MC、外部参考和 authority 证据必须分别报告。 | 长期要求 |
| QA-03 | 外部 MELA、似然覆盖与原生 ARM64 必须有独立证据后才支持科学结论。 | 尚待外部/完整验证 |

所有未完成科学验证的输出只能描述为 educational/technical workflow。
