# H4l Research 数据预处理方案与流程

状态：**当前代码已实现；完整受控 MC、科学数值结论与原生 ARM64 权威验证需要单独执行和记录。**

本文说明 `src/higgsml` 当前 H4l 研究流程在模型训练前如何读取、筛选、重建、变换和封存数据。本文只描述 MC-only educational/technical workflow，不构成 ATLAS 结果、Higgs discovery 或物理测量。

本文面向当前唯一的 `higgsml` H4l 路径，说明其输入契约、持久化字段、角色划分和 `m4l` 使用规则。

## 1. 目标与原则

数据预处理的目标是把受控 ROOT MC 转换为可重复、可审计、角色隔离的 H4l research event population，并在任何模型拟合前完成以下工作：

1. 绑定数据集、信号/背景样本、ROOT profile、文件元数据和协议字节；
2. 在允许的数据总体内读取事件，执行冻结的四轻子选择与候选重建；
3. 只保留先导终态 `2e2mu`，构造工程特征、Angular5 和研究所需逐轻子信息；
4. 计算 signed physical weight，并按物理事件组确定性分配研究角色；
5. 发布带摘要和 lineage 的 `events.jsonl` prepared artifact；
6. 下游按角色最小化数据访问，训练时只使用 train/validation；
7. 使用 train 统计量进行模型输入标准化，避免验证或 assessment 信息进入拟合变换。

核心安全原则是：只处理 MC；不根据文件名猜测样本身份；同一物理事件组不得跨角色；assessment 在分析冻结前不得解码；已发布和失败的 run 不得覆盖。

## 2. 总体流程

```text
受控下载记录 + ROOT manifest + dataset profile + research protocol
                              │
                              ▼
                输入、文件、DSID、tree/schema 绑定
                              │
                              ▼
                  先读 event/channel 身份字段
                              │
                              ▼
          development-only 或 exploratory all-MC 总体选择
                              │
                              ▼
                按连续 eligible span 读取 ROOT payload
                              │
                              ▼
             四轻子事件选择与 SFOS/Z 候选重建
                              │
                              ▼
                      2e2mu 终态筛选
                              │
                              ▼
      engineered19 + Angular5 + m4l/y4l + 逐轻子信息
                              │
                              ▼
            physical_weight、身份和事件组字段构造
                              │
                              ▼
 train / validation / calibration / template / assessment
                     确定性角色分配
                              │
                              ▼
                 G0/P0 审计与 events.jsonl 发布
                              │
                              ▼
              训练读取 train + validation，train-only 标准化
```

ROOT 转换由 `higgsml.data.export_research_data()` 实现；训练前加载由 `load_research_data()` 实现；模型侧标准化由 `higgsml.modeling.discriminants.train_discriminant()` 实现。

## 3. 输入与绑定

### 3.1 必需输入

受控 ROOT prepare 接收：

- research protocol，例如 `config/protocols/h4l_v2.json`；
- dataset 名称，必须与 protocol 一致；
- `h4l-root-input-v1` manifest；
- 数据集对应的封存 profile；
- 受控下载契约中登记的 Higgs signal 和 ZZ background MC 文件；
- 正式受控 MC 训练所需的独立 P0 validation evidence。

合成测试可以从显式 `events.jsonl` 输入进入 prepare，但必须标记 `source_kind=synthetic`，不能冒充受控 MC 或完整科学验证。

### 3.2 prepare 前验证

代码在事件处理前验证：

- manifest 的 schema、dataset 和 `mc_only: true`；
- manifest 恰好绑定 `higgs` 和 `zz` 两类样本；
- profile 字节与 dataset contract 中的 profile 完全一致；
- 来源文件名、父目录、文件大小和已登记 SHA256；
- manifest 记录的 verified size/mtime 与当前文件元数据一致；
- ROOT tree 名称、原始 entry count 和必要 branches；
- 每个文件的 `channelNumber` 全部等于受控样本 DSID。

这里的 SHA256 是已有 acquisition evidence。当前 prepare 不重新扫描整份 ROOT 文件计算哈希，因此不能把它描述为本次重新验证了全部输入字节。

