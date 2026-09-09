# 当前科研与软件状态

状态日期：2026-09-09。本文描述当前工作区能力与缺口，不将代码存在或历史软件测试升级为科学验证。

## 状态矩阵

| 能力 | 状态 | 当前边界 |
|---|---|---|
| 两套受控 MC 数据集绑定 | 当前代码已实现 | `atlas2020_4lep` 与 `atlas2025_exactly4lep` 分开运行，跨 release 等价性未证明 |
| 有窗、inclusive、debug 预处理 | 当前代码已实现 | 只处理 MC；development/test 独立发布 |
| 19 项工程特征与 Angular5 | 当前代码已实现 | 研究导出另保留逐轻子四动量、配对、终态与y4l；仍需绑定MC重建审计 |
| 固定 legacy15 adversarial MLP | 当前代码已实现 | classifier 禁止 `m4l`；网络与候选集合密封 |
| 事件组五折 OOF 与 final fit | 当前代码已实现 | 不等同于新研究的五角色拆分 |
| normal/inclusive 资格判断 | 当前代码已实现 | AUC、KS、效率是当前流程门槛，不是 μ 推断结果 |
| debug diagnostic | 当前代码已实现 | 仅供诊断，不能升级为正式科学资格 |
| 冻结 held-out MC 评价 | 当前代码已实现 | 需要匹配 dataset 和 run 绑定；不自动授权 |
| 锁定 ARM64 权威验证 | 需要外部或权威验证 | Windows/synthetic 结果不能替代 authority gate |
| 完整 MC 新研究证据 | 需要外部或权威验证 | 当前没有可作为 H4l 论文结果的冻结运行 |
| `src.research` 与 `higgsml-research` | 当前代码已实现 | 十个阶段入口，独立于legacy15 |
| ResearchProtocol 与五角色数据 | 当前代码已实现 | v1兼容；v2新增诊断契约，仍是合成软件默认规则 |
| decay7/engineered19/mass-only/lab-extension | 当前代码已实现 | 研究模型支持1/8/10/20维，旧classifier保持15维 |
| MELA 适配 | 当前代码已实现 | 外部后端实际构建和独立物理参考仍需验证 |
| 条件 CDF 与 calibration artifact | 当前代码已实现 | signed约束估计与绝对权重桥接；M5-abs须通过G1 |
| 二维模板、pyhf 与 μ inference | 当前代码已实现 | pyhf 0.7.6可选依赖；signed-MC T1适用性需独立证据 |
| G0/G1、Asimov、伪实验和覆盖检查 | 当前代码已实现 | 不是绑定MC先导通过声明；仅检查覆盖，不自动校准区间 |
| 逐epoch训练诊断 | 当前代码已实现 | v2分项loss、λ、AUC、质量诊断及配对图；不保证收敛 |
| 带符号μ伪信号诊断 | 当前代码已实现 | 独立固定名义模板T0点估计；T1剖面诊断未实现 |
| Toy区间校准 | 后续预注册与实现 | 不把覆盖检查称为区间校准 |
| 有来源系统变化和外部 MC | 需要外部或权威验证 | 人为压力测试不能冒充实验系统误差 |

## 当前可支持的结论

仓库提供严格绑定、MC-only的legacy15流程及独立H4l研究软件。研究软件支持五角色、可变表示、CDF、模板、物理区间和辅助诊断，并提供数据隔离、不可覆盖run、协议/输入摘要及冻结assessment守卫。当前不能据此声称已取得μ精度改善或覆盖可靠的科学结果。

这些能力只能支持 educational/technical demo。代码存在、单元测试通过、合成数据验证、真实 MC 运行、锁定 ARM64 复现、外部矩阵元验证和论文级科学结论是不同状态，不能相互替代。

## H4l 项目缺口

[`H4l-Research-Project.md`](H4l-Research-Project.md) 是下一阶段方案，目前仍是 draft。开始主实验前至少需要：

- 审计样本过程、终态、支持域、signed yield、有效统计和历史 test 反馈；
- 在已有development-only导出、模型、CDF及推断实现上完成绑定MC验证；
- 完成实际MELA后端与独立参考、signed模板近似适用性证据；
- 在软件默认协议基础上冻结适用于MC的G0/G1、分箱、似然和预算，新增版本不得复用旧assessment反馈冒充独立验证；
- 完成合成数值验证、绑定 MC 先导、独立参考和有来源稳健性验证。

实现、测试和科学证据分别标记；不得从现有`eligible`、`debug_diagnostic`或`test_reproduced`状态推导研究完成。实际软件验证记录见[开发记录](../sw-dev/h4l-research-development.md)及[本次修订记录](../sw-dev/h4l-review-revision-2026-09-09.md)。

## 继续工作的入口

- 科研总方案：[`H4l-Research-Project.md`](H4l-Research-Project.md)
- 当前预处理：[`preprocess-protocol.md`](preprocess-protocol.md)
- 当前模型：[`adversarial-mlp-protocol.md`](adversarial-mlp-protocol.md)
- 当前 development/test：[`development-protocol.md`](development-protocol.md)、[`test-opening-protocol.md`](test-opening-protocol.md)
- 软件架构与 schema：[`../sw-dev/architecture.md`](../sw-dev/architecture.md)、[`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)
