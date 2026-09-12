# Sprint M2-01 Review Confirm

日期：2026-09-12。输入为两份M2文档评审，目标为FR-SE-02和sprint-m2-01。

## 结论

评审正确发现现有h4l-events-v1无法在完全不解码payload时计算权重/质量摘要。选择最小兼容方案：先验证整文件receipt和全部identity，再只解码train行payload的`physical_weight`/`m4l`；assessment及其他非train payload永不解码。补齐schema、摘要、ID、双协议和freeze run绑定后进入实现。

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Critical | Correctness | sol F-01 / 5.5 #1 | identity不含weight/m4l，纯identity要求不可实现 | Accept | data.py的IDENTITY只有7字段，其余在payload | 两阶段读取：先扫描/验证identity，第二遍仅解码train payload的两个字段；poison assessment测试。 |
| 2 | High | Requirement | sol F-02 / 5.5 #4 | schema与ID/digest preimage未定义 | Accept | 当前文档只给名称 | 定义三个文件各一个schema；membership digest绑定排序记录，subset ID绑定overlay/prepared/draw/fraction/digest，ledger alias明确full。 |
| 3 | High | Security | sol F-03 | overlay/freeze trust chain未落地 | Accept | M1明确payload校验不证明artifact来源 | M2要求prepared run与compact-freeze run均为LoadedRun；receipt验证freeze.json，重建freeze对象；manifest upstreams含两者，另写overlay snapshot并绑定digest。 |
| 4 | High | Correctness | sol F-04 | 摘要和质量支持阈值不明确 | Partial | sumw/sumw2/neff可定义；M1没有质量跨度阈值 | 定义组级权重：每组所有行求和；sumw2为组和平方，neff_abs=(sum_abs_group)^2/sum(group_sum^2)。m4l仅记录min/max，不设未注册门；低统计只依据每类group数、正sum_abs和协议min_effective_count。 |
| 5 | Medium | Correctness | sol F-05 / 5.5 #3 | run与cell终态不明 | Accept | ResearchRun complete和terminal reader不同 | 只要身份有效就发布complete计划；每个subset可planned或training_subset_insufficient_statistics。两类均可由M3读取；若全无planned也保持complete可审计计划。非有限train weight/mass为binding mismatch，不是低统计。 |
| 6 | Medium | Documentation | 5.5 #2/#5 | 不存在per-row预期digest且文档更新不具体 | Accept | prepared只有整文件receipt | 删除“验证per-row digest”，改为重算identity digest并纳入subset摘要；Sprint明确更新artifact-schema。 |

## 状态

所有接受/部分接受项在下述FR/Sprint修订中落实；文档门通过。M3—M7不在本次实现范围。
