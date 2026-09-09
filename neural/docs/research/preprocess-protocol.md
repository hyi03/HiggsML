# 数据预处理科研协议

状态：**当前代码已实现；完整 MC 与权威环境结论需要单独验证。**

本文说明当前预处理实现承载的科学语义。软件流程、数据接口和 artifact 字段见 [`../sw-dev/dataset-and-preprocessing-design.md`](../sw-dev/dataset-and-preprocessing-design.md) 与 [`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)。

## 数据边界

当前流程严格 MC-only，并要求每次运行显式绑定一个受控数据集：

| 数据集 | 信号 | 背景 | 输入形态 |
|---|---|---|---|
| `atlas2020_4lep` | DSID 345060 | DSID 363490 | 2020 Open Data `mini` tree |
| `atlas2025_exactly4lep` | DSID 345060 | DSID 700600 | 2025 `analysis` tree |

数据集定义绑定文件身份、大小、校验和、tree、entry count 和角色。两套数据的归一化来源与输入 profile 不同，跨 release 的物理等价性尚未证明，因此不得联合训练或共享 held-out test 反馈。

流程禁止真实数据，也不允许通过路径或运行配置替换样本身份、标签、profile、物理规则或数据集配对。运行配置只提供受控文件路径和资源参数。

## 选择与重建

当前代码按冻结顺序执行触发、轻子数、横动量、接受度、trigger matching、质量、隔离、冲击参数、SFOS、Z 配对、Z 质量要求和可选 `m4l` 窗口。单位转换在 profile 层完成，后续物理计算统一使用 GeV。

Z1 是最接近名义 Z 质量的 SFOS 对；Z2 从剩余轻子构造。选择、tie-break、四动量和 Angular5 约定由 `src/domain/` 实现，不能由运行参数临时修改。

每个通过选择的事件生成 19 项工程特征：

- 单轻子运动学：四个 `lep_pt` 和四个 `lep_eta`；
- Z 内部结构：`mZ1`、`mZ2`、`deltaR_Z1`、`deltaR_Z2`；
- 四轻子与双 Z 运动学：`pt4l`、`deltaPhi_ZZ`；
- Angular5：`cos_theta_star`、`cos_theta_1`、`cos_theta_2`、`phi_decay_planes`、`phi_production_plane`。

`m4l` 单独保存，不属于这 19 项。当前持久表还保存标签、split、signed `physical_weight`、来源身份和物理事件分组身份；有窗/debug 表另含 `train_weight`，inclusive 表不含该列。

## 身份、权重与隔离

`source_file_id` 与 `source_entry` 标识来源行；`event_group_id` 表示保守的物理事件分组。相同物理事件的来源行必须进入同一 development/test split，并在训练时进入同一 fold，避免行级泄漏。

`physical_weight` 保留符号，用于物理产额及审计。优化器和分类指标不能直接使用 signed weight：有窗兼容流程持久化按既定口径生成的非负 `train_weight`；inclusive 流程在拟合折内根据 `abs(physical_weight)` 计算类别归一化。两种口径不得混用。

预处理分别发布 development 与 test 文件及各自哈希。development reader 只解码 development；test reader 只有通过冻结 gate 后才解码 test。任何新研究导出都必须先判定事件属于 development，再访问新增逐轻子内容。

## 有窗与 inclusive

| 模式 | 质量范围 | 输出 | 后续训练 |
|---|---|---|---|
| mass-window | `105 <= m4l < 160` GeV | 31 列，含 `train_weight` | 固定质量边和兼容权重语义 |
| inclusive | 不额外施加 `m4l` 窗口 | 30 列，不含 `train_weight` | 拟合折分位数质量箱与折内类别归一化 |
| debug | 无额外质量窗的诊断入口 | 31 列，含 `train_weight` | 仅用于明确标记的诊断流程 |

“inclusive”只表示通过基础选择后不再增加固定四轻子质量窗，不表示没有生成级过滤、数据集预选或 Z 质量要求。

## 与新 H4l 研究的关系

状态：**最新方案规划中。** 当前表支持 legacy15 和 19 项工程变量，但不完整保留新方案需要的逐轻子四动量、终态、配对和研究角色。不得从 19 列反推缺失信息。新研究需要独立、版本化的 research 导出契约，同时保持现有预处理和冻结 run 的语义不变。
