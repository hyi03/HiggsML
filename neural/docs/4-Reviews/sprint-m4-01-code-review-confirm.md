# Sprint M4-01 代码评审确认

## 输入与结论

- 实现目标：[FR-SE-04](../1-Requirement/Done/FR-SE-04-learning-curve-batch-workflow.md)、[sprint-m4-01](../3-Plan/Done/sprint-m4-01.md)
- 评审输入：[gpt-5.5](sprint-m4-01-code-review-by-gpt-5.5.md)、[gpt-5.6-sol](sprint-m4-01-code-review-by-gpt-5.6-sol.md)
- 结论：两份评审独立确认了 cell 状态机、gate/T1 schema 和 clean 删除边界的缺口。以下接受项必须在 M4 提交前完成；失败控制器采用 M4 范围内的 stage failure evidence，资源字段按 reference executor 的真实生效范围收窄。

| 严重度 | 类型 | 评审意见 | 决定 | 依据 | 本 Sprint 处理 |
|---|---|---|---|---|---|
| High | Evidence integrity | gpt-5.6-sol #1：T1/G1 只做常量字段检查，未执行正式 exact schema 与 protocol/dataset 绑定。 | Accept | FR §8、§14、§16 要求 receipt-bound 且严格验证的 gate evidence。 | 使用正式 T1 schema并检查 dataset、protocol digest、独立验证；为 G1 定义精确 schema；在任何 run 输出前失败。 |
| High | State machine | gpt-5.6-sol #2：complete/terminal ledger 可被自洽重签为不可能状态。 | Accept | ledger 是 M5 的唯一批次消费入口，必须由已验证 stage 链推导唯一 outcome。 | 集中实现完整 stage matrix；固定 complete 的 status/grid/reason，并按 terminal stage拒绝后续 artifact、要求成功前缀。 |
| High | Clean safety | gpt-5.6-sol #3：CLI 可把任意 output root 当删除授权根，且存在路径替换窗口。 | Accept | FR §12 将生产删除范围固定在 `neural/runs`，并要求 Windows reparse 安全。 | CLI 固定 `PROJECT_ROOT/runs`；helper 要求规范化直接子目录，逐组件拒绝 reparse；删除前原子重命名到受控 quarantine 后复验再删除。 |
| High | Test authenticity | gpt-5.6-sol #4：tamper 测试仅命中 receipt，未覆盖 semantic reader。 | Accept | 测试必须证明 reader 拒绝 receipt 自洽重签攻击。 | 增加重签 helper，覆盖状态矩阵、grid、gate/T1、duplicate key、plan-only、clean 和 assessment poison。 |
| Medium | Strict JSON | gpt-5.6-sol #5：共享 JSON reader 接受重复 key。 | Accept | FR §16 明确要求 strict schema；last-wins 会隐藏非规范载荷。 | 在 artifact JSON ingress 统一拒绝任意层级重复 key 与非有限常量，并加重签负例。 |
| Medium | Common grid | gpt-5.6-sol #6：reader 未重放 `initial_mass_edges` 与规范 `reason`。 | Accept | common-grid payload 必须可由 sealed plan 与参与者 calibration 完整重算。 | 校验全部字段、有限值、初始边界及 status 对应 reason。 |
| Medium | Failure audit | gpt-5.6-sol #7：grid 构建异常可能发生在 ResearchRun 事务外。 | Partial | M4 要保留 binding/unknown failure evidence，但完整跨 Sprint controller 不在本 Sprint 范围。 | 将 frame 构建与共同网格算法纳入 grid stage transaction并发布失败 manifest；batch reader仍仅接受完整 batch。 |
| Low | Config | gpt-5.6-sol #8：示例引用不存在的 validated T1 文件。 | Accept | 可复制示例不应伪装仓库存在有效科学授权。 | 改为明确占位路径并说明 pending evidence不能执行 T1。 |
| High | Correctness | gpt-5.5 #1：scientific-terminal 可携带后续 artifact，complete 可缺 grid ID。 | Accept | 与 gpt-5.6-sol #2 独立一致。 | 由 terminal stage 推导 artifact存在矩阵、blocked stages、grid时机与规范 outcome。 |
| Medium | Identity | gpt-5.5 #2：`progress` 被绑定进 execution plan ID。 | Accept | 进度显示不改变输出、资源或科学计划。 | 从 canonical plan及 execution ID preimage 移除；CLI 本地保留选项并测试 ID 稳定。 |
| Medium | Clean safety | gpt-5.5 #3：helper 未自行证明 resolved target 是 allowed root 的直接子目录。 | Accept | 删除 helper 应在自身边界完成路径证明。 | 拒绝 `..`、root自身、非直接子目录和解析后越界；对实际删除路径重复验证。 |
| Medium | Gate schema | gpt-5.5 #4：T1/G1 缺 exact keys 与完整形态检查。 | Accept | 与 gpt-5.6-sol #1 独立一致。 | 使用版本化 schema与精确键集合，拒绝未知/缺失/不匹配字段。 |
| Medium | Test | gpt-5.5 #5：缺 plan-only 零写入、clean 与语义重签测试。 | Accept | 这些均是已确认 M4 AC 的直接证据。 | 补 targeted tests，并保留真实 30-cell synthetic E2E。 |
| Low | Resources | gpt-5.5 #6：未使用资源字段仍改变 execution identity。 | Accept | execution identity 只应覆盖 reference executor 实际生效资源。 | M4 资源 schema 收窄为 `workers=1`；移除未传递参数并更新示例/文档/测试。 |

## 执行状态

当前阶段：`completed`。接受与部分接受项已落实；focused 45 passed/68 warnings，`pip check`通过，全量680 passed/122 warnings。Windows synthetic未运行ARM64 authority、完整ROOT或科学数值验证。
