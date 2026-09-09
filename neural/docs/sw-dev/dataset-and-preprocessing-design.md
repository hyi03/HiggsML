# 数据集与预处理设计

## 1. 受控数据集

**当前代码已实现。** 系统只接受两个具名 MC dataset：

| Dataset | Higgs | ZZ background | Release / collection | Profile |
|---|---:|---:|---|---|
| `atlas2020_4lep` | 345060 | 363490 | 2020 / `4lep` | `open_data_2020.yaml` |
| `atlas2025_exactly4lep` | 345060 | 700600 | 2025 / `exactly4lep` | `release22.yaml` |

每个定义必须恰有 Higgs/ZZ 两个成员并声明 `mc_only: true`。精确 record URL、文件名、字节数、entry count、source checksum 和 SHA-256 只以 `config/datasets/*.json` 为准；`src/data_contract.py` 还固定已审核定义本身的 revision 与摘要。

两个 dataset 是隔离的实验单元。相同 DSID 不足以证明跨 release 的逐事件等价，因而不能联合训练、交叉替换 artifact 或共享 test 反馈。

## 2. 下载与本地输入

下载定义由标准库代码解析，URL 必须为固定 HTTPS 资源。目标文件使用 exclusive create；下载到临时文件时流式计算摘要并检查大小，成功后原子改名。已存在、partial、摘要不符或 schema 不符均失败关闭，不能把本地同名文件当成受控输入。

本地 run config 只引用 dataset 名和允许的数据根。业务 CLI 必须显式传 `--dataset`，且参数、run config、definition 和实际文件四者必须一致。

## 3. Profile 与 domain 归一化

Profile 负责 ROOT tree、branch 映射、单位和输入形状差异；domain 层接收归一化事件后执行统一的四轻子重建、选择和特征计算。Profile 与科学选择分别封存，避免把格式差异误写成物理差异。

当前输出包含 19 项工程变量：四个 lepton `pt`、四个 lepton `eta`、`mZ1`、`mZ2`、`pt4l`、`deltaR_Z1`、`deltaR_Z2`、`deltaPhi_ZZ`、`cos_theta_star`、`cos_theta_1`、`cos_theta_2`、`phi_decay_planes`、`phi_production_plane`。其中只有协议固定的 legacy15 进入当前 classifier；精确列表见训练协议和 [`training-and-evaluation-design.md`](training-and-evaluation-design.md)。

## 4. 身份、分区与防泄漏

- `source_file_id + source_entry` 是全局来源行键，用于 lineage 与逐行唯一性。
- `event_group_id` 来自物理事件身份，当前编码为 `channelNumber:eventNumber`。
- Development/test split 和五折 assignment 都绑定事件组；同组的所有来源行必须进入同一 split/fold。
- 当前 fold 算法为 `sha256_event_group_v2`。内部算法名可以版本化，文档文件名不随实现版本编号。

预处理同时生成 development 与 test 文件，但训练 reader 只验证并解码 development。Test 描述符在这时只是冻结的预期绑定，不等于 test 字节已被重新读取或验证。

## 5. 输出模式

| 模式 | 范围与权重设计 | 表列数 | 工程状态 |
|---|---|---:|---|
| Mass-window | 固定质量窗；持久化全部选后样本定义的 `train_weight` | 31 | 当前代码已实现 |
| Inclusive | 无固定质量窗；不持久化 `train_weight`，训练时只在 fitting scope 计算归一化 | 30 | 当前代码已实现 |
| Debug | 显式诊断协议，沿用有窗列契约 | 31 | 当前代码已实现 |

两类表都包含 19 项工程变量、`m4l`、label、split、physical weight、来源信息和两种身份。质量、权重、身份、label 和 split 都是禁止的 classifier 特征。

## 6. 发布与校验

预处理运行发布配置快照、两个分区表、cutflow、MC summary 和 manifest。Manifest 记录输入、dataset binding、协议/config 摘要、列序/dtype、计数、软件、平台、确定性与性能。CSV 使用固定 UTF-8、LF、`.17g` 与 deterministic gzip，并记录压缩和 canonical 内容摘要。

Authority comparator 只在锁定原生 ARM64 且存在预登记独立 reference 时构成权威验证；Windows 或 synthetic micro-ROOT 只能提供开发证据。

## 7. 下一阶段缺口

**最新方案规划中。** H4l 研究需要 development-only research export，持久化更完整的逐轻子四动量、终态/渠道和五角色身份；该导出必须与现有产品 artifact 隔离，不能更改 legacy reader 的含义。

**需要外部或权威验证。** 两套 release 的物理支持域、signed yield、有效统计、跨 release 等价性和完整 MC cutflow 仍需独立审计。当前配置和代码存在不代表这些科学结论已经取得。
