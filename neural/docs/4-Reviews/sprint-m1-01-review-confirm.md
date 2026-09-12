# Sprint M1-01 Review Confirm

日期：2026-09-12。输入：`sprint-m1-01-review-by-gpt-5.6-sol.md`、`sprint-m1-01-review-by-gpt-5.5.md`；目标为 FR-SE-01 与 sprint-m1-01。

## 结论

两份当前评审文件均已核验非空。接受具体化契约、异常及验证清单的意见。实现前先将规范表与绑定不变量补入 FR，明确契约文档更新目标。科学预注册不由本次软件评审代替。

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Requirement | sol F-01 | 缺精确字段和算法 ID | Accept | 开发计划 §5.2 与 FR 需求5仅列类别 | FR 增加完整 v1 软件 schema 表、固定 ID、数值约束；模板用 null，测试不得发明新规则。 |
| 2 | High | Correctness | sol F-02 | 交叉绑定不够具体 | Accept | overlay/freeze 重复 compact 和 delta；receipt 推迟 | 明确 base digest、prepared/population、artifact ID 与 payload digest 分别校验；compact descriptor 与 delta/source 逐项比对，发现总体不强制等于学习总体；新增成对篡改测试。 |
| 3 | Medium | Correctness | sol F-03 | 缺候选异常含糊 | Accept | errors.py 的 ResearchError=3、ResearchStateError=0 | M1 抛 ResearchError(status=compact_candidate_not_frozen)，exit_code=3；不返回状态对象、不发布 workflow 终态；测试异常类/status/code。 |
| 4 | Medium | Documentation | sol F-04 | 未指定 artifact-schema 更新 | Accept | 计划 M1、FR 输出要求已实现契约 | Sprint 明确 artifact-schema.md、research-software-design.md 和文档索引，登记两种 payload 的软件状态/摘要边界及未实现发布。 |
| 5 | Medium | Test | 5.5 SE-01 | 专项命令漏旧协议测试 | Accept | test_data.py 包含旧协议严格读取覆盖 | 专项验证加入 tests/research/test_data.py，新增 characterization 固定现有三个摘要。 |
| 6 | Medium | Documentation | 5.5 SE-02 | 契约文档目标不明确 | Accept | 与 sol F-04 相同结论但给出 schema 清单证据 | 同第4项落实；仅登记 M1 两种 payload，不登记未来模型/子集为已实现。 |
| 7 | Info | Consistency | 5.5 SE-03 | M1 软件范围合理 | Accept | 研究计划 §17、FR 非目标 | 保留正式预注册 pending，后续 M2—M7 未启动，所有正式值由外部证据提供。 |

## 立即行动与状态

按上述表更新 FR/Sprint 后 document-confirm gate 通过；不存在需要用户批准的新增科学默认值。此为文档门确认记录；后续代码评审与测试已完成，见 [最终Sprint](../3-Plan/Done/sprint-m1-01.md)。正式 artifact receipt、候选审计和 ARM64/ROOT 验收明确推迟。
