# H → ZZ* → 4ℓ XGBoost Demo 进展简报

> **2026-08-12 更新：** 在下述 1.0 消融之后，唯一的 DropTop4 + 质量分箱迭代
> 重加权 MC-only 比较也已完成。新 run 的终态是 `no_eligible_iteration`，
> `selected_iteration: null`、`test_opened: false`；第 5 轮把三个 ZZ KS 降至
> 0.074168/0.097203/0.094070，却使 OOF AUC 降至 0.758871（门槛 0.80）。因此
> 组合仍未通过，held-out MC test 和 periodA 均未开启。下方保留部分历史 Task 4B/DSID 700600 数值作为过程
> 记录。当前 1.0 基准已改用 DSID 363490：selection 后 11,976 个 ZZ；full-14 OOF/test
> AUC 0.885296/0.894054，但 OOF 最大 ZZ KS 0.457954。三个预声明删特征方案均未同时
> 通过 AUC >= 0.80 与所有 KS <= 0.10，最终为 `no_eligible_profile`，held-out test
> 未开启。当前科学结论以项目总览、路线图和 DropTop4 交接报告为准。

**讨论日期：** 2026-08-11
**当前状态：** 历史 5,000-entry 端到端 Demo、Task 4A full-ROOT 预处理和 Task 4B MC-only 全量训练审计均已完成；物理分析仍处于方法验证阶段。
## 一句话总结

历史 5,000-entry Demo 已完成含真实数据评分的端到端流程；Task 4A 完成三个 ROOT 的
全量预处理，Task 4B 又只用全量 MC 完成 OOF 模型选择、三个工作点和独立 test 审计。
Task 4B 没有读取或评分真实数据，且 selected ZZ 很少，因此仍不足以支持物理结论。

## 研究目标

目标过程为：

\[
H\rightarrow ZZ^*\rightarrow4\ell,\qquad \ell=e,\mu
\]

使用 XGBoost 区分：

- **信号：** Higgs MC；
- **背景：** 连续 \(ZZ^*\rightarrow4\ell\) MC；
- **真实数据：** 只用于模型固定后的推理，不参与监督训练。

核心设计是：**不把四轻子不变质量 \(m_{4\ell}\) 输入模型 `FEATURES`**。预处理仍使用宽范围的 \(m_{4\ell}\) selection；模型固定后，质量变量才可按盲化政策用于独立分布检查。

## 已完成工作

以下第 5–10 项描述历史 5,000-entry 模型流程；Task 4A 和 Task 4B 的独立完成结果在
第 13–14 项以及后文分别说明，不能混作同一次运行。

1. 读取并核对 Higgs MC、ZZ MC 和 data16 period A ROOT 文件；
2. 重建四轻子事件及两个 SFOS Z 候选；
3. 计算 14 个运动学特征；
4. 构造带符号的 MC 物理权重和非负训练权重；
5. 按事件哈希划分 train、validation 和 test；
6. 完成 300 轮 XGBoost 训练，并加入训练进度显示；
7. 使用 validation 选择分类阈值；
8. 使用 test 计算最终 AUC、KS 距离和过拟合指标；
9. 保存模型并应用到真实数据；
10. 生成 ROC、分数分布和 \(m_{4\ell}\) 图；
11. 接入可配置 selection、逐级分样本 cutflow、data/MC 分离摘要和 run manifest；
12. 建立单元测试和交接文档：Task 4A 验收时为 `194 passed`，Task 8 文档收尾后为
    `383 passed`；
13. 完成 Task 4A full-ROOT 预处理：Higgs、ZZ、data 分别全量读取 `419943`、
    `11260`、`29275` 条，并选择 `350928`、`471`、`226` 条；manifest schema
    为 `1.1`，旧 `data/processed/` 与 `outputs/` 保持不变。
14. 完成 Task 4B 全量 MC 训练审计：从 `351399` 行 MC 建立 `281249` 行 development
    OOF 和 `70150` 行 independent test，冻结模型和三个工作点，全程不读取或评分真实数据。

## 数据与方法

### 数据来源与样本定义

