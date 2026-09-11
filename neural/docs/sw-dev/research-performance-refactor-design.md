# H4l Research 代码重构与性能优化修改方案

状态：方案草案，尚未实施。日期：2026-09-11。

分析基线：`66784d3af0a4b73c6001acc94404da3540040866`。范围：`neural/src/research/`，以及直接调用该模块的研究 CLI 和相关测试。本文依据循环分析和关键实现复核制定；优先级是工程判断，性能收益须由基准验证，不代表已经完成全量 profiling。

## 1. 目标与边界

减少 ROOT 单事件读取、重复 DataFrame 扫描与分组、重复模板构造和重复数值拟合；降低 JSON 序列化与中间矩阵的峰值内存。优化后的输出仍须遵守现有科学协议、事件组统计、随机预算和 artifact 契约。

科学边界以 [Neural AGENTS](../../AGENTS.md)、[H4l 研究方案](../research/H4l-Research-Project.md) 和绑定协议为准；软件边界参考 [研究软件设计](research-software-design.md) 与 [Artifact 契约](artifact-schema.md)。历史分类器和研究模型的特征规则分别适用，不因本方案改变。

本方案不授权打开 held-out 数据、不调整科学阈值、不减少训练/toy 预算，也不覆盖 frozen 或 failed run。性能验证使用 synthetic 和获准的 development MC；assessment 路径通过合成数据验证，真实 assessment 仍服从既有冻结访问流程。

## 2. 修改范围与优先级

P0 为当前 prepare 首要问题；P1 为高潜在收益；P2 为内存和辅助流程改进；P3 为保留或按 profiling 决定的小循环。

| 优先级 | 位置与函数族 | 拟修改内容 | 主要验证点 |
|---|---|---|---|
| P0 | `data.export_research_data` | identity 预筛选、连续 development 区间读取、限制分块大小、复用 identity | payload 请求区间无 test，entry 身份及事件顺序一致 |
| P1 | `discriminants.train_discriminant`、`_diagnostics` | tensor/mask/bin 缓存；质量箱诊断批量聚合 | 每 epoch 指标、最佳 epoch、checkpoint 和随机流 |
| P1 | `calibration._moments`、`fit_calibration` | group/bin 编码与充分统计；增量合箱 | multiplicity、跨 score-bin 拒绝、合箱与 mapping |
| P1 | `calibration.apply_calibration` | 事件维插值向量化 | 端点、tails、单 slice、输出与 threshold |
| P1 | `templates.build_templates`、`common_mass_grid` | 复用 group-bin 统计，公共网格增量合并 | 完整协方差、组并集计数、issues 与 merge history |
| P1 | `inference.profile_interval`、`run_asimov`、`run_toys` | 同一 data 共享无条件 MLE，分别求各置信区间 | 求解状态、边界、区间与失败传播 |
| P1 | `inference.run_t2_procedure`、`assessment.run_assessment_t2` | 缓存固定输入；预生成随机任务；outer replica 并行 | RNG 消费顺序、每 replica 重新校准、结果顺序 |
| P1 | `assessment._joint_mother`、`infer_assessment` | 缓存评分/category 数组、模型与 aux 布局；拟合并行 | paired observations、model/mapping 绑定、active bins |
| P1 | `stress.build_stress_templates`、`assessment.run_assessment_stress` | nominal 统计复用，down/up 在固定编码上重加权 | nominal 来源验证和 endpoint 数值 |
| P2 | `inference.paired_event_toys` | 缓存 cell 到候选 bin 的投影 | pairing、整数计数、内存上界 |
| P2 | `data.write_research_data`、`load_research_data` | 流式行对象、分块缓冲，减少完整 records 副本 | identity 先解析、JSON 格式、数值类型、行序 |
| P2 | `data.role_for_group` 的调用层 | 唯一 physical group 只计算一次角色 | 分区 hash、重复组角色一致 |
| P2 | `workflow._population_id` | 复用安全读写过程累计的 physical-group 集合 | 去重后排序的原始摘要语义 |
| P2 | `matrix_element.export_me_inputs`、`import_me_results` | 减少 records 副本，复用 event 索引 | 四轻子校验、逐事件 digest、精确覆盖 |
| P2 | `workflow._supplement_me_bundles`、`_score`、`assessment._scores` | 按 binding 索引补充结果；同一次调用内复用 ME lookup | 缺失、冲突、未使用补充项仍报错 |
| P2 | `workflow.execute`、`inference.build_model` | 调用范围内缓存已验证输入与模型 | 缓存失效、最终完整性检查、阶段隔离 |
| P3 | `data.audit_g0`、`calibration.constrained_distribution`、`bootstrap_calibration` | 默认保留固定小循环 | 审计与主动集规则 |
| P3 | `templates.gate_g1`、`protocol._grid`、`validate_protocol`、`_unique_object` | 保留科学门禁和配置检查 | 拒绝行为不变 |
| P3 | `stress.build_stress_model`、`sample_auxiliary`、`diagnostics.signed_mu_fit` | sample 循环保留；必要时缓存 metadata | auxiliary 分布、参数排列、求解定义 |
| P3 | `reporting.main_comparison` | records 很大时预建复合索引 | 重复/缺失候选和全部配对 seeds |
| P3 | `reporting.exact_shapley`、特征组合、coverage/pull 汇总和 learning curves | 保留固定组合与线性汇总；绘图按测量决定 | 16 子集完整性、失败样本计数 |
| P3 | `artifacts.ResearchRun`、相关校验推导式 | 保留生命周期和发布检查 | 文件摘要与事务状态 |
| P3 | `representations`、`workflow.expected_candidates` | 保留固定特征组和候选枚举 | 特征顺序、候选身份 |

