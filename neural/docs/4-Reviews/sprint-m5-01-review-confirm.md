# Sprint M5-01 文档评审确认

## 输入与结论

- 需求：[FR-SE-05](../1-Requirement/FR-SE-05-paired-aggregation-reporting.md)
- Sprint：[sprint-m5-01](../3-Plan/sprint-m5-01.md)
- 评审：[gpt-5.5](sprint-m5-01-review-by-gpt-5.5.md)、[gpt-5.6-sol](sprint-m5-01-review-by-gpt-5.6-sol.md)
- 结论：两份评审指出统计重放与可信reader边界尚未闭合。全部实质意见接受并已写回FR/Sprint；M5实现不得在这些合同之外自行选择统计算法。

| 严重度 | 来源 | 意见 | 决定 | 落实 |
|---|---|---|---|---|
| High | 5.5 #1 / sol #5 | M4 verified结果到cell payload的可信边界不明确。 | Accept | publisher/reader均重跑M4 reader；use-time再调用public cell reader并核对ledger ID。 |
| High | 5.5 #2 / sol #3 | model-stage terminal无model，actual count来源矛盾。 | Accept | M2 subset summary为所有cell权威来源；model存在时双向重验。 |
| High | 5.5 #3 / sol #4 | bootstrap RNG、AUC ties、ddof、quantile与0/1有效状态未冻结。 | Accept | 固定canonical group排序、PCG64调用、带权Mann–Whitney、ddof=1、linear quantile和nullability。 |
| High | sol #1 | mean(cell std)不是聚合曲线AUC误差。 | Accept | 每replicate先聚合curve-row固定cell，再计算aggregate std/quantile。 |
| High | sol #2 | summary/Q*/CSV/nested uncertainty缺exact schema。 | Accept | 增加顶层/curve/Q* keys、状态枚举、ID、CSV方言及contract算法映射。 |
| High | sol #6 | Q*可受幸存者偏差与重复actual n影响。 | Accept | 仅完整curve row eligible；重复n具名不可估计；记录插值两侧row ID且禁止外推。 |
| Medium | 5.5 #4 / sol #8 | pairing identity与聚合分母不完整。 | Accept | 同时核对pairing ID/subset及显式键；固定planned/complete/pair eligible/paired/missing计数。 |
| Medium | 5.5 #5 | Q*输入曲线重复actual count和plateau未定义。 | Accept | unique actual n门禁；精确命中或严格下降包围，多个 crossing取最小n。 |
| Medium | sol #7 | subset误差会混入不同seed缺失模式。 | Accept | 使用所有draw共同complete seed交集，不足2 draw/seed显式not_estimated。 |
| Medium | 5.5 #6 / sol #9 | PNG/Markdown receipt不足以认证人类输出语义。 | Accept | summary绑定exact plot spec；PNG标非权威缓存；Markdown/CSV逐字节重放。 |
| Medium | 5.5 #7 / sol #10 | M5不能复用M4 exact config且CLI边界不完整。 | Accept | 新建M5 exact config；列出完整参数、优先级、固定runs root与退出码。 |
| Medium | 5.5 #8 | 缺关键自洽重签与统计golden测试。 | Accept | Sprint补use-time替换、terminal count、tie/zero/single-class、Q*重复n、human output重签测试。 |
| Low | 5.5 #9 | 未明确artifact-schema §11。 | Accept | Sprint scope与FR输出明确新增§11。 |

## 执行状态

当前阶段：`document-review-confirmed`。实现只能在本确认之后开始。