## 4. 来源总体与读取边界

### 4.1 development-only 协议

常规 v1/v2 research protocol 先仅读取 `eventNumber` 和 `channelNumber`，调用冻结的 `event_split(eventNumber, dsid)` 判定历史 split。只有 `split != test` 的 entry 才进入 payload 解码；最终 research split 标记为 `development`。

eligible entries 被整理为升序、半开且不跨 forbidden entry 的连续 span，每个 span 最多读取 `root_max_entries` 条。这降低碎片化读取开销，同时保证应用层不会为了拼接区间跨过 test entry 解码其事件数组。

ROOT basket 可能同时包含相邻 development/test 字节。这里保证的是“不解码 test 事件数组”，不是“底层存储从未读取包含 test 字节的混合 basket”。

### 4.2 exploratory all-MC 协议

当 protocol 声明 `source_population=all_mc` 时，所有 MC entries 都是 eligible，最终 split 标记为 `exploratory`。该模式不保留历史 held-out test 边界，不能产生独立 test 泛化证据。

内部五角色和 assessment 冻结门禁仍然存在，但它们是从合并后的全 MC 总体重新划分的。

### 4.3 诊断条目上限

`--diagnostic-entries-per-file N` 只保留每个源文件前 N 个 eligible entries，用于固定工作量性能诊断。它不是科学事件选择，不得把这种 prepare run 用作训练输入；workflow 会把它发布为诊断终态。

## 5. 事件选择与 filter

当前流程确实执行 filter，而且分为来源总体 filter、物理事件 filter、终态 filter、结构/数值验证和角色访问 filter。

### 5.1 冻结的四轻子选择

Research prepare 读取 `config/protocols/h4l_selection_v1.yaml` 中的基础选择，再用当前 research protocol 的 `mass_window` 覆盖其中的 `m4l_window_gev`。因此，具体 H4l research 质量支持域由 research protocol 决定，而不是固定采用历史预处理文件中的 `105–160 GeV`。

当前选择顺序和默认阈值如下：

| 阶段 | 条件 | 未通过时的处理 |
|---|---|---|
| Trigger | `trigE` 或 `trigM` 为真 | 丢弃事件 |
| Allowed flavours | 至少四个 `|lep_type| in {11, 13}` 的轻子 | 丢弃事件 |
| Tight ID | 经过 tight identification 后至少四个轻子 | 丢弃事件 |
| Track isolation | `lep_track_iso / lep_pt < 0.3` | 丢弃不合格轻子；不足四个则丢弃事件 |
| Calorimeter isolation | `lep_calo_iso / lep_pt < 0.3` | 同上 |
| Transverse impact parameter | 电子 `|d0sig| < 5`，μ子 `< 3` | 同上 |
| Longitudinal impact parameter | `|z0 / cosh(eta)| < 0.5 mm` | 同上 |
| Multiplicity | 上述 good leptons 恰好为四个 | 丢弃事件 |
| Trigger match | 至少一个 good lepton 被 trigger matched | 丢弃事件 |
| Lepton pT | 四个有序轻子依次满足 `20, 15, 10, 7 GeV` | 丢弃事件 |
| Acceptance | 电子 `|eta| < 2.47`，μ子 `< 2.7` | 丢弃事件 |
| Charge | 四轻子总电荷为零 | 丢弃事件 |
| SFOS reconstruction | 能构造有效 same-flavour opposite-sign pairing | 丢弃事件 |
| All-SFOS mass | 每个 SFOS 质量 `> 5 GeV` | 丢弃事件 |
| Z1 window | `50 < mZ1 < 106 GeV` | 丢弃事件 |
| Z2 window | `12 < mZ2 < 115 GeV` | 丢弃事件 |
| Research m4l window | `lo <= m4l < hi`，边界来自 research protocol | 丢弃事件 |

Z1 定义为最接近名义 Z 质量的 SFOS 对，Z2 由剩余轻子组成；配对和 tie-break 由 `higgsml.physics.reconstruction` 冻结实现。

输入轻子数组必须与 `lep_n` 一致，相关数值必须有限。格式错误或非有限输入不是普通 selection failure，而是 input binding failure。