## 3. ROOT prepare 读取重构

### 3.1 现状与成本模型

`export_research_data` 先整列读取 event/channel identity，随后逐 entry 判断 split，对每个 development entry 调用 `tree.arrays(entry_start=i, entry_stop=i+1)`。大量调用重复承担分支选择、读取调度、数组解释和对象分配成本；底层 basket 是否重复解压取决于缓存与 uproot 实现，需要单独测量。选择和特征重建也有逐事件成本，不能把总耗时全部归因于磁盘 I/O。

此前分析提及的两个文件合计 718,995 entries、development 约 80% 仅用于量级说明，实施时须重新绑定输入清单核实。如果 split 在 entry 顺序上近似随机，development 连续段期望约为 `p + (N-1)p(1-p)`；p=0.8 时约有 11.5 万段，平均每段约 5 个 development entry。因此，合并连续段不保证把请求降至几十或几百次，也不保证总时间按请求数同比下降。

### 3.2 设计

1. 保留 schema/count/DSID 检查和 identity 读取，按原算法计算每个 entry 的 split。
2. 用一个独立纯函数生成最大连续 development 半开区间；按资源配置上限切分长区间，禁止跨 test 间隙合并。
3. 每次读取一个合法区间，payload 分支排除已经拥有的 event/channel identity；从 identity 数组补回原事件字段。
4. 在区间内保持 entry 升序，先继续复用 `select_event`、特征与角变量构造。保持 `file_id:entry` 的身份和错误顺序。
5. 测量区间读取收益后，再评估只读任务进程池。每个 worker 自行打开 ROOT 文件，禁止跨进程共享 reader；父进程按 source/entry 顺序汇总并独占发布。

拟新增内部接口：`development_spans(mask, max_entries)` 和 `iter_development_events(...)`，名称在实现时依现有分层确定，不作为已发布 API。

安全验收首先监视应用层所有 payload `arrays` 请求的 entry 范围，断言不含 test。由于 ROOT basket 的物理边界可能跨 split，还须核实绑定 uproot 的解释/解码行为是否满足现有访问契约；不能把“返回数组已过滤”直接当作底层未解码的证据，也不能引入整块 payload 解码后过滤的实现。

## 4. 校准与模板统计层

### 4.1 统计表示

提取只处理已获准输入的内部统计组件，复用 event-group 编码、质量箱、score 箱和 category 编码。不要强行统一 calibration 与 template 的权重公式：前者有 target 和 bootstrap multiplicity 语义，后者保留 yield-weight 完整协方差。

模板定义 `G[g,b]` 为物理组 g 在 bin b 的 signed yield-weight 总和：`yield = sum_g G`，`C = G.T @ G`，`variance = diag(C)`。此外保存逐行绝对权重和正负权重累计，以及 group/bin 占用关系；signed 权重抵消为零的组仍可能占用 bin，不能通过 `G != 0` 推断组计数。

选择 dense 或 sparse 表示前，测量 `组数 × bin 数 × 元素字节数` 和稀疏度，设置内存预算。最终 artifact 仍输出当前契约要求的完整协方差。

### 4.2 增量合箱

用固定映射矩阵 A 表示旧箱到新箱的合并：`G_new = G @ A`，`C_new = A.T @ C @ A`。合并两个箱时，新方差是 `v_a + v_b + 2*C[a,b]`，不能仅相加方差。

绝对、正、负逐行权重统计可以相加；group count 必须按两箱组集合的并集计数。category-major 的 flatten 顺序、结构零支持、process 排列和 active bins 按原规则更新。

`common_mass_grid` 每轮仍检查所有候选，严格选择原实现的最左失败质量箱，并按原规则删除边界；仅替换统计构造成本。不能预先批量删除所有失败边界。