数据来自 [ATLAS 13 TeV Open Data for Education 2025 beta](https://opendata.atlas.cern/docs/data/for_education/13TeV25_details)。MC 的 dataset ID、过程、生成器、截面和归一化信息通过 [ATLAS 官方 metadata](https://opendata.atlas.cern/docs/data/for_education/13TeV25_metadata) 核对。

当前使用的是三个 `exactly4lep` ROOT skim，TTree 名称均为 `analysis`，四动量单位为 GeV：

| 本地文件 | 数据类型 | Dataset ID | 过程与生成器 | ROOT 总记录数 |
|---|---|---:|---|---:|
| `data/raw/higgs.root` | Higgs MC | 345060 | \(ggH,\,H\rightarrow ZZ\rightarrow4\ell\)；Powheg + Pythia8 + EvtGen | 419,943 |
| `data/raw/zz.root` | ZZ MC | 700600 | \(VV\rightarrow4\ell\)；Sherpa 2.2.12 | 11,260 |
| `data/raw/data16_periodA.root` | 真实碰撞数据 | 不适用 | 2016 period A，无 MC truth label | 29,275 |

本地文件已用 SHA-256 与下载记录核对：

| 文件 | SHA-256 |
|---|---|
| `higgs.root` | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `zz.root` | `3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789` |
| `data16_periodA.root` | `adc3236398d1b6175438c9b5f77f540f3e1a377d628899156030b0bd3e0042cb` |

以下处理后事件数和 train/validation/test 划分属于历史 5,000-entry 模型运行，
不是 Task 4A 的全量训练结果。

| 样本 | 处理后事件数 | 用途 |
|---|---:|---|
| Higgs MC | 4,884 | 信号 |
| ZZ MC | 4,685 | 背景 |
| Data16 period A | 1,112 | 无标签真实数据 |

MC 划分为：

| 集合 | 事件数 | 作用 |
|---|---:|---|
| Train | 5,752 | 只用于模型拟合 |
| Validation | 1,919 | 只用于选择阈值 |
| Test | 1,898 | 只用于最终评价 |

Task 4A 已对三个 ROOT 做全量预处理并冻结独立 aggregate 基准：

| 样本 | full 读取数 | selection 后事件数 |
|---|---:|---:|
| Higgs MC | 419,943 | 350,928 |
| ZZ MC | 11,260 | 471 |
| Data16 period A | 29,275 | 226 |

该任务没有训练新模型、选择新阈值或给真实数据重新打分；真实数据的盲化质量区也没有
被人工检查。

### MC 权重

配置采用的目标积分亮度为：

\[
\mathcal{L}=10{,}000\ \mathrm{pb}^{-1}=10\ \mathrm{fb}^{-1}
\]

物理权重计算为：

\[
w_{\mathrm{phys}}
=\mathcal{L}\,
\frac{\sigma\cdot k\cdot\epsilon_{\mathrm{filter}}}
{\sum w_{\mathrm{MC}}}
\cdot w_{\mathrm{MC}}
\]

本地 ROOT 分支中的归一化参数为：

| MC | xsec [pb] | k-factor | filter efficiency | sum of weights |
|---|---:|---:|---:|---:|
| Higgs 345060 | 28.3 | 1.717 | 0.000124 | 45,231,012 |
| ZZ 700600 | 1.2974 | 1.0 | 1.0 | 8,900,161,536 |

Higgs 三个截面因子的乘积约为 `0.006025 pb`，与官方 metadata 中约 `0.006024 pb` 的有效截面一致到当前展示精度。

带符号的 `physical_weight` 保留用于产额计算。由于 XGBoost 不接受负 sample weight，训练时另外使用：

\[
w_{\mathrm{train}}
=\frac{|w_{\mathrm{phys}}|}
{\left\langle|w_{\mathrm{phys}}|\right\rangle}
\]

历史模型只处理每个文件前 5,000 条记录，尚未做抽样比例修正，因此其权重不能直接
解释为完整样本的最终预期产额。Task 4A 已验证全量 MC 归一化 metadata 和 aggregate
yield；完成的 Task 4B 对 Higgs、ZZ 都使用 `1.0` 抽样比例，并在每个拟合子集中构造
类别平衡的非负训练权重，同时保留 signed `physical_weight` 用于物理摘要。

## 模型细节

### 输入特征

模型使用 14 个变量。四个轻子首先按 \(p_T\) 从高到低排序，因此 lepton 1 是 leading lepton，lepton 4 是最低 \(p_T\) 的 lepton。

| Feature | 定义 | 单位 | 主要物理信息 |
|---|---|---|---|
| `lep1_pt` | leading lepton 的横动量 | GeV | 最硬轻子的能标与事件 boost |
| `lep2_pt` | sub-leading lepton 的横动量 | GeV | 第二硬轻子的运动学 |
| `lep3_pt` | 第三个轻子的横动量 | GeV | 较软衰变产物的运动学 |
| `lep4_pt` | 第四个轻子的横动量 | GeV | 对 off-shell \(Z^*\) 和软轻子较敏感 |
| `lep1_eta` | leading lepton 的赝快度 | 无量纲 | 轻子相对束流方向的分布 |
| `lep2_eta` | 第二个轻子的赝快度 | 无量纲 | 事件拓扑与探测器接受度 |
| `lep3_eta` | 第三个轻子的赝快度 | 无量纲 | 事件拓扑与探测器接受度 |
| `lep4_eta` | 第四个轻子的赝快度 | 无量纲 | 软轻子的方向和接受度 |
| `mZ1` | \(Z_1\) 候选的双轻子不变质量 | GeV | on-shell Z 候选的质量一致性 |
| `mZ2` | \(Z_2\) 候选的双轻子不变质量 | GeV | off-shell \(Z^*\) 与连续 ZZ 拓扑差异 |
| `pt4l` | 四轻子系统矢量和的横动量 | GeV | Higgs/ZZ 系统的整体 recoil 与产生运动学 |
| `deltaR_Z1` | \(Z_1\) 两个轻子之间的 \(\Delta R\) | 无量纲 | 第一个 Z 候选的角分离 |
| `deltaR_Z2` | \(Z_2\) 两个轻子之间的 \(\Delta R\) | 无量纲 | 第二个 Z 候选的角分离 |
| `deltaPhi_ZZ` | 两个 Z 候选之间的绝对方位角差 | rad，范围 \([0,\pi]\) | 两个 Z 系统的横向角关联 |

其中：

\[
\eta=-\ln\tan\frac{\theta}{2},
\qquad
\Delta R=\sqrt{(\Delta\eta)^2+(\Delta\phi)^2}
\]

轻子配对要求形成两个 same-flavour opposite-sign（SFOS）轻子对。在所有有效配对中：

- \(Z_1\) 定义为双轻子质量最接近 \(m_Z=91.1876\ \mathrm{GeV}\) 的候选；
- \(Z_2\) 是同一四轻子配对中剩余的 SFOS 候选；
- 如果存在多个有效划分，选择 \(Z_1\) 与名义 Z 质量距离最小的组合。

`m4l`、event/run/channel number、样本来源和所有权重字段均禁止进入模型。这样可以在模型固定后独立检查 \(m_{4\ell}\)，降低直接质量泄漏风险；Task 4B 已完成基础 MC-only 质量塑形审计，但其他运动学变量仍可能与 \(m_{4\ell}\) 相关。更多 ZZ 统计量和系统变化属于未来 MC 研究；任何盲化 sideband 扩展须经独立协议批准，且不在当前 1.2 授权范围内。

### 未作为模型输入、但保留用于分析的变量

| 变量 | 用途 | 不进入模型的原因 |
|---|---|---|
| `m4l` | 最终四轻子质量分布和 125 GeV 信号区检查 | 避免模型直接学习 Higgs 质量峰 |
| `eventNumber`、`runNumber`、`channelNumber` | 事件追踪、划分和样本验证 | 属于标识信息，可能产生数据泄漏 |
| `physical_weight`、`train_weight` | 物理产额和训练加权 | 权重不是事件运动学特征 |
| `period`、样本来源 | 数据追踪 | 会直接暴露 data/MC 或过程身份 |

### XGBoost 配置（历史 5,000-entry 模型）

历史模型使用 `XGBClassifier`，参数为：

| 参数 | 值 | 作用 |
|---|---:|---|
| `objective` | `binary:logistic` | 二分类 score |
| `eval_metric` | `auc` | validation 训练监控 |
| `n_estimators` | 300 | boosting rounds |
| `max_depth` | 3 | 单棵树最大深度 |
| `learning_rate` | 0.05 | 每轮学习率 |
| `min_child_weight` | 5 | 限制过小叶节点 |
| `subsample` | 0.8 | 每棵树使用 80% 事件 |
| `colsample_bytree` | 0.8 | 每棵树使用 80% 特征 |
| `reg_alpha` | 0.1 | L1 正则化 |
| `reg_lambda` | 2.0 | L2 正则化 |
| `random_state` | 42 | 固定随机种子 |
| `n_jobs` | 1 | 单进程训练，保证 Demo 简单可复现 |

当前没有使用 early stopping 或自动超参数搜索。输出的 `xgb_score` 是分类器分数，不是经过校准的 Higgs 概率。

### 训练与验证逻辑（历史 5,000-entry 模型）

1. 使用事件号和 channel number 的哈希做确定性 60/20/20 划分；
2. 模型只在 train 上拟合；
3. validation 作为 XGBoost 的 `eval_set`，并用于阈值扫描；
4. 阈值从 `0.05` 到 `0.95`，步长 `0.01`，选择加权 Asimov significance 最大点；
5. test 在模型和阈值固定后计算最终 AUC 和 significance；
6. 通过 train-test AUC gap 以及信号、背景各自的加权 KS 距离检查过拟合；
7. AUC gap 大于 `0.05` 或任一 KS 大于 `0.10` 时给出警告。

### Task 4B 全量 MC 训练审计（完成，2026-08-11）

Task 4B 的完成运行使用：

```bash
.venv/bin/python -m scripts.train_full_mc \
  --input-run runs/full-baseline-2026-08-10 \
  --config config/full_training.yaml \
  --run-dir runs/full-training-2026-08-11
```

它把非 test 的 development MC 做五折 OOF 交叉验证，只用 OOF 指标按
one-standard-error 规则选择 `depth2_child20` 和最终树数 `124`；随后从 OOF ZZ 冻结
loose `0.4421731233596802`、medium `0.6183240413665771`、tight
`0.6919658780097961` 三个背景效率工作点，最后才在 `70150` 行 independent test 上
评价。OOF weighted AUC 为 `0.7819012512935757`，test weighted AUC 为
`0.844677675856134`。

selected ZZ 总数 `471`（`391 development`、`80 test`），所以背景指标及 OOF/test
差异有很大的统计不确定性。总 warning 为 `true`，唯一原因是 `background_ks_distance`；
background KS distance 为 `0.1903422555517139`，signal
KS distance 为 `0.023516517743828735`，mass-sculpting warning 为 `false`。五张批准图
均为 MC-only，质量图只含 ZZ，不能显示或验证 125 GeV Higgs 峰。

Task 4B 未读取或评分真实数据，也不声称在真实数据中观察到 125 GeV Higgs 峰。
**历史 1.0 后续计划（非当前授权，保留以兼容 Task 4B 记录）：** 下一阶段是扩充 data periods，并单独设计冻结模型的盲化数据应用；不得在查看真实数据后重新调整 Task 4B。
该历史计划现已被 1.2 的 sealed MC-only 强去相关研究取代；当前不读取、评分或打开
periodA/其他真实数据，held-out test 保持封存，也不得根据真实数据重新调整 Task 4B。

## 模型验证结果（历史 5,000-entry 模型）

| 指标 | 历史结果 |
|---|---:|
| Train weighted AUC | 0.9936 |
| Validation weighted AUC | 0.9741 |
| Test weighted AUC | 0.9813 |
| Train-test AUC gap | 0.0123 |
| Signal KS distance | 0.0867 |
| Background KS distance | 0.0319 |
| 过拟合警告 | False |

Test AUC 约为 0.981，说明在当前 MC 小样本上模型具有较好的信号与背景区分能力。Train-test AUC gap 较小，两个类别的 KS 距离也低于当前设定的 0.10 警戒值，因此暂未发现明显过拟合迹象。

![测试集 ROC 曲线](outputs/roc_curve.png)

训练集和测试集的分数形状较接近：Higgs MC 主要分布在高分区域，ZZ MC 主要分布在低分区域。

![训练集与测试集分数比较](outputs/train_test_score_comparison.png)

## 阈值与真实数据结果（历史 5,000-entry 模型）

本节只记录 Task 4A 之前已有的历史模型 artifact，不是 full-ROOT 预处理的新结果。
Task 4A 没有重新打分，也没有人工检查真实数据的盲化质量区。

程序在 validation 上扫描 `0.05–0.95` 的 score 阈值，并选择当前加权 Asimov significance 最大的工作点：

\[
\text{XGBoost score}\geq0.93
\]

这里的 `0.93` 是当前 MC 小样本下的分类工作点，不代表事件有 93% 的概率来自 Higgs。

将固定模型应用到 1,112 个真实数据事件后：

- 16 个事件满足 `score ≥ 0.93`；
- 1,096 个事件满足 `score < 0.93`；
- `122–128 GeV` 内原本有 10 个真实数据事件；
- 该质量窗内没有事件通过 `0.93`；
- 质量窗内最高分约为 `0.9221`。

![高分真实数据的四轻子质量分布](outputs/m4l_high_score.png)

当前高分样本没有在 125 GeV 附近显示明显峰。这不表示分析失败；它说明现阶段的数据量、抽样方式和阈值还不足以形成可解释的物理结果。

## 当前限制

这些限制必须和模型结果一起说明：

1. 历史模型每个文件只读取前 5,000 条记录；其 AUC、Asimov 阈值和真实数据评分不能
   解释为 Task 4B 结果；
2. Task 4B 已完成全量 MC 训练，但 selected ZZ 只有 471 条，background KS warning
   为 true，背景诊断和 OOF/test 差异有很大的统计不确定性；
3. 只使用一个真实数据 period，统计量很少；
4. full-ROOT selection、cutflow、分离摘要、manifest 1.1 和 MC 归一化已经验证；只审查 aggregate artifact，没有人工检查真实数据盲区；
5. 尚未加入 trigger、identification、isolation 和 impact-parameter 选择；
6. 历史 `0.93` 阈值和 Asimov significance 只适合作为历史 Demo 技术指标；Task 4B
   使用三个 OOF 背景效率工作点，不使用 Asimov 扫描；
7. 尚未进行系统误差、sideband、control region 或质量谱统计拟合。

因此，当前可以得出的结论是：

> **分析链和模型验证流程已经跑通，但不能根据当前高分事件或质量图得出 Higgs 物理结论。**

## 当前下一阶段计划（1.2，MC-only）

### 第一优先级：预先设计更强的去相关训练

- 在新的、独立的 MC-only 设计中预先定义 uBoost 风格或对抗式去相关目标；
- 保持 OOF AUC >= 0.80、全部工作点 KS <= 0.10 与一次 test-opening 规则；
- 不因 DropTop4 + 重加权的负结果增加迭代、改变 mass bin、放宽门槛或做事后特征搜索；
- held-out test、periodA 和所有真实数据保持封存。

### 第二优先级：扩展 MC 验证

- 增加 ZZ MC 有效统计量并研究多随机种子和工作点稳定性；
- 扩展 MC-only score–mass 与质量塑形审计；
- 在任何独立、经批准的盲化协议之前，保持真实数据应用不在范围内。

### 第三优先级：未来独立统计分析（当前 1.2 不授权）

- 研究阈值对随机种子和样本变化的稳定性；
- 检查 classifier score 对 \(m_{4\ell}\) 的质量塑形；
- 仅在未来独立协议中定义 signal region 和 sidebands；
- 加入系统误差并对 \(m_{4\ell}\) 做统计拟合。

## 希望和教授讨论的问题

1. 在当前 1.2 之外、未来独立盲化协议获批时，哪些 data periods 与盲化边界才值得讨论？
2. 只有 471 条 selected ZZ 时，应优先增加哪类背景 MC 或控制样本？
3. 三个 OOF 背景效率工作点应如何评估统计和系统稳定性？
4. 最终分析是否应按 XGBoost score 分区，再对 \(m_{4\ell}\) 做联合统计拟合？
5. 下一阶段最需要加入哪些实验和理论系统误差？

## 60 秒口头摘要

> 我已经完成历史 5,000-entry 端到端 Demo、Task 4A full-ROOT 预处理和 Task 4B
> MC-only 全量训练审计。历史模型 test weighted AUC 0.981 和阈值 0.93 只属于旧流程。
> Task 4B 用 351399 行 MC 做 development OOF 选择，冻结三个工作点，再评价独立 test；
> OOF/test weighted AUC 为 0.782/0.845。它未读取或评分真实数据。selected ZZ 只有
> 471 条且 background KS warning 为 true，所以不能据此声称看到 125 GeV Higgs 峰。
> 最新 1.2 MC-only DropTop4 + 重加权研究在第 5 轮将三个 KS 降到 <= 0.10，但 AUC
> 降至 0.758871，低于 0.80，因此终态为 `no_eligible_iteration`，test 未开启。下一步
> 是预先设计更强的 MC-only 去相关目标；periodA 和其他真实数据继续封存。
