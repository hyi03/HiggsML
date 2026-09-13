# 当前科研与软件状态

状态日期：2026-09-13。本文区分代码能力、软件验证和论文级科学证据。

## 状态矩阵

| 能力 | 状态 | 证据边界 |
|---|---|---|
| 受控 MC 数据集契约与下载校验 | 已实现 | 数据集分开绑定；跨 release 等价性未证明 |
| H4l 重建、选择、Angular5、工程变量与权重 | 已实现 | 仍需完整绑定 MC 重建审计 |
| 五角色事件组隔离 | 已实现并有合成测试 | 合成测试不替代实际总体审计 |
| mass-only、decay7、engineered19、lab-extension | 已实现 | 支持协议定义的共同 `m4l` 条件 |
| 普通/对抗训练与逐 epoch 诊断 | 已实现 | 诊断存在不保证物理收敛或泛化 |
| MELA 导出/导入适配 | 已实现接口 | 实际后端和独立物理参考仍需验证 |
| 条件 CDF、共同二维模板与 pyhf 推断 | 已实现 | signed-MC T1 适用性需独立数值证据 |
| G0/G1、freeze、assessment 与报告 | 已实现 | 当前没有可直接作为论文结果的冻结完整 MC run |
| 增强分析导出 | 已实现并有合成/现有 MC 产物重放检查 | AUC、训练、校准、模板、推断、归因和状态可导出；AUC仍是同 validation checkpoint 指标 |
| 注册评价编排 | 已实现并有合成软件测试 | bootstrap/Toy/T2/stress 的正式 MC 预算尚未执行完成 |
| 独立证据包导入 | 已实现 receipt 与类型守卫 | signed-MC/T1、物理变化、MELA、ARM64 的外部材料仍为 `external_pending` |
| 样本效率子集、训练、聚合与确认 | 已实现并有合成测试 | 正式注册值和完整 MC 实验尚待执行 |
| 软件测试 | 本次增强聚焦 39 passed；Windows 全套 416 passed / 34 failed | 失败来自本次改动之外的既有 scientific resource seal 与训练历史契约不一致；未擅自重签资源。软件测试不等同于科学或 authority 验证 |
| 原生 macOS ARM64 authority | 未在本次重构中运行 | Windows 结果不能替代 |
| 完整 MC 科学验证 | 未在本次重构中运行 | 不得声称已获得 `mu` 精度改善或覆盖结论 |

## 当前可支持的结论

仓库已提供严格绑定、不可覆盖且具备 assessment 反馈守卫的 H4l 软件链路。它可支持方法开发、合成闭合测试和后续受控 MC 实验，但目前只能描述为 educational/technical workflow。

代码存在、单元测试通过、合成数据验证、完整 MC 运行、原生 ARM64 复现、外部矩阵元验证和论文级物理结论是不同状态，不能相互替代。

## 形成论文结果前的主要缺口

- 审计实际样本过程、终态、支持域、signed yield、有效统计和事件组隔离；
- 冻结适用于完整 MC 的协议、G0/G1、分箱、似然和计算预算；
- 完成实际 MELA 后端与独立参考验证；
- 验证 signed 模板近似、似然闭合、区间覆盖和有来源的建模变化；
- 执行封存评价计划中的固定网络 MC bootstrap、μ=0/1/2 Toy、配对 coverage、T2 与人工压力矩阵；
- 在冻结后执行 assessment，并保证结果不回流改变研究设计；
- 在锁定原生 ARM64 环境中完成单独的 authority 重放。

继续工作应从[研究方案](../methods/research-project.md)、[运行手册](../reproducibility/runbook.md)、[产物契约](../reproducibility/artifact-schema.md)和 `config/protocols/h4l_protocol.json` 开始。