### 4.3 校准增量计算与插值

`_moments` 先按物理组聚合权重，再计算平方和与 multiplicity 修正；禁止改为逐行 `sum(w*w)`。拟合层缓存初始质量箱统计，合并时重新组合组权重并复核“同物理组跨 score-bin”的拒绝规则。原先分居不同质量箱的组在合箱后可能触发该规则，不能只检查一次初始网格。

`apply_calibration` 可先保留少量 slice 的 score 插值循环，用 `searchsorted` 为全部事件定位相邻质量中心并批量插值；需要限制 `slice_count × event_count` 中间数组内存，可按事件分块。复现两端常值外推、单 slice、边界相等和浮点行为。

## 5. 训练循环重构

在训练开始前构造所需 tensor、标签 mask 和 mass-bin 索引；batch 内直接 tensor 索引，减少 Python、NumPy 和 Torch 之间转换。`_diagnostics` 用批量箱统计替换反复全数组扫描。

保留每 epoch validation AUC、现有 early stopping 和详细历史要求；详细模式规定的完整训练集评分与每 epoch threshold 重算不能降频。200 epoch 上限、batch size、排列生成、归一化和模型架构不作为资源优化项。

候选/seed 训练进程并行后，每任务独立设置原有随机生成器，限制 worker 内 Torch/BLAS 线程，记录资源配置。GPU、混合精度、批量大小和新优化器不纳入本次等价改造。

## 6. 推断与 T2 重构

### 6.1 多区间共享拟合

拟新增 `profile_intervals(model, data, levels)`：共享参数布局、输入准备和一次无条件 MLE，然后按原 confidence 顺序分别进行 fixed-POI 拟合与根搜索。现有 `profile_interval` 保留兼容包装，输出 schema 不变。

无条件拟合失败时，各区间按既有失败契约报告；单一区间根搜索失败不能掩盖其他区间结果。保留边界和 nuisance 配置。收益约为每份 data 少一次无条件拟合，不等于推断时间减半。fixed-POI warm start 为后续实验项，需先验证优化器收敛与失败行为，默认不启用。

### 6.2 确定性并行

优先一次只启用一个并行层：普通 inference 按 toy，T2 按 outer replica，训练按候选/seed。避免外层 worker 再创建内层 worker 导致 CPU 与内存超额占用。

随机任务按现有串行逻辑生成和编号，包括 observation、auxiliary draws、bootstrap multiplicity 和 inner seed。worker 执行固定输入的计算，父进程按任务编号收集；缓存、日志与 manifest 发布均由父进程控制。预生成采用有界队列，不能一次保留所有 replicas 的大数组。

T2 仅缓存不随 replica 改变的特征和模型输入；每 replica 仍重新拟合 calibration、threshold 和对应 template。模型输出是否可缓存须证明其不依赖重采样权重，并校验 event/model identity。消除按对象身份进行的线性反查时，使用任务内显式 key 或身份索引。

### 6.3 配对与 stress

为 paired toys 缓存 cell 到各候选 bin 的投影，保留整数计数、候选排序和 pairing identity。先测量投影矩阵内存，必要时使用稀疏或分块累计。

stress 在固定 group/bin 编码上分别累计 nominal/down/up 权重；nominal 来源一致性仍必须验证。若变化影响事件归类或支持域，不能复用旧编码。aux 参数布局与模型可在同一次计算内缓存，缓存 key 绑定 template、stress 和后端配置。

## 7. 数据流、缓存与 artifact

JSONL 写入使用逐行对象和有界缓冲，避免完整 `to_dict(records)` 副本。加载时先解析 identity envelope，依据现有访问规则决定是否解析 payload；不可整体加载后筛选。下游仍需要完整 DataFrame 时，应明确最终内存不会随分块加载而消失。

population ID 可以随原有安全扫描累计，但必须保留“physical groups 去重、排序、按原结构编码再摘要”的算法，不能换成按文件顺序的流式 hash。ME 的四向量、digest、重复/缺失行和 binding 校验保持完整。

缓存默认只存活于单次阶段调用，key 至少覆盖被缓存值实际依赖的输入、模型、mapping、grid、target 和 replica 身份。可变对象不在候选间共享；缓存设内存上限。文件完整性检查不能用仅 stat 命中的缓存替代，发布前按原逻辑重新验证。

资源选项放在 run configuration，建议包括 worker 数、每 worker 线程数、读取块上限和内存预算；具体名称随接口设计落地。资源与性能记录不参与既有科学身份计算，也不能擅自删减原 manifest 字段。

## 8. 等价性、基准与验收

### 8.1 等价性分级

