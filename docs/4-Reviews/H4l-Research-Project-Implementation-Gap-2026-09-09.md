# H4l 方案与当前代码差距分析

日期：2026-09-09。依据：[已确认的导师评审](H4l-Research-Project-Mentor-2026-09-09-review-confirm.md)。

## 结论

需要修改，但无需重写科研路线。当前重点是：更新实现状态、细化并落实训练诊断、补齐带符号 μ 的伪信号诊断，以及堵住 M5-abs 绕过 G1 的执行路径。

当前已经存在 `src.research`、`higgsml-research`、研究协议、CDF、模板与推断软件，不能继续沿用“研究模块尚不存在”的判断。与此同时，软件存在不代表真实 MC 先导、独立 MELA 参考、signed-MC T1 近似或科学覆盖验证已经完成。

本轮使用代码图谱发现函数，更新索引后核读实现、协议和相关测试；对图谱结果不足处用文件检索核对。分析为静态审阅，没有修改原方案/代码/协议，没有执行测试、训练或 Toy，没有读取真实数据、MC 特征或 held-out test。开发记录中的历史测试数字不是本轮复跑结果。

## 需要修改的具体位置

| ID | 优先级 | 对象 | 现有证据与问题 | 最小修改及验证要求 |
|---|---|---|---|---|
| D1 | Medium | H4l-Research-Project.md §5.1、§10.1、§12；current-research-status.md 及软件设计说明 | 方案 §5.1 明确注明历史快照，但其中“未发现现成 MELA/CDF/μ 拟合实现”已经不能代表当前工作区；current-research-status 更直接声称研究代码/CLI 不存在，与 pyproject.toml 及源码冲突 | 保留历史快照和计数出处，新增截至当前的实现状态与 runbook 链接；按“软件已实现／本轮未运行／需外部验证／确实未实现”拆分。同步 current-research-status、architecture、artifact-schema、research-software-design，避免互相矛盾。不把历史 Windows 测试当科学验收。 |
| D2 | Low | 方案 §6.1、§10.1、§13 | 只泛称“记录学习曲线与最终状态”，没有明确已采纳评审第07项的分项日志及附录要求；§10.1 命令列表也遗漏现有 freeze | 明确每轮分类损失、背景 adversary 损失、有效 λ、验证 AUC 和固定定义的背景质量诊断，说明权重与汇总口径、warm-up/ramp 标记、同种子 λ=0 对照及最终 checkpoint；区分逐 epoch 训练曲线与 R2 的样本量学习曲线。列入 freeze 命令和产物。 |
| C1 | Medium，正式训练前 | src/research/discriminants.py:135–178；reporting.py 与 workflow.py 的 report 分支 | history 每轮只保存 epoch、effective_lambda、validation_absolute_weight_auc 和合并 loss；BCE 与 adversary CE 相加后才记录，质量诊断只在最终模型计算。现有报告也没有曲线交付 | 独立保存分类与对抗损失并声明加权分母，保留合并值但不把它当纯分类损失或收敛证明；按预注册定义逐轮计算质量诊断，生成附录图。阈值来源和每轮是否重算须先明确，不能用 assessment 决定。测试应验证分项数值口径、200轮、λ阶段、配对预算及未访问 assessment。 |
| C2 | High，纯背景诊断前 | src/research/inference.py:23–85；protocol.py:99–100；assessment.py:95–191 | build_model 将 μ 下界固定为0；协议同样拒绝负下界；所有区间与 Toy 复用这一模型。未找到独立带符号 μ 拟合入口，而方案 §7.4 已明确要求这种伪信号诊断 | 新增独立诊断契约与入口，保留正式物理区间 μ≥0。负 μ 搜索必须保证各箱总期望及 nuisance 变化下的合法性，不能只把主模型下界改负。报告分别标注 constrained bias、带符号伪信号及失败。先用正/负注入偏差的单箱解析例、纯背景例、非法物理率和退化支持测试验证。没有该能力时输出“未实现”，不能以边界正偏宣称失配。 |
| C3 | Medium，扩展候选前 | src/research/workflow.py:342–350、378–415 | G1 检查仅在非最小 train 分支；calibrate 的 absolute 分支只验证来源是 M3，没有要求 gate_run 或检查 G1。由 G0 通过的 prepared 和 seed42 M3 可在 G1 前构造 M5-abs，与方案 §5.4 和运行手册不符 | 将 M5-abs 校准纳入扩展守卫：同一 prepared、协议绑定且 G1 passed；在拟合映射之前拒绝缺失、失败或不匹配证据。补无 gate、失败 gate、不同总体 gate 和有效 gate 的回归测试；更新桥接命令示例。此问题是扩展顺序缺口，不等于 assessment 已泄漏。 |
| D3 | Low | 方案 §5.2、§5.4 | 原文没有评审所称的7.5统计或干涉归因错误，但可进一步减少误读 | 可补一句“14.9/7.5 为未筛终态前原始 MC 条目示意，不是10 fb⁻¹预期观测产额或 N_eff”；在物理来源审计中明确负权重机制待核对，不能从符号直接推断干涉。无需修改原统计数值或提高亮度。 |
| F1 | Medium，可靠覆盖结论前 | inference.py:54–85；方案 §7.4/§12 | 区间目前只使用 bounded profile likelihood 的 χ²(1) 临界值；Toy 实现检查覆盖，但并未实现按 Toy 校准临界值/区间构造 | 当前渐近区间可保留用于先导诊断，并明确其覆盖未经验证。若要交付“覆盖不足后已校准”的结论，需要独立版本化的校准方案和代码、独立验证预算；不能把运行500次 Toy 当成自动校准，也不能在同一 assessment 上调整再声称独立验证通过。 |

