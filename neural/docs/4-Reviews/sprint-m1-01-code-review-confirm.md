# Sprint M1-01 Code Review Confirm

日期：2026-09-12。目标：sample_efficiency_protocol.py、模板、两个新测试模块及已确认 FR/schema 文档。

输入：`sprint-m1-01-code-review-by-gpt-5.5.md` 与 `sprint-m1-01-code-review-by-gpt-5.6-sol.md`。两份报告均为本次生成且非空；sol 首次评审超时，唯一一次同模型/high重试成功，其输出文案错误也已由作者更正。没有用另一模型替代缺失评审。

## 总体结论

严格schema和科学边界总体成立。5.5 指出的一项身份混用检查可在M1实现，无须提前引入完整 receipt reader。接受该最小修改，同时保留“caller metadata 校验不证明来源”的限定。必须先应用并测试此项，再完成提交门。

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Correctness | 5.5 CR-01 | payload SHA 可同时冒充 manifest artifact ID | Accept | artifacts.py 的 artifact_id 来自 manifest digest；新 validator 当前只分别比对调用方期望值；FR 明确两者含义不同且不互代 | 在 overlay 交叉绑定后拒绝 artifact ID 字面等于 freeze payload SHA；添加两侧同时替换为摘要仍拒绝的回归测试。该检查只拦截已知混用，不认证其他任意ID。 |
| 2 | Info | Consistency | 5.5 CR-02 | 其余边界未发现回归 | Accept | 新契约/characterization 测试及旧运行代码未修改 | 保留 M1 纯元数据范围；M2—M7 和 ARM64/科学证据另行验收。 |
| 3 | Info | Correctness | sol F-00 | 静态复核未发现当前范围缺陷 | Partial | 严格校验和已运行测试可验证其主要结论；CR-01仍证明一项可补的字段级拒绝缺口 | 认可其明确的静态验证范围，但不据此忽略CR-01。应用第1项并复跑专项与全量测试后关闭代码确认门。 |

## 后续行动与状态

唯一代码修正为第1项；文档补充字面值混用拒绝与其验证局限。不扩展为来源认证、事件读取或确认执行。修复后的验证记录和最终提交状态见 Sprint。其余后续建议均为已有 M2/M5/M6 范围，不阻塞本软件 Sprint。

最终状态：第1项已应用并增加 `test_freeze_payload_digest_cannot_substitute_artifact_identity`；专项157 passed，全量645 passed（316.08s），pip check通过。全部接受/部分接受行动已完成，代码确认门关闭为通过。FR/Sprint已归档，完整交付见 [Sprint M1-01](../3-Plan/Done/sprint-m1-01.md)。
