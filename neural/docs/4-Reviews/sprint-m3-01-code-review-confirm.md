# Sprint M3-01 代码评审确认

## 输入与结论

- 实现目标：[FR-SE-03](../1-Requirement/Done/FR-SE-03-subset-bound-discriminant-v2.md)、[sprint-m3-01](../3-Plan/Done/sprint-m3-01.md)
- 评审输入：[gpt-5.5](sprint-m3-01-code-review-by-gpt-5.5.md)、[gpt-5.6-sol](sprint-m3-01-code-review-by-gpt-5.6-sol.md)
- 结论：两份评审确认了可信对象边界、下游直接来源、严格 schema、assessment 前置关闭和对抗测试的实质缺口。以下接受或部分接受项必须在 M3 提交前完成；部分建议涉及 M4 publisher 或 M6 功能的部分仍按既定 Sprint 边界延期。

| 严重度 | 类型 | 评审意见 | 决定 | 依据 | 本 Sprint 处理 |
|---|---|---|---|---|---|
| High | Security | gpt-5.5 #1：校准 frame 未证明来自 lineage 绑定的 prepared run。 | Accept | FR §5、§12—13 要求 receipt-backed 来源和直接上游验证。 | 校准入口改为接收 verified prepared run 与 `LoadedSubsetDiscriminant`，内部重验 receipt、artifact/population 后加载 calibration role；增加跨 prepared 替换测试。 |
| High | Security | gpt-5.5 #2：手工 template 可直接绑定 lineage。 | Accept | FR §13 要求 template 从直接可信 calibration 上游生成，普通 dict 不能升级为可信 artifact。 | 新增由 verified prepared run、可信 model handle 和已验证 calibration bundle内部构建 template 的入口；普通手工 template 绑定拒绝。 |
| High | Security | gpt-5.5 #3：裸 v2 dict 可在缺少 selection/base/overlay 时重签表示字段并预测。 | Accept | FR §7、§10—11 要求 reader 重算语义，自签 dict 不具 run provenance。 | `predict_discriminant()` 拒绝裸 v2；新增仅接受 `LoadedSubsetDiscriminant` 的预测入口并重验 handle/model。 |
| Medium | Correctness | gpt-5.5 #4：calibration 缺少覆盖 lineage 和内容的 digest。 | Accept | FR §13 明确要求 mapping/threshold/template/result digest 覆盖 lineage。 | 增加严格 calibration schema、`calibration_id` 与验证器；template 构建前验证完整 calibration。 |
| Medium | Security | gpt-5.5 #5：带 lineage template 可省略 expected lineage 进入 legacy Asimov。 | Accept | FR §14 只允许 v2 raw/model-self 且必须传播 lineage。 | `run_asimov()` 对含 lineage template 强制可信 expected handle/lineage，遗漏时在 `build_model` 前失败。 |
| Medium | Compatibility | gpt-5.5 #6：`history_contract` 是否必需由 payload 自己决定。 | Accept | FR §8 要求按 base protocol 条件决定。 | validator 按 base diagnostics 条件精确要求/禁止字段并检查结构。 |
| Low | Test | gpt-5.5 #7：缺跨 prepared、手工 template、重签表示攻击测试。 | Accept | 三项均直接覆盖已确认的高风险边界。 | 增加 receipt 自洽的负例，并断言统一状态。 |
| High | Security | gpt-5.6-sol F-01：`ExperimentLineage` 可由普通 dict 构造，无法作为可信 capability。 | Accept | FR §12 明确限定只能由 verified model-run reader 构造。 | 构造函数使用模块私有 mint token；publisher 发布后调用完整 reader；下游接收 verified model handle并逐字段匹配。 |
| High | Security | gpt-5.6-sol F-02：v2 可进入 assessment/mismatch，且 Asimov 可绕过 lineage。 | Partial | Asimov 绕过和现有 assessment/toy 入口前置关闭属于 M3；实现 capacity/CDF/claim confirmation 属 M6。 | 对含 sample-efficiency lineage 的 `run_asimov`、`run_toys`、assessment ingress 在模型构建、mother decode、RNG/claim前拒绝非 model-self；不实现 M6 科学功能。 |
| High | Security | gpt-5.6-sol F-03：calibration 内容未被外层 digest覆盖，template 不验证直接上游。 | Accept | 与 gpt-5.5 #2/#4 独立论证一致。 | 严格验证 calibration keys、model/threshold/lineage/digest；template 只从可信 calibration 和 prepared template role计算。 |
| High | Correctness | gpt-5.6-sol F-04：reader 未验证 seed grid、fraction grid与条件字段。 | Accept | FR §8—10 要求协议成员关系和条件 schema 均可重算。 | 校验 fraction 范围及 overlay 网格、network seed集合、base条件 `history_contract`，补 receipt 自洽重签测试。 |
| Medium | Security | gpt-5.6-sol F-05：upstream 被转成 set，忽略 path及重复项。 | Accept | FR §7 要求三条 upstream 路径与集合精确绑定。 | 按 manifest 顺序无关但 multiplicity 敏感地验证恰好三项，并比较规范路径、stage、artifact ID。 |
| Medium | Correctness | gpt-5.6-sol F-06：malformed输入泄漏原生异常或在计算后才失败。 | Accept | FR §15 要求统一 `training_subset_binding_mismatch` 且在训练/计算前失败。 | 为 M3 public ingress 增加精确类型/键检查，先验证可信 handle和stage，再访问 payload；对 schema 错误统一包装。 |
| Medium | Test | gpt-5.6-sol F-07：关键自洽重签与前置失败路径缺覆盖。 | Partial | 评审列出的 seed/upstream/schema/downstream攻击属于 M3；完整 capacity、CDF、claim 测试属于 M6。 | 增加 M3 范围内自洽重签、伪造 capability、下游 digest、assessment/toy前置拒绝测试；M6 项保留在 FR-SE-06。 |

## 执行状态

当前阶段：`completed`。接受与部分接受项已落实；Windows synthetic focused 51 passed/7 warnings，`pip check`通过，全量673 passed/61 warnings。ARM64 authority、完整 ROOT 与科学数值验证未运行。