### 5.2 `2e2mu` 终态筛选

通过通用四轻子选择后，research export 额外要求重建候选的绝对 flavour 排序结果恰好为：

```text
[11, 11, 13, 13]
```

即只保留两个电子和两个 μ 子。`4e`、`4mu` 和其他组合不会进入 prepared population。若最终没有任何选中的 `2e2mu` 事件，prepare 以 `insufficient_statistics` 终止。

### 5.3 不是事件删除的检查

以下情况不会被静默 filter，而会使运行失败：

- Angular5 重建无效；
- 四轻子 rapidity 无定义，即 `E <= |pz|`；
- 必需特征或权重非有限；
- dataset、protocol、split、label 或 role 绑定不一致；
- event/source identity 缺失或重复；
- 同一 `event_group_id` 跨 role 或 label。

这种 fail-closed 行为防止异常事件被静默吸收到不同的数据总体中。

## 6. 重建与特征构造

### 6.1 单位与四动量

ROOT branch 名称和动量单位由 dataset profile 解释。`normalize_leptons()` 将输入转换到统一的研究表示，后续质量和动量均按 GeV 使用。

通过选择的事件保留：

- `lep_pt`、`lep_eta`、`lep_phi`、`lep_e`；
- `lep_charge`、`lep_type`；
- Z1/Z2 pairing indices；
- 四轻子 rapidity `y4l`。

这些逐轻子和配对字段用于 research、矩阵元导出和可重放审计；不能从旧的 19 列历史表中反推生成。

### 6.2 19 项工程特征

| 组 | 含义 | 特征 |
|---|---|---|
| A | 单轻子实验室系运动学 | `lep1_pt`…`lep4_pt`、`lep1_eta`…`lep4_eta` |
| B | Z 质量与内部几何 | `mZ1`、`mZ2`、`deltaR_Z1`、`deltaR_Z2` |
| C | 四轻子/双 Z 运动学 | `pt4l`、`deltaPhi_ZZ` |
| D | Angular5 | `cos_theta_star`、`cos_theta_1`、`cos_theta_2`、`phi_decay_planes`、`phi_production_plane` |

`m4l` 单独保存，不计入 engineered19。当前 `higgsml` protocol 明确允许每种研究表示把 `m4l` 作为共同质量条件；这个例外不改变历史固定 15 特征分类器禁止使用 `m4l` 的规则。

### 6.3 模型表示

| 表示 | 输入特征 |
|---|---|
| `mass-only` | `m4l` |
| `decay7` | `mZ1`、`mZ2`、Angular5、`m4l` |
| `engineered19` | 19 项工程特征、`m4l` |
| 指定 A/B/C/D 组合 | 所选组的工程特征、`m4l` |
| `lab-extension` | decay7、`pt4l`、`y4l`、`m4l` |

特征顺序由 `higgsml.modeling.representations` 固定，不由 DataFrame 当前列顺序决定。

## 7. 身份、标签与权重

### 7.1 身份字段

每个通过选择的来源 entry 生成：

- `event_id = <file_id>:<entry>`；
- `source_row_id = <file_id>:<entry>`；
- `event_group_id = <channelNumber>:<eventNumber>`；
- `dataset`；
- `split`；
- `label`；
- `role`。

信号/背景 label 来自受控 dataset contract 中的样本定义，不从文件名、ROOT 内容或运行参数推断。

### 7.2 Physical weight

每个事件计算：

```text
physical_weight = luminosity_pb
                × xsec_pb
                × k_factor
                × filter_efficiency
                ÷ sum_of_weights
                × mcWeight
```

归一化常数来自 dataset science contract，luminosity 来自 research protocol。`physical_weight` 保留正负号，用于产额、抵消率和分组统计。

### 7.3 Sampling 与 yield weight

角色分配后计算：

```text
sampling_probability = role_probability × development_probability
yield_weight          = physical_weight / sampling_probability
```

对于当前 development-only v2，`development_probability=0.8`。对于 all-MC protocol，该字段应由协议设置为与其总体语义一致的值；读取器会逐行复算并拒绝不一致的 prepared artifact。