| 类别 | 要求 | 不满足时的处理 |
|---|---|---|
| 离散语义 | 行序、组身份、候选序、分区、随机输入、合箱历史、状态完全一致 | 阻止替换，定位行为改变 |
| 科学数值 | 保持现有容差；对强抵消、阈值附近、区间边界重点比较 | 实验前约定容差，不根据结果放宽 |
| 序列化身份 | 内容相同的科学 payload 及其 digest 一致；完整 run manifest 可因软件记录变化而不同 | 不伪造旧 ID，不将“近似一致”冒充同一 artifact |
| 平台复现 | 同平台串行/并行对照；Windows 与锁定 ARM64 分别记录 | Windows 结果不替代 ARM64 权威验证 |

浮点加法顺序变化不必然意味着科学协议必须修改；但必须记录实现版本、产生新 artifact identity 和新 run，并证明科学选择未变。凡涉及科学规则改变或现有协议明确限制的事项，按该协议的变更流程处理。

### 8.2 测试矩阵

| 范围 | 必测样例与断言 |
|---|---|
| ROOT | 全 development、全 test、交替 split、首尾单事件、重复 physical group、多文件；捕获全部 payload 请求并验证范围、行序和身份 |
| 校准 | signed cancellation、multiplicity、重复组、合箱后跨 score-bin、空箱、tails；比较 y/v/neff、状态、mapping 和 threshold |
| 模板 | 同组跨相邻箱、同箱正负抵消但仍占用、结构零、失败箱与多候选；比较 covariance、group count、active bins 和 merge history |
| 训练 | 固定 seed 的完整小样本历史；每 epoch AUC/threshold、最佳 epoch、模型状态和随机排列 |
| 推断 | 内点、边界、MLE 失败、单一区间失败、多 nuisance；比较 68%/95% 区间、状态及无条件拟合次数 |
| T2/并行 | worker=1 与多 worker、任务乱序完成、worker 异常；随机输入、replica 重拟合次数、输出顺序、失败发布语义 |
| 序列化/ME | round-trip、identity 拒绝、缺失/重复事件、绑定不匹配；科学 payload 与 digest |

使用独立期望值或现有实现的固定基线做对照，避免只测试优化实现的内部步骤。针对性测试通过后，从 `neural/` 按项目要求执行 `conda run -n pytorch python -m pip check` 和 `conda run -n pytorch python -m pytest -q`；权威平台另行验证。

### 8.3 性能测量

记录 wall time、CPU time、峰值 RSS、输入大小、ROOT 请求数及区间长度分布、groupby/template 构造次数、无条件/fixed-POI 拟合次数、worker/线程数和软件版本。prepare 分开计时 identity、payload、选择、特征和写入；推断区分模型构造、MLE、根搜索。

基准使用固定 synthetic 与绑定 development 数据，区分冷/热缓存，短基准至少重复三次报告中位数及范围。计时使用单调时钟；progress 日志按时间或块输出，不逐事件打印。性能报告不记录受限 payload。

验收先满足科学与访问契约，再比较性能：目标操作调用数确实下降、代表性端到端耗时超过测量波动的改善、峰值内存不超配置预算。无稳定收益的改造不默认启用。速度倍数和内存目标应在基线测得后填写，本文不承诺未经测量的加速比。

## 9. 分阶段交付与回退

| 阶段 | 交付边界 | 前置依赖与退出条件 |
|---|---|---|
| A | 基线、关键阶段计时、独立黄金样例 | 可重复测量；科学与性能结果分开记录 |
| B | ROOT 合法区间读取，先串行 | 请求范围验证、事件级一致性、实际 spans 与吞吐报告 |
| C | 校准插值和训练 tensor/诊断优化 | 独立小改动逐项验证，完整训练历史对照 |
| D | 统计组件、模板/校准增量合箱、stress 复用 | 先验证统计组件，再接调用层；协方差与合箱身份通过 |
| E | 多置信区间共享 MLE | 兼容原入口；失败路径和数值对照通过 |
| F | 有界确定性并行 | 串行基线稳定；单层并行、内存及异常回收通过 |
| G | JSONL、population ID、ME 与局部缓存 | 身份摘要、事务与加载边界通过 |

每阶段可独立评审和回退，避免一次替换全部热点。串行路径作为初期基准与故障回退；旧实现若临时保留，限定为测试 oracle 或过渡入口，防止长期出现两套科学逻辑。部署采用新版本、新 run 路径；失败时回退代码或资源配置后创建新 run，保留失败证据，不重写已发布文件。

最终交付包括实现与测试、接口/资源配置说明、绑定版本的性能对照和科学一致性记录。本方案仅交付设计文档；实际代码重构、性能测量与科学验证状态仍为未实施。