## 不需要因本次评审改动的部分

| 主题 | 文档/代码证据 | 判断 |
|---|---|---|
| M6 固定200轮与 λ=0 对照 | discriminants.train_discriminant 固定选择200轮，构造匹配 adversary 保持 RNG 消耗；test_discriminants 有确定性及配对断言 | 保留。评审把它解释成防止过拟合才是需要纠正的地方，不应改回最高 AUC checkpoint。 |
| 边界正偏的解释 | 方案 §7.4 明确不能直接归因失配；reporting.fit_diagnostics 将偏差/pull 标为描述性并记录边界计数 | 原则正确。缺口是 C2 所述的第二条诊断路径，而不是现有物理区间应允许负 μ。 |
| 500次预算与覆盖误差 | 方案 §7.4 已给出先导精度；coverage_summary 输出 Wilson 区间、失败计数及成功且覆盖比例 | 无需为迎合“充分验证”措辞增加成功宣称。预算扩展仍须预注册。 |
| assessment 冻结与角色隔离 | workflow.events 要求 freeze，绑定模板、协议与预算；claim 在 payload 解码前建立；train/calibrate/templates/freeze 检查总体未开启 | 核读路径已落实相关守卫；不因评审“立即跑Toy”调整为先评估后冻结。本结论不等于完整安全审计。 |
| G1/T1 科学资格 | templates.gate_g1 检查最小模板状态、协方差和外部证据契约；workflow 冻结要求 G1 passed | 保留门槛。代码验证证据字段不等于自动证明物理近似正确，仍须实际独立验证。 |
| MELA 基线 | 已有导出/导入、外部运行器与可选 adapter；运行手册明确独立参考缺失时不能完成科学比较 | 无需从零重做适配层；优先补实际后端构建、来源和独立参考证据。 |
| Shapley 与 L1 解释 | 方案 §8 限定流程贡献、同流程空集、互补/替代和非因果解释；代码已有 exact_shapley 及表示支持 | 不把评审赞许改成已经获得物理解释。完整实验仍属后续预注册工作。 |
| 系统变化 | 方案 §9 区分 S/P；当前实现主要为人工压力工具 | 有来源轻子/生成器变化仍是 R3 工作，不属于此次必须完成的新功能；不能把10%扰动重命名为真实系统误差。 |

## 建议实施顺序

1. 小范围更新 D1/D2/D3，保持现有科学目标、评审已纠正的边界和历史快照可追溯。
2. 正式研究训练前补 C1，防止先训练后发现无法恢复分项曲线；同步修 C3，确保候选扩展遵守 G1。
3. 首次正式纯背景诊断前补 C2，并在协议中区分物理区间与带符号伪信号估计。F1 的 Toy 校准规则需在相应验证前预注册。
4. 再推进 P0/G0、最小 G1、MELA 独立参考与 T1 适用性证据，按冻结分析运行正式 assessment。外部证据缺失是科研推进条件，不应通过放宽代码检查解决。

这些修改限制在新研究命名空间和相关说明内。旧 legacy15 分类器、历史 checkpoint 规则、test-opening 与冻结产物保持原语义。本轮未发现证据要求为该评审调整旧流程。

## 主要核对入口

- [科研方案](../../neural/docs/research/H4l-Research-Project.md)
- [当前科研状态（含过期描述）](../../neural/docs/research/current-research-status.md)
- [当前运行手册](../../neural/docs/sw-dev/h4l-research-runbook.md)
- [历史开发记录](../../neural/docs/sw-dev/h4l-research-development.md)
- [研究软件默认协议](../../neural/config/research_protocol_v1.json)
- [训练](../../neural/src/research/discriminants.py)、[推断](../../neural/src/research/inference.py)、[工作流](../../neural/src/research/workflow.py)、[assessment](../../neural/src/research/assessment.py)、[报告](../../neural/src/research/reporting.py)
- [训练测试](../../neural/tests/research/test_discriminants.py)、[推断测试](../../neural/tests/research/test_inference.py)、[工作流守卫测试](../../neural/tests/research/test_workflow_guards.py)

未运行测试，因此以上不声称当前测试通过，也不以历史94/484等通过数作为本轮验证结果。已确认的问题来自对应源码分支及文档契约的直接比对；对整个仓库其他行为不作无缺陷保证。