## 8. 角色划分与防泄漏

角色按 `event_group_id` 的固定哈希确定：

```text
SHA256("h4l-role-v1:" + event_group_id)
→ 前 8 字节大端整数
→ mod 100
→ 按 protocol 比例映射角色
```

当前 v2 比例为：

| 角色 | 比例 | 用途 |
|---|---:|---|
| train | 40% | 模型参数拟合、scaler 和训练侧质量分箱 |
| validation | 10% | epoch 选择、验证 AUC 和训练诊断 |
| calibration | 20% | CDF 映射和阈值拟合 |
| template | 20% | 冻结网格上的模板构建 |
| assessment | 10% | 分析冻结后的独立 assessment |

哈希对象是物理事件组而不是来源行，因此同组的重复来源行始终进入同一角色。代码还验证同一组不能同时具有不同 label。

assessment 的身份 envelope 会参与总体和角色完整性验证，但在默认加载中，其 payload 在 JSON decode 前被跳过。只有存在与 protocol 和 freeze artifact 绑定的 frozen-analysis evidence 时，读取器才允许解码 assessment payload。

## 9. Prepared artifact 与加载验证

### 9.1 `events.jsonl` 格式

prepare 写出 `h4l-events-v1` JSON Lines：

- 第一行是 header，记录 dataset、`source_kind`、`mc_only`、protocol digest 和 source evidence；
- 后续每行由 `identity envelope<TAB>feature payload` 构成；
- 文件写入过程中同步计算 SHA256 和字节数；
- run manifest 绑定文件摘要、population ID、协议、来源和软件环境。

identity 与 payload 分离，使读取器能够先验证 dataset/split/role，再决定是否解码 assessment payload。payload 不允许覆盖任何 identity 字段。

### 9.2 下游加载时的复验

`load_research_data()` 会再次验证：

- header schema、dataset、MC provenance 和 protocol digest；
- 每行 identity 的 exact keys、split 和 dataset；
- role hash、身份唯一性、事件组 role/label 隔离；
- engineered19、`m4l`、`y4l` 和三类权重字段存在且有限；
- 所有 `m4l` 位于 protocol 的半开质量区间；
- `sampling_probability` 和 `yield_weight` 可由 protocol 与 `physical_weight` 精确复算；
- population ID 与已发布总体一致。

已发布 run 每次作为下游输入读取时，还会先由 artifact reader 验证 manifest 登记的文件 SHA256 和大小。

## 10. G0/P0 训练前门禁

prepare 对 assessment 之外的 train、validation、calibration 和 template，分别按 label 计算事件组统计：

- signed yield；
- positive/negative weight sum；
- negative fraction；
- `sum_abs_weights`；
- 分组 `sumw2`；
- signed/absolute effective count；
- cancellation ratio `rho = |sum(w)| / sum(|w|)`。

每个 role/label 必须满足 protocol 中的正 signed yield、最小 `N_eff_signed` 和最小 `rho`，否则 G0 状态为 `insufficient_statistics`。受控 MC 还要求 P0 evidence 完整绑定 processes、units、four-vectors、pairing、weights 和 selection 的独立审计。

训练入口会重新要求 prepared run 的 G0/P0 门禁通过；不会因为能够读出事件表就直接开始拟合。

## 11. 模型训练前的数值预处理

workflow 只把 `role in {train, validation}` 的行传给 `train_discriminant()`。模型函数再次检查：

- 输入非空且只含允许角色；
- dataset 和 label 合法；
- 必需特征与 `physical_weight` 有限；
- 每个 event group 不跨 role 或 label；
- train 和 validation 中 signal/background 都有正的 absolute effective weight。

### 11.1 特征标准化

标准化统计量只在 train 角色上计算：

```text
mean_j  = mean(x_train,j)
scale_j = std(x_train,j, ddof=0)
z_j     = (x_j - mean_j) / scale_j
```

零方差特征的 `scale_j` 被置为 1。validation 使用同一组 train mean/scale，不参与 scaler 拟合。模型 artifact 保存特征名、mean 和 scale，使预测阶段可以重放同一变换。

