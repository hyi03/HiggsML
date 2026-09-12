---
document_id: h4l-compact-kinematics-sample-efficiency-development-plan
status: development-started-m1-software
date: 2026-09-12
research_basis: ../research/H4l-Compact-Kinematics-Sample-Efficiency.md
scope: MC-only educational/technical research software
---

# H→ZZ*→4ℓ 紧凑运动学表示与样本效率：代码开发方案与实施计划

## 1. 文档目的与状态

本文把 [`H4l-Compact-Kinematics-Sample-Efficiency.md`](../research/H4l-Compact-Kinematics-Sample-Efficiency.md) 的研究目标转换为可实施、可测试、可审计的软件开发方案。本文描述的是**拟开发能力**，不是当前代码已经具备的能力。

开发已从 [Sprint M1-01](../3-Plan/Done/sprint-m1-01.md) 启动并完成首个软件交付：严格 overlay、compact freeze payload 与旧行为 characterization。正式科学预注册仍 pending；M2—M7 尚未启动。本计划以下完整链路仍是目标，具体已实现契约见 [artifact schema §7](artifact-schema.md#7-样本效率元数据契约)，评审/测试/提交状态以 Sprint 记录为准。

目标是在不改变现有发现批次、历史分类器和 assessment 访问约束的前提下，新增以下完整链路：

1. 冻结一个由发现阶段产生的紧凑表示候选；
2. 对 train 角色生成事件组级、分层且嵌套的训练子集；
3. 对 `decay7`、冻结紧凑候选和 `engineered19` 执行配对训练样本量实验；
4. 聚合随实际训练事件组数变化的 W68、相对 W68、AUC、失败率和分层不确定性；
5. 在独立确认总体上执行预注册非劣性检验；
6. 以受限 raw/CDF 对照检查结论对质量条件校准的依赖。

本方案严格属于 MC-only educational/technical research。它不能产生 ATLAS/CMS 结果、Higgs discovery 或真实数据物理测量，也不授权读取任何真实数据或历史 held-out test 特征。

## 2. 范围与非目标

### 2.1 本期范围

- 复用当前 `src.research` 的数据角色、表示定义、普通 MLP、校准、共同模板、T1 推断和不可覆盖 artifact；
- 新增独立、严格校验的样本效率实验协议；
- 新增训练事件组子集计划 artifact，并把其身份绑定到模型及所有下游产物；
- 新增三表示学习曲线批处理、配对汇总、绘图和机器可读报告；
- 新增紧凑候选冻结与独立确认守卫；
- 增加一个预注册、有限的容量对照，不开放观察结果后的架构搜索；
- 保持旧协议、旧 run 和现有命令的读取兼容性。

### 2.2 明确不做

- 不把 A/B/C/D 的 15 个非空组合全部扩展到样本量网格；
- 不以 assessment 指标选择候选、样本比例、网络、容差、分箱或 CDF 网格；
- 不把当前按 epoch 绘制的 `learning-curves.png` 改名后当作样本效率曲线；
- 不修改历史 `higgsml-train` / `higgsml-test` 的固定 15 特征、安全门或 test-opening 规则；
- 不允许普通运行配置承载科学规则；路径、进程数和线程数仍是资源配置，样本比例、种子、判据和确认策略必须进入版本化协议；
- 不在观测样本量范围之外外推“可节省多少倍 MC”；
- 不用重复训练同一个 100% 子集冒充训练子集抽样不确定性。

## 3. 当前代码基线与目标关系

当前代码已经实现了课题的大部分“固定分析链”，但尚未实现“训练样本量是受控实验变量”。课题与现有神经网络训练的关系可概括为：**网络本体继续作为固定测量工具，主要开发工作发生在训练数据身份、实验编排、统计汇总和确认边界上。**

| 研究需要 | 当前实现 | 差距与开发结论 |
|---|---|---|
| 可变输入、共同 `m4l` 条件 | `src/research/representations.py` 和 `ResearchClassifier` 已支持 `decay7`、`engineered19`、A/B/C/D 子集及可变输入维数 | 直接复用；样本效率主实验不新增表示搜索 |
| 固定 MLP 与五网络种子 | `train_discriminant()` 固定网络、训练预算和种子 42—46 | 复用训练主体；需增加训练子集参数和 artifact 身份 |
| train-only 拟合统计 | scaler、类别绝对权重均值、训练质量分箱均在 train 上拟合 | 正确基线；子抽样后必须只在所选 train 子集内重拟合 |
| 事件角色隔离 | train/validation/calibration/template/assessment 已分离，assessment 有 durable one-shot claim | 保持；学习曲线不得缩小非 train 角色，确认不得破坏 claim-before-decode |
| 15 组合发现 | `scripts/h4l_run.py` 固定对每个种子训练 M0c、M2、M3 和 15 个组合 | 作为候选发现输入；不修改其批次含义 |
| 训练诊断曲线 | `reporting.write_learning_curves()` 绘制指标随 epoch 的变化 | 保留原名和语义；新增独立的 `sample-efficiency-curves.*` |
| 共同校准、模板和 T1 推断 | `calibrate`、`templates`、`infer` 已实现 raw/CDF、带符号模板和 pyhf 推断 | 复用计算；必须扩展候选 key 和 lineage，避免不同样本量单元冲突 |
| W68、Shapley、二阶差分 | 当前报告可按网络种子汇总发现阶段结果 | 学习曲线需新增按样本比例、抽样种子、网络种子配对的聚合器 |
| 不可覆盖 run artifact | `research-run-v1`、manifest-last、上游摘要绑定已实现 | 复用事务；新增正式 payload schema，科学身份不能只写入自由 `context` |
| 训练样本量学习曲线 | 当前训练总是使用完整 train 角色 | 完全缺失；需先生成可审计的训练子集计划 |
| 独立非劣性确认 | 当前 freeze/assessment 面向既有研究候选矩阵 | 需新增候选冻结、容差和确认总体独立性契约，不能复用已消耗的确认身份 |

当前 `scripts/h4l_run.py` 每个网络种子执行 18 次训练和 20 次校准，五种子合计 90 次训练。它回答的是完整组合发现与归因问题，不回答训练事件组数量 `n` 改变时的样本效率问题。

## 4. 总体架构

新增链路采用“科学协议、事件组子集、单模型训练、共同评价、聚合确认”五层结构：

```text
Base ResearchProtocol + prepared artifact + compact-candidate freeze
                              |
                              v
                 SampleEfficiencyProtocol freeze
                              |
                              v
                 training-subsets artifact
              (draw seed × fraction × label)
                              |
                              v
        representation × fraction × draw × network seed
                     model artifacts v2
                              |
                              v
           raw calibration -> batch-wide common template
                              |
                              v
                       T1 model-self inference
                              |
                              v
          paired aggregation + uncertainty decomposition
                              |
             +----------------+----------------+
             |                                 |
       restricted CDF check          independent confirmation
```

设计原则如下：

- 子集成员资格先生成、后训练，训练函数不得临时随机抽样；
- 三种表示在同一实验单元使用完全相同的物理事件组；
- validation、calibration、template 和 assessment 始终保持完整；
- 每个随机性来源有独立 seed 字段，不能复用一个 `seed` 表示多种随机性；
- 计划项即使失败也进入 ledger 和报告，不补抽、不删除；
- 发现、学习曲线和确认使用明确的 population lineage，不以换网络种子恢复数据独立性。

## 5. 协议设计

### 5.1 保持 ResearchProtocol 不变

当前 `src/research/protocol.py` 对 `h4l-research-v1/v2/v3` 使用严格键集合校验。现有版本继续定义数据角色、质量支持、训练主体、校准、模板和推断规则。不得向旧版本静默加入学习曲线字段，也不得放宽未知字段拒绝逻辑。

### 5.2 新增 SampleEfficiencyProtocol

新增 `src/research/sample_efficiency_protocol.py`，定义独立 schema `h4l-sample-efficiency-protocol-v1`。该协议是现有 ResearchProtocol 的严格 overlay，而不是替代品。其冻结实例至少包含：

| 字段 | 含义与校验 |
|---|---|
| `schema_version`、`protocol_id` | 非空、版本化、不可复用 |
| `base_research_protocol_sha256` | 精确绑定完整 ResearchProtocol canonical digest |
| `prepared_artifact_id`、`population_id` | 绑定发现或学习曲线总体，禁止跨 prepared run 套用 |
| `compact_candidate_freeze_artifact_id` | 唯一绑定冻结候选、输入顺序和选择历史 |
| `representations` | 精确为 `decay7`、一个冻结 compact、`engineered19`；不得在运行时增删 |
| `sample_fractions` | 严格递增，默认候选值 `[0.25, 0.5, 1.0]`，正式运行前冻结 |
| `sample_draw_seeds` | 独立于网络种子；数量及值冻结 |
| `network_seeds` | 初始为 `[42, 43, 44, 45, 46]` |
| `subset_algorithm` | 算法 ID、事件组单位、按 label 分层、排序摘要、舍入规则和嵌套规则 |
| `primary_metric` | `W68_Asimov_mu1_T1`，并明确越小越好 |
| `pairing_keys` | 固定为 fraction、draw、network seed；100% 端点采用特殊规范化 |
| `noninferiority` | `delta_w68`、置信水平、区间算法、bootstrap 单位/次数/种子和判定方向 |
| `capacity_control` | 是否执行、确定性宽度规则、运行样本点；不能接受任意候选列表 |
| `cdf_check` | 冻结表示和样本点；默认只做精简端点检查 |
| `assessment_access` | 发现/学习曲线禁止 assessment；确认要求独立 population 和新 claim namespace |
| `failure_policy` | 失败保留、不重抽、不插补、不把缺失配对当有效结果 |

路径、output root、worker 数、worker 内线程数和进度显示不进入该科学协议，继续放入严格的 run config。

### 5.3 紧凑候选冻结 artifact

新增 `h4l-compact-candidate-freeze-v1` payload。冻结动作只接受显式候选，不负责从报告中自动选“赢家”。至少记录：

- 发现 prepared artifact、发现报告和所有选择依据的 artifact ID；
- 候选表示 ID、A/B/C/D 组、有序输入和实际输入维数；
- 候选选择规则版本、已浏览数据历史和探索性状态；
- `engineered19` 参考表示身份；
- 非劣性容差 `delta_w68` 的来源说明；
- 用于后续独立确认的 population 排除集合；
- canonical payload digest 和冻结状态。

若候选未冻结，样本效率计划以 `compact_candidate_not_frozen` 具名终止。发现报告不得被直接当作候选 freeze。

## 6. 训练子集计划

### 6.1 为什么必须是一级 artifact

如果 `train_discriminant()` 在每次调用时自行抽样，将无法可靠证明三种表示使用相同事件组，也无法区分子集种子和网络种子，失败后的“再跑一次”还可能无意中改变样本。因此先发布训练子集 artifact，再允许训练。

拟新增 `src/research/training_subsets.py`，只读取 prepared artifact 中 train 角色的身份和必要统计，不读取 assessment payload。

### 6.2 确定性嵌套算法

对每个 `sample_draw_seed`：

1. 校验同一 `event_group_id` 的 dataset、role 和 label 一致；
2. 按 label 分层收集 train 事件组；
3. 对每个事件组计算 SHA-256 排序键：

   ```text
   canonical(base_protocol_id,
             prepared_artifact_id,
             subset_algorithm_id,
             sample_draw_seed,
             label,
             event_group_id)
   ```

4. 每个类别按 `(hash, event_group_id)` 稳定排序；
5. 对比例 `f < 1` 取前 `floor(f × N_label)` 个组，对 `f = 1` 取全部组；
6. 不足一个有效类别、权重支持或预注册质量支持时记录 `training_subset_insufficient_statistics`，不改变舍入规则、不重新抽样；
7. 使用排序前缀保证同一 draw 内 `25% ⊂ 50% ⊂ 100%`；
8. 三种表示只引用同一个 subset ID，不各自生成成员资格。

子集选择单位始终是 `event_group_id`，一个组的所有来源行共同进入或离开。算法不得按行采样。

### 6.3 100% 端点去重

100% train 集合不随 `sample_draw_seed` 改变。计划 artifact 可为每个 draw 记录其嵌套家族指向同一 `full_subset_id`，但执行器只训练一次 `(representation, 100%, network_seed)`。完全相同数据和网络种子的重复运行只能作为确定性诊断，不能作为训练子集波动样本进入科学汇总。

若有 5 个子集抽样种子、3 个比例、3 个表示和 5 个网络种子：

- 朴素重复计划为 `3 × 3 × 5 × 5 = 225` 次训练；
- 对 100% 端点规范化去重后为 `3 × (2 × 5 + 1) × 5 = 165` 次科学训练。

执行计划和报告必须同时给出 planned、deduplicated、completed、terminal-failed 数量。

### 6.4 Artifact 内容

一个 `training-subsets` run 发布：

- `training-subsets.json`：schema、协议绑定、总体摘要、每个计划单元的状态和摘要；
- `training-subset-membership.jsonl`：规范化的 `draw_seed`、fraction、label、event_group_id 和 membership hash；
- `training-subset-ledger.json`：所有预定单元及其 planned/terminal 状态；
- manifest：prepared artifact、base protocol、sample-efficiency protocol 和 compact freeze 的上游绑定。

每个子集摘要至少含目标比例、实际组数/行数、每类组数/行数、`sum_abs_weight`、`sum_signed_weight`、`sumw2`、有效统计、质量支持摘要和 membership digest。读取器必须逐文件验证 manifest receipt，并重算 membership digest。

## 7. 训练接口与模型 artifact 扩展

### 7.1 接口变更

`train_discriminant()` 增加一个结构化、可选的 `training_subset` 参数；旧调用不传时保持完整 train 行为。新路径必须：

1. 先验证 subset artifact 的 protocol、prepared artifact、population 和算法绑定；
2. 只对 frame 中 `role == train` 的事件组应用成员资格；
3. 明确拒绝 subset 中出现 validation/calibration/template/assessment 组；
4. 保持 validation 完整，不允许通过同一参数缩小；
5. 在筛选后的 train 上重新拟合 scaler、类别权重均值、训练质量分箱和训练阈值；
6. 对实际成员资格重算摘要，并与 subset artifact 比较；
7. 任何不一致以 `training_subset_binding_mismatch` 终止，不回退到完整 train。

CLI 的 `train` 阶段增加：

```text
--training-subset-run PATH
--sample-fraction FRACTION
--sample-draw-seed INTEGER
```

三个参数只在 sample-efficiency 协议下成组出现。普通 ResearchProtocol 路径不得接受其中任何一个。100% 端点使用协议规定的 canonical draw identity，避免同一模型产生多种等价 key。

### 7.2 `research-discriminant-v2`

新模型 payload 在 v1 字段基础上增加：

- `sample_efficiency_protocol_sha256`；
- `training_subset_artifact_id`、`training_subset_id`、`membership_digest`；
- `sample_fraction_target`、`sample_draw_seed`、`full_endpoint_canonicalized`；
- 实际事件组/行数和逐类别统计；
- `network_seed`，并保留旧 `seed` 的兼容读取；
- `representation_id`、`experiment_cell_id` 和 `pairing_id`；
- 可训练参数量与 `architecture_variant`；
- train-fitted 统计来源明确为该 subset ID。

`predict_discriminant()` 同时读取 v1/v2。v1 artifact 可作为历史完整 train 发现证据，但由于缺少可证明的 subset identity，不能伪装成 25%/50% 样本效率点。只有在协议显式允许的迁移审计中，它才可作为“历史 100% 参考”，且不得进入需要完整配对的主结果。

### 7.3 实验 key 扩展

当前 candidate key 主要由候选、组和网络 seed 构成，会在不同 sample fraction/draw 之间冲突。新 key 必须包含：

```text
representation_id / subset_id / network_seed / transform / architecture_variant
```

校准 bundle、模板、推断和报告均复制并校验同一 `experiment_cell_id` 与 `pairing_id`。下游不得从目录名推断科学身份。

## 8. 批处理编排

### 8.1 独立脚本

新增 `scripts/h4l_learning_curve.py`，保留 `scripts/h4l_run.py` 的发现语义不变。脚本只负责路径解析、完整计划生成、调用应用服务和最终状态检查，科学计算留在 `src/research`。

建议参数：

```text
--config PATH
--sample-efficiency-protocol PATH
--prepared-run PATH
--compact-freeze-run PATH
--gate-run PATH
--t1-validation PATH
--output-root PATH
--resources PATH
--plan-only
--clean
--no-progress
```

`--plan-only` 必须输出协议摘要、训练/校准/模板/推断数量、去重数量、预计最大并发和输出路径，但不创建 run。`--clean` 只删除脚本能够证明属于该批次且位于 `neural/runs/` 下的未冻结目标；不得删除冻结或已发布科学 run。

### 8.2 计划单元

主 raw 批次按以下顺序执行：

1. 校验 base protocol、prepared、G0/G1 gate、compact freeze 和独立性历史；
2. 发布 `training-subsets`；
3. 为三表示、各 fraction/draw、网络种子建立完整 ledger；
4. 训练 planned model，终态失败写入 ledger；
5. 对成功模型执行 raw calibration；
6. 用全部计划内有效候选构建一个**批次级共同质量网格**，保证不同 `n` 的 W68 使用相同模板支持与合并规则；
7. 在同一 T1 规则下执行 model-self Asimov inference；
8. 汇总所有成功、失败和缺失单元；
9. 仅对协议冻结的表示/样本点执行精简 physical CDF 对照；
10. 独立确认作为单独批次和单独 claim 执行，不与发现/学习曲线批次混写。

共同网格若因最弱单元无法满足统计规则，应按照协议产生具名失败或整体终止；不得事后为有利模型改用更细网格。若正式协议决定采用预冻结固定网格而不是全批次共同合并，则必须更换算法 ID 和协议版本，不能由运行时自动选择。

现有 `templates` stage 内含面向原候选矩阵的 G1 `required_minimum`，不能直接用于只有三种表示的学习曲线。新 workflow 只复用 `common_mass_grid()`、分类和模板构建等计算服务，并实现由 SampleEfficiencyProtocol 定义的 `sample_efficiency_completeness` gate；不得删除或放宽旧 G1 要求来迁就新批次。

### 8.3 并发模型

复用 `resources.ordered_map()` 的有序、有界多进程模型：

- 只允许一个并行层；批处理并行时，单次训练/推断内部不得再开进程池；
- worker 初始化时限制 Torch、BLAS/OpenMP 线程为 `worker_threads`；
- 每个 task 创建独立模型、随机数生成器和不可共享的本地状态；
- worker 返回纯结果或临时 payload，父进程按计划顺序发布 artifact；
- 任何 worker 失败映射回确定的 experiment cell，不打乱 ledger；
- Windows 开发验证和锁定 ARM64 权威验证分别记录，不互相替代。

## 9. 样本效率统计与报告

### 9.1 新增聚合模块

新增 `src/research/sample_efficiency.py`，不把新语义塞入现有发现报告函数。输入是完整 planned ledger、模型/校准/模板/推断 artifact，输出 `h4l-sample-efficiency-report-v1`。

主记录按以下键组织：

```text
(representation_id,
 sample_fraction,
 actual_train_group_count,
 sample_draw_seed_or_full,
 network_seed,
 architecture_variant)
```

主比较只在完全匹配的 `(fraction, draw/full, network_seed, architecture_variant)` 内计算：

\[
\Delta W_{68}(R,n)=W_{68}(R,n)-W_{68}(\mathrm{engineered19},n).
\]

缺少任何一侧时记录 `paired_cell_missing`，不得用不同 seed、不同子集或跨 fraction 的结果补齐。

### 9.2 随机性分解

报告层必须把以下来源分开：

| 来源 | 身份 | 软件处理 |
|---|---|---|
| 训练子集波动 | `sample_draw_seed` | 比较相同比例下不同事件组前缀；100% 不估计此项 |
| 网络随机性 | `network_seed` | 同一 subset 上配对比较种子 42—46 |
| 评价事件误差 | `evaluation_resample_seed` | 冻结模型后按 event group 配对 bootstrap，不改变训练或候选 |
| 校准误差 | `calibration_resample_seed` | 仅在协议要求的外层重校准中改变映射，不能复用评价 seed |
| 模板有限 MC | 模板 `sumw/sumw2` 与 shapesys | 继续由带符号模板和 T1 规则传播 |

五个网络种子的标准差不得标为“MC 统计不确定性”。未实施的误差层必须在报告中明确写 `not_estimated`，不能省略。

### 9.3 学习曲线输出

新增：

- `sample-efficiency-records.jsonl`：所有计划单元及状态；
- `sample-efficiency-summary.json`：按表示和实际 `n` 的聚合；
- `sample-efficiency-curves.png`：W68 与相对 W68 随实际 train event-group count 的曲线；
- `sample-efficiency-curves.csv`：图对应的机器可读数据；
- `sample-efficiency-report.md`：协议、完整性、结果边界和失败表；
- `capacity-control.*`、`cdf-check.*`：仅在协议启用时产生。

图的横轴使用实际事件组数而不是只写百分比。误差带/点型应区分子集波动、网络波动和评价误差。所有图表从已发布 JSON/JSONL 生成，不重新计算或筛选实验单元。

### 9.4 目标性能所需样本量

协议可给出一个预注册 `Q*`。只有当观测网格在相邻点间包围 `Q*` 且所选单调插值规则已冻结时，才报告观测范围内的所需事件组数；否则写“在研究范围内未达到”。禁止多项式、幂律或神经缩放律向网格外推 MC 节省倍数。

## 10. 非劣性确认

### 10.1 判据

令冻结紧凑候选为 `C`，完整工程表示为 `F`：

\[
D=W_{68}(C)-W_{68}(F).
\]

只有预注册区间满足

\[
\operatorname{UpperCI}(D)\leq\delta_W
\]

时，状态才是 `confirmed_noninferior_within_registered_margin`。区间跨越 `delta_w68` 时状态为 `noninferiority_unconfirmed`，不能报告“两者相同”。

### 10.2 独立性和访问守卫

- compact 候选、`delta_w68`、置信水平、CI 算法、重采样预算和容量对照必须在确认 payload 解码前冻结；
- 确认 prepared artifact/population 不得出现在 discovery、candidate freeze 或学习曲线 lineage 中；
- 同一批事件换划分、换网络种子或 bootstrap 仍视为同一总体；
- 确认使用独立 claim namespace，claim key 至少绑定 population ID、base protocol、sample-efficiency protocol 和 compact freeze；
- 必须先以 exclusive create 发布 durable claim，再读取 assessment payload；
- claim 后不得回到候选、容差或网格选择；重复只允许完全相同 freeze 和显式 repeat；
- 不满足独立性时以 `confirmation_population_not_independent` 拒绝，而不是降级后继续标记确认。

学习曲线主批次默认只使用 model-self Asimov/T1，不打开 assessment。这样训练样本量结果不会无意消耗确认资源。

## 11. raw/CDF 精简检查

主学习曲线使用 raw 分数。physical CDF 检查只允许：

- 三种预选表示；
- 协议冻结的少量样本点，初始建议为完整训练端点，必要时再预注册一个低样本端点；
- 相同 calibration 角色、质量网格、ties、tails 和失败规则；
- 与 raw 结果相同的 experiment pairing；
- 单独报告接受率命中误差和质量区形变。

不得观察 raw 曲线后临时决定哪些 fraction 做 CDF，也不得扩展回 15 组合全网格。若校准统计主导结论，报告应停止在 `calibration_uncertainty_dominant`，后续另立方法课题。

## 12. 容量控制

当前固定网络参数量为：

\[
P(d)=64d+6657.
\]

因此 `decay7`、AB 和 `engineered19` 的实际输入维数分别为 8、13、20，参数量约为 7169、7489、7937。主结果保留固定网络主体并报告参数量，因为这正是当前流程下的表示比较。

容量对照只增加一个预注册 variant。例如保持后两层为 64、32，只按确定公式选择第一层宽度，使各表示参数量最接近 `engineered19` 主网络；公式、舍入、运行 fraction 和种子必须写入协议。它只用于机制检查，不参与 compact candidate 选择，也不允许从多个宽度中挑最有利结果。

容量对照实现应封装为具名 `architecture_variant`，普通 `higgsml-research train` 仍拒绝任意隐藏层参数，避免把受控对照变成架构搜索入口。

## 13. Artifact 与兼容策略

### 13.1 新 schema

| Schema | 用途 |
|---|---|
| `h4l-sample-efficiency-protocol-v1` | 样本量网格、配对、指标、确认和失败规则 |
| `h4l-compact-candidate-freeze-v1` | 唯一 compact candidate、容差和选择历史 |
| `h4l-training-subset-plan-v1` | 事件组成员资格、嵌套关系和计划 ledger |
| `research-discriminant-v2` | 模型与 subset/cell/参数量的正式绑定 |
| `h4l-sample-efficiency-report-v1` | 完整计划、曲线、配对差、误差层和终态 |
| `h4l-noninferiority-confirmation-v1` | 独立总体、claim、区间和确认状态 |

`research-run-v1` manifest 可继续使用，但必须通过正式 payload 和 upstream receipts 表达科学身份；不能只依赖 `manifest.context`。若 manifest 本身无法表达双协议绑定，再单独设计 `research-run-v2`，并提供只读 v1 reader；不得原地改变 v1 digest 语义。

### 13.2 兼容规则

- 现有 ResearchProtocol v1/v2/v3 和 `research-discriminant-v1` 保持可读；
- 旧 `h4l_run.py` 命令、输出目录和报告字段不变；
- 新 reader 按 schema 分派，未知版本拒绝；
- 缺 subset 字段的旧模型不能补造 draw seed、fraction 或 membership digest；
- 新 artifact 不得作为旧 freeze 的候选矩阵项，除非未来协议显式定义迁移；
- 所有新 run 继续 manifest-last、不可覆盖，并验证上游文件 receipt。

## 14. 具名终态与退出语义

新增状态至少包括：

| 状态 | 含义 | 是否可进入主配对汇总 |
|---|---|---|
| `training_subset_insufficient_statistics` | 预定子集缺类别或有效支持 | 否；保留失败记录 |
| `training_subset_binding_mismatch` | 成员资格、prepared、协议或重算摘要不一致 | 否；输入/绑定失败 |
| `compact_candidate_not_frozen` | 未提供唯一冻结候选 | 否；批次不得启动 |
| `paired_cell_missing` | 比较的一侧缺少相同配对单元 | 否；不得跨单元补齐 |
| `learning_curve_incomplete` | planned ledger 未全部达到成功或具名终态 | 否；报告不完整 |
| `noninferiority_unconfirmed` | 区间未满足冻结容差 | 是科学终态，但不是确认成功 |
| `confirmation_population_not_independent` | 确认总体已参与发现/选择 | 否；拒绝确认访问 |

既有 `insufficient_statistics`、`training_failed`、`fit_failed` 等状态继续保留。批处理捕获预期科学终态后必须写入 ledger；未知异常使用稳定退出码 70，并留下不可覆盖失败 run。

## 15. 文件级开发清单

### 15.1 新增文件

| 文件 | 责任 |
|---|---|
| `src/research/sample_efficiency_protocol.py` | overlay 协议解析、严格校验和 canonical digest |
| `src/research/training_subsets.py` | 事件组排序、嵌套子集、摘要和 membership 校验 |
| `src/research/sample_efficiency.py` | planned ledger、配对聚合、不确定性和报告 payload |
| `src/research/sample_efficiency_workflow.py` | 新 stages 的应用编排，避免继续膨胀现有 `workflow.execute()` |
| `src/cli/sample_efficiency.py` | 薄 CLI；参数解析后调用应用服务 |
| `scripts/h4l_learning_curve.py` | 完整批次、plan-only、clean 和进度显示 |
| `config/research_sample_efficiency_protocol_v1.json` | 受审模板；正式值冻结后另存新协议文件 |
| `config/research_sample_efficiency_batch.example.json` | 仅路径和资源配置示例 |
| `tests/research/test_training_subsets.py` | 子集与成员资格单元测试 |
| `tests/research/test_sample_efficiency_protocol.py` | schema 和未知字段拒绝测试 |
| `tests/research/test_sample_efficiency.py` | 配对、聚合、不确定性和失败传播测试 |
| `tests/research/test_h4l_learning_curve_script.py` | 脚本计划、路径和批次行为测试 |
| `tests/research/test_sample_efficiency_workflow.py` | 合成端到端与 artifact lineage 测试 |

### 15.2 修改文件

| 文件 | 最小修改 |
|---|---|
| `src/research/discriminants.py` | 可选 subset 输入、train 过滤、v2 model payload、参数量记录和 v1/v2 预测兼容 |
| `src/research/artifacts.py` | 双协议/新 payload 的严格读取辅助，不改变 v1 digest |
| `src/research/workflow.py` | 仅抽取可复用 train/calibrate/templates/infer 服务；保持旧命令行为 |
| `src/cli/research.py` | 若旧 train 作为底层执行器，只增加成组 subset 参数；否则保持不变 |
| `src/research/reporting.py` | 保留 epoch 曲线；共享通用绘图样式，不承载新统计语义 |
| `src/research/resources.py` | 如有必要增加 task 标签/worker 初始化测试，不增加嵌套并行 |
| `docs/sw-dev/artifact-schema.md` | 实现完成后登记新 payload 与 lineage 契约 |
| `docs/sw-dev/research-software-design.md` | 实现完成后链接样本效率扩展，不把计划写成已实现 |
| `docs/research/current-research-status.md` | 仅在功能及验证状态真实变化后更新 |

## 16. 测试矩阵

### 16.1 协议和 schema

- 接受唯一合法 v1 overlay；拒绝缺字段、未知字段、NaN/Infinity、无序/重复比例；
- 拒绝 base protocol hash、prepared、population 或 compact freeze 不匹配；
- 拒绝 15 组合、任意 network seed、运行时 `delta_w68` 和任意架构宽度；
- v1/v2/v3 ResearchProtocol 既有测试保持通过。

### 16.2 子集算法

- 同输入和 seed 字节级确定；不同 draw seed 可改变低比例集合；
- 同 draw 下 25% 是 50% 子集，50% 是 100% 子集；
- 信号/背景分别满足冻结舍入；组内行不拆分；
- 三表示引用同一 membership digest；
- 输入行顺序改变不改变结果；hash tie 由 event_group_id 稳定打破；
- 混合 role/label、重复冲突组、空类别、无效权重和低支持产生正确终态；
- 100% endpoint 被 canonicalized，不能计为多个 draw 副本。

### 16.3 训练和下游绑定

- validation 行数在 fraction 改变时不变；
- scaler、类别均值和质量分箱确实在所选 train 子集拟合；
- subset 外 train 事件不会进入优化；
- calibration/template/assessment 事件不能进入 subset；
- model v2 篡改 fraction、draw、membership 或参数量后读取失败；
- calibration、template、inference 对 experiment cell key 全链校验；
- v1 模型仍能预测，但不能进入主样本效率配对。

### 16.4 聚合和统计

- `Delta W68` 只在相同 fraction/draw/network seed 内配对；
- 顺序打乱不影响汇总；失败和缺失不被删除；
- 100% 不产生虚假的 subset variance；
- 网络、子集、评价和校准 seed 不得混用；
- 不完整 ledger 返回 `learning_curve_incomplete`；
- `Q*` 未被观测网格包围时不外推；
- CI 上界等于容差时通过，大于容差时 `noninferiority_unconfirmed`。

### 16.5 安全和 assessment

- discovery/learning-curve 命令在任何情况下都不解码 assessment；
- confirmation 在 claim 前的绑定失败不会创建 claim；
- 合法确认先 durable claim，再解码 payload；
- 已浏览 population、同总体重划分和 lineage 重合均被拒绝；
- claim 后的 redesign 和不同 freeze repeat 被拒绝；
- symlink、越界 output root、覆盖现有 run 和 artifact receipt 篡改被拒绝。

### 16.6 性能与平台

- `workers=1` 与多 worker 产生相同计划顺序、cell ID 和统计结果；
- worker 内线程限制生效，无嵌套进程池；
- 失败 worker 不影响其他 cell 的身份和发布顺序；
- synthetic 小样本在 Windows 用于开发验证；
- 完整 ROOT 数值和性能必须在锁定 ARM64 环境另行验收，Windows 结果不能替代。

## 17. 分阶段实施计划

### M1：协议、schema 与特征化测试

工作：

- 固化 SampleEfficiencyProtocol、compact freeze 和 artifact schema；
- 为现有 `train_discriminant`、candidate key、claim 顺序和 `h4l_run.py --plan-only` 增加 characterization tests；
- 决定正式 fraction、draw seeds、CI 算法、`delta_w68` 来源和 CDF/capacity 点位。

退出条件：

- 所有科学参数均由严格协议拥有；
- 旧协议与旧批处理测试无变化通过；
- 未确定的统计选择不进入编码默认值。

### M2：确定性训练子集 artifact

工作：

- 实现事件组级分层哈希排序、嵌套前缀和 100% canonicalization；
- 发布 summary、membership 和 ledger；
- 实现 receipt、digest、population 和重算摘要验证。

退出条件：

- 子集确定性、嵌套性、角色隔离、行顺序不变性和失败语义测试通过；
- 不读取 assessment；
- 三种表示能够证明引用同一 subset ID。

### M3：训练与模型 lineage

工作：

- 扩展训练服务和 `research-discriminant-v2`；
- 扩展 experiment key、calibration bundle 和下游绑定；
- 保持 v1 reader 兼容。

退出条件：

- scaler/权重/分箱仅来自所选 train；validation 保持完整；
- artifact 篡改与跨 fraction 混用均被拒绝；
- 无 subset 的旧调用产生与基线一致的结果。

### M4：学习曲线批处理

工作：

- 实现独立 CLI、`h4l_learning_curve.py`、plan-only 和安全 clean；
- 构建去重后的完整 planned ledger；
- 复用 raw calibration、批次共同 template 和 T1 model-self inference。

退出条件：

- 合成数据可跑通三表示 × 25/50/100 × 多 draw × 多 network seed；
- planned、deduplicated、complete 和 terminal 数量一致；
- 现有 `h4l_run.py` 输出与测试不变。

### M5：配对聚合、绘图与误差分层

工作：

- 实现 W68(n)、相对 W68、AUC(n)、失败率、实际组数和配对完整性；
- 实现 event-group 评价重采样；
- 生成 JSONL/JSON/CSV/PNG/Markdown；
- 实现观测范围内 `Q*` 规则。

退出条件：

- 所有 planned cell 均出现在报告中；
- 网络、subset 和评价误差分别标记；
- 缺失配对、未达到 Q* 和未估计误差不会生成夸大结论。

### M6：容量、CDF 与非劣性确认守卫

工作：

- 实现唯一 capacity variant 和精简 CDF 点；
- 实现独立总体检测、新 claim namespace、预注册 CI 和确认 payload；
- 增加 claim-before-decode 与反馈隔离测试。

退出条件：

- capacity/CDF 不能参与候选再选择；
- 非独立总体在 payload 解码前被拒绝；
- 只有区间上界满足冻结容差才发布确认成功。

### M7：端到端验收、文档和运行手册

工作：

- 完成 synthetic 端到端、全回归、pip check 和故障注入；
- 更新 artifact schema、软件设计、CLI 帮助和 runbook；
- 在锁定 ARM64 环境执行正式 ROOT 性能与科学数值验收；
- 记录 repository authority 和 scientific numerical validation 为彼此独立的状态。

退出条件：

- Windows 开发测试和 ARM64 权威证据分别可追溯；
- frozen/failed run 不可覆盖；
- 每个报告结论能回溯到协议、population、subset、模型、校准、模板和推断 artifact。

## 18. 最终验收标准

功能验收：

- 一个命令可生成完整、不可覆盖的样本效率批次；
- 三表示在同一 paired cell 使用相同 train event groups；
- 25/50/100 为确定性嵌套，100% 不被伪重复；
- 非 train 评价资源固定；
- 图表横轴是实际事件组数，W68 差值严格配对；
- 失败、缺失和不可估计单元完整保留；
- 独立确认只在冻结候选和冻结容差下打开。

代码验收：

```powershell
conda run -n pytorch python -m pytest -q tests/research/test_sample_efficiency_protocol.py
conda run -n pytorch python -m pytest -q tests/research/test_training_subsets.py
conda run -n pytorch python -m pytest -q tests/research/test_sample_efficiency.py
conda run -n pytorch python -m pytest -q tests/research/test_sample_efficiency_workflow.py
conda run -n pytorch python -m pytest -q tests/research/test_h4l_learning_curve_script.py
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
```

科学验收：

- 正式协议在读取确认数据前冻结；
- 完整 MC 来源、特征定义、权重、角色支持和历史使用完成独立审计；
- 校准、模板和 assessment 统计未因训练 fraction 缩小；
- 报告明确区分网络随机性、train 子集波动、评价误差、校准误差和模板有限 MC；
- 非劣性结论来自独立总体；无独立总体时只发布探索性结果；
- 未完成训练样本量或确认时，从标题和结论中删除相应承诺。

## 19. 风险与回退策略

| 风险 | 影响 | 预防与回退 |
|---|---|---|
| 小 fraction 缺类别或质量支持 | 曲线点不可估计 | 先用身份/权重摘要审计；按冻结规则失败，不补抽 |
| 全批共同网格被弱单元迫使过度合并 | W68 分辨率下降 | 在 plan 阶段检查统计预算；若需改变网格算法，使用新协议，不运行时切换 |
| 165 次以上训练资源过高 | 周期过长、失败恢复困难 | 100% 去重、有界并行、逐 cell 不可覆盖 artifact；删减预算必须在看结果前新协议冻结 |
| `workflow.execute()` 继续膨胀 | 守卫难审计、回归风险高 | 新建 sample-efficiency workflow，并抽取已有服务而非增加巨型分支 |
| experiment key 漏掉 subset 身份 | artifact 冲突或错误配对 | key 与 payload 同时绑定 subset/cell；全链重算校验 |
| 同批数据选候选又确认 | 选择偏差 | lineage 排除集合和独立 population 检查；无独立数据则降级探索性 |
| 容量差异混入表示差异 | 错误归因 | 主结果报告参数量；只做唯一预注册容量对照 |
| raw/CDF 结果分歧 | 结论由有限校准统计驱动 | 明确报告，不扩大网格；必要时另立校准课题 |
| 旧 artifact 被补造新身份 | 审计链失真 | v1 只读兼容；缺失字段永不推断为低比例实验 |

若阶段 M2 或 M3 的身份绑定无法达到字节级可重放和篡改检测，后续批处理不得启动。若没有独立确认 MC，M6 只实现守卫和探索性报告，不发布确认状态。若计算预算不能支持预注册重复数，应在任何主指标生成前创建新协议并收缩研究问题，而不是完成后删除失败或不利重复。

## 20. 交付顺序与依赖

| 交付 | 依赖 | 可并行项 |
|---|---|---|
| 协议/schema | 研究方案、现有 ResearchProtocol | characterization tests |
| subset artifact | 协议/schema、prepared identity | CLI plan 展示 |
| model v2 lineage | subset reader、现有训练 | v1 兼容测试 |
| batch workflow | model v2、calibration/template key | 安全路径测试 |
| aggregate/report | 完整 ledger、inference payload | 绘图与 CSV 输出 |
| confirmation | compact freeze、独立 population、聚合统计 | CDF/capacity 对照 |
| authority validation | 全功能和全测试 | 文档、复现索引 |

关键路径为 `M1 → M2 → M3 → M4 → M5 → M6 → M7`。实现时可以并行编写测试和文档，但不能绕过前一阶段的科学身份退出条件。

## 21. 结论

完成该课题所需的软件变化，重点不是重写神经网络，而是把当前“固定完整 train 上的多表示训练”扩展为“固定分析链上的可审计训练样本量实验”。现有 MLP、角色隔离、校准、模板、T1 推断和 artifact 事务均可复用；必须新增的是独立学习曲线协议、事件组子集 artifact、模型 lineage、配对统计、失败 ledger 和独立非劣性确认。

该方案实施后，代码才能严格区分以下三类问题：输入是否包含额外物理信息、固定学习器是否更容易利用某种表示、以及性能差异是否随有限训练 MC 改变。在此之前，现有 epoch 学习曲线和五种子 15 组合报告只能作为发现与软件先导证据，不能作为样本效率或紧凑非劣性的确认结论。
