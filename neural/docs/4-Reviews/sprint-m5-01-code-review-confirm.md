# Sprint M5-01 代码评审确认

## 输入与结论

- 实现目标：[FR-SE-05](../1-Requirement/Done/FR-SE-05-paired-aggregation-reporting.md)、[sprint-m5-01](../3-Plan/Done/sprint-m5-01.md)
- 评审输入：[gpt-5.5](sprint-m5-01-code-review-by-gpt-5.5.md)、[gpt-5.6-sol](sprint-m5-01-code-review-by-gpt-5.6-sol.md)
- 结论：两份评审确认初版happy path可运行，但terminal、exact schema、误差层及人类输出认证仍有缺口。以下全部接受项在提交前完成。

| 严重度 | 来源 | 意见 | 决定 | 本Sprint处理 |
|---|---|---|---|---|
| High | 5.5 #1 | `load_training_subset`拒绝M2 terminal，报告无法保留合法终态。 | Accept | 以完整M2 plan summary查actual count，只对planned/model调用selection reader；增加terminal聚合测试。 |
| High | 5.5 #2 | PNG metadata未与plot spec核对。 | Accept | reader读取PNG metadata并比对plot-spec ID；增加自洽重签替换测试。 |
| High | sol #1 | bootstrap/curve nested payload偏离合同且无validator。 | Accept | 实现contract/record/summary/nested exact validator；拆分protocol method与AUC algorithm，修正计数字段。 |
| High | sol #2 | baseline inference重复读取且未核对ledger ID。 | Accept | 从M4 resolved path一次读取、核对并缓存全部complete inference/W68；配对只用缓存。 |
| High | sol #3 / 5.5 #5 | PNG/CSV/Markdown缺完整误差、series、失败与Q*语义。 | Accept | plot spec绑定series/points/断线/误差；CSV扩充固定列；Markdown加入完整性、失败表、逐层状态和Q*来源。 |
| High | sol #4 | 测试未证明关键统计/安全矩阵。 | Accept | 增加golden统计、terminal、重签、extra file、PNG、CLI路径与具体status断言。 |
| Medium | 5.5 #3 | report接受额外文件。 | Accept | manifest files要求protocol加固定六文件精确集合。 |
| Medium | 5.5 #4 | curve evaluation缺requested/valid/plan ID。 | Accept | curve row evaluation对象显式携带三项并严格验证。 |
| Medium | sol #5 | network单draw状态错误，subset覆盖mean字段。 | Accept | 使用专用network/subset schema与字段，按seed/draw支持决定状态。 |
| Medium | sol #6 | 非有限统计被静默过滤，valid计数可漂移。 | Accept | 输入/累积/输出遇非有限即拒绝；valid只计最终有限值。 |
| Medium | sol #7 | 全terminal构造伪空resample plan。 | Accept | 仍从verified prepared validation构建正常计划，独立于complete model数量。 |
| Medium | sol #8 | reader先做昂贵上游重放且接受extra files。 | Accept | 先验report manifest/receipts/fixed surface，再进行M4和统计重放。 |
| Medium | sol #9 | publication路径冲突可能晚失败并映射exit70。 | Accept | publisher在任何上游读取前preflight fresh direct child；CLI将RunPathError稳定映射为binding exit 3。 |
| Low | 5.5 #8 | relative denominator未要求正且有限。 | Accept | baseline W68必须有限且大于0，否则具名拒绝。 |

## 执行状态

当前阶段：`completed`。接受项已落实；focused报告3 passed/105 warnings、CLI 3 passed，`pip check`通过，全量686 passed/227 warnings。Windows synthetic未运行ARM64 authority、完整ROOT或科学数值验证。