这一步的目的不是事件筛选，而是统一不同量纲、改善优化稳定性，并避免 validation/assessment 统计量泄漏到模型输入变换。

### 11.2 优化器权重

训练损失使用：

```text
w_abs = abs(physical_weight)
optimizer_weight_i = w_abs_i / mean(w_abs | class_i)
```

signal 和 background 分别按 train 角色中的类别平均绝对权重归一化。验证 AUC 使用 `abs(physical_weight)`，物理产额报告仍使用 signed weight；两者不能混用。

### 11.3 对抗质量分箱

对于 `M6` 和 `M3-fixed200`，代码用 train-background 的 `abs(physical_weight)` 拟合 10 个内部分位点，形成 11 个 `m4l` bins。重复边界、空有效 bin 或缺少有效类别会在优化前以 `insufficient_statistics` 停止。

这些分箱属于训练侧预计算，不会改变 prepared event population，也不会读取 validation 或 assessment 来拟合边界。

## 12. Filter 分类总结

| 类型 | 是否删除事件 | 示例 |
|---|---:|---|
| 来源总体 filter | 是 | development-only 排除历史 test entries |
| 物理事件 selection | 是 | trigger、ID、isolation、impact parameter、SFOS/Z/m4l cuts |
| 终态 filter | 是 | 只保留 `2e2mu` |
| 训练角色 filter | 对当前阶段不可见 | train 只读取 train/validation |
| Assessment access gate | payload 不解码 | 未冻结时跳过 assessment payload |
| 结构/数值校验 | 否，直接失败 | 非有限值、重复身份、协议或权重不一致 |
| 诊断 entry limit | 是，但仅限性能诊断 | 每个文件截取前 N 个 eligible entries |
| 标准化 | 否 | train mean/std 的 z-score 变换 |

因此，“当前流程是否 filter 数据”的答案是肯定的；但必须区分科学 selection、总体/角色访问边界、诊断截断和 fail-closed 数据校验。它们具有不同目的，不能统一称为普通的数据清洗。

## 13. 可复现性与已知边界

- 科学阈值来自封存配置和 research protocol，不允许通过普通运行参数修改；
- profile 负责格式和单位差异，domain 负责统一物理选择；
- role hash、特征顺序、protocol digest、population ID 和 artifact SHA 共同绑定处理结果；
- prepare、训练和后续阶段必须写入新的 run 目录；
- Windows synthetic tests 只能提供软件证据，不能替代完整 ROOT、独立物理来源或原生 ARM64 权威验证；
- exploratory all-MC 不具有 held-out test 解释；
- `diagnostic_entries_per_file` 产物不是训练输入；
- 当前流程没有缺失值填补、异常值 winsorization、类别过采样或基于观测结果的自适应 cut；不合法输入会失败，物理 cuts 由预先声明的协议决定。

## 14. 实现与相关文档

主要实现：

- `src/higgsml/data.py`：ROOT export、来源总体、角色、权重、G0、序列化和加载验证；
- `src/domain/selection.py`：事件选择 cutflow；
- `src/domain/reconstruction.py`：轻子归一化、SFOS pairing 和四轻子候选；
- `src/domain/features.py`：基础候选特征；
- `src/domain/angular5.py`：Angular5；
- `src/domain/weights.py`：physical event weight；
- `src/higgsml/modeling/representations.py`：研究表示和有序特征集合；
- `src/higgsml/modeling/discriminants.py`：train-only scaler、优化器权重和对抗质量分箱；
- `src/higgsml/workflow.py`：prepare/train 阶段编排和门禁。

相关文档：

- [`research-project.md`](research-project.md)：研究目标、角色和科学解释边界；
- [`../reproducibility/runbook.md`](../reproducibility/runbook.md)：运行命令、阶段和 artifact 使用；
- [`software-design.md`](software-design.md)：软件组件与隔离设计；
- [`../../config/protocols/h4l_selection_v1.yaml`](../../config/protocols/h4l_selection_v1.yaml)：H4l 选择阈值；
- [`../reproducibility/artifact-schema.md`](../reproducibility/artifact-schema.md)：通用 artifact 与完整性契约。
