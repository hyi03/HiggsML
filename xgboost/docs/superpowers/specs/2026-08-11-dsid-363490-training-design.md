# DSID 363490 四轻子背景训练设计

## 1. 目标

使用 ATLAS Open Data 2020 的 DSID 363490
`Sherpa_221_NNPDF30NNLO_llll` 作为主要连续四轻子背景，替代统计量不足的
DSID 700600 参与 XGBoost 训练。复用已经完成的 ROOT 读取、四轻子重建、物理权重、
稳定数据划分、交叉验证、工作点、诊断、绘图和运行发布框架，不覆盖任何已有运行。

本任务的成功标准是：

- 官方单文件被下载、校验并保存在独立文件名下；
- Higgs 345060 与 ZZ 363490 通过同一套增强 selection；
- 363490 selection 后的有效背景统计量足以进行稳定的五折训练；
- 模型候选和工作点仍只由 development/OOF MC 决定；
- 700600 不参与训练，只用于冻结后的外部生成器/版本验证；
- 生成 MC-only 的 Higgs 与 ZZ 四轻子质量图，检查 Higgs MC 是否在 125 GeV
  附近形成峰，同时明确这不是在真实数据中观察到 Higgs；
- 不评分真实数据，不人工查看真实数据的 120--130 GeV 信号区。

## 2. 数据角色

| 样本 | 角色 | 是否参与拟合 | 是否决定工作点 |
|---|---|---:|---:|
| Higgs 345060 | 信号 MC | 是 | 仅 development/OOF |
| ZZ 363490 | 主要背景 MC | 是 | 仅 development/OOF |
| ZZ 700600 | 外部版本验证 | 否 | 否 |
| data16 period A | 本任务不评分的真实数据 | 否 | 否 |

363490 与 700600 都代表连续四轻子背景，因此不得把两者的完整物理产额相加。
700600 的用途是检验使用旧 Sherpa/旧开放数据训练的模型能否推广到更新样本。

## 3. 输入获取与不可变性

只下载 CERN Open Data record 15005 中的单个
`mc_363490.llll.4lep.root`，不下载 930.5 MiB 的完整 `4lep.zip`。文件保存为
`data/raw/zz_363490.root`；现有 `data/raw/zz.root` 保持不变。

下载后、任何预处理前必须记录：

- 官方下载 URL；
- 字节大小与 SHA-256；
- TTree 名称和条目数；
- ROOT 内实际 `channelNumber`；
- 所需分支及其基本类型；
- MC 归一化字段 `xsec`、`kfac`、`filteff`、`sum_of_weights` 的一致性。

若 DSID、分支、单位或归一化字段与可信 metadata 不一致，流程立即停止，不训练。

## 4. 增强 selection

增强条件以 YAML 配置表达，并对 Higgs 345060、ZZ 363490、ZZ 700600 使用相同定义。
事件从 ROOT 中的全部轻子出发，先建立 good-lepton mask，再要求恰好四个 good leptons。

### 4.1 事件级触发

- 要求 `trigE || trigM`；
- 最终四轻子中至少一个满足 trigger-match。新版分支名为
  `lep_isTrigMatched`，2020 格式分支名为 `lep_trigMatched`；进入 selection 前必须映射为
  同一个 canonical 字段。

### 4.2 轻子 identification

- 每个最终电子和缪子均要求 `lep_isTightID`；
- 不同时叠加不透明的 `lep_isTightIso`，isolation 使用下面的显式变量和阈值。

### 4.3 Isolation

对每个最终轻子要求。新版分支 `lep_ptvarcone30`、`lep_topoetcone20` 与 2020 分支
`lep_ptcone30`、`lep_etcone20` 必须先映射为同一 canonical 字段：

\[
\frac{p_T^{\mathrm{varcone30}}}{p_T^\ell}<0.3,
\qquad
\frac{E_T^{\mathrm{topoetcone20}}}{p_T^\ell}<0.3.
\]

分母必须有限且严格为正；非有限输入或无效分母直接拒绝事件并体现在 cutflow 中。

### 4.4 Impact parameter

- 电子：\(|d_0/\sigma(d_0)|<5\)；
- 缪子：\(|d_0/\sigma(d_0)|<3\)；
- 所有轻子：\(|z_0\sin\theta|<0.5\ \mathrm{mm}\)。

这里的 \(\theta\) 由轻子 \(\eta\) 计算。实现前必须通过 ROOT metadata/已知开放数据
格式确认 `lep_z0` 的单位；不得根据数值大小猜测单位。新版 `lep_d0sig` 与 2020
`lep_tracksigd0pvunbiased` 必须映射为同一 canonical \(d_0\) significance。

### 4.5 已有四轻子条件

good leptons 恰好为四个后，继续使用现有条件：

- 轻子种类仅为电子或缪子；
- 有序 \(p_T\) 阈值为 20、15、10、7 GeV；
- 电子 \(|\eta|<2.47\)，缪子 \(|\eta|<2.7\)；
- 四轻子总电荷为零；
- 存在两个 SFOS 配对，并按距离 \(m_Z\) 最近定义 \(Z_1\)；
- 所有 SFOS 质量大于 5 GeV；
- \(50<m_{Z_1}<106\) GeV；
- baseline 使用 \(12<m_{Z_2}<115\) GeV，sliding 下限保留为可配置的更强版本；
- \(105<m_{4\ell}<160\) GeV。

不得使用 120--130 GeV 窄窗筛选训练事件，`m4l` 继续禁止进入模型特征。

### 4.6 Cutflow 顺序

固定记录以下阶段：

```text
read
trigger
allowed_lepton_types
tight_identification
track_isolation
calorimeter_isolation
transverse_impact_parameter
longitudinal_impact_parameter
exactly_four_good_leptons
trigger_match
lepton_pt
lepton_eta
zero_charge
valid_sfos_pairing
all_sfos_mass
z1_mass_window
z2_mass_window
m4l_analysis_window
selected
```

每一级记录未加权计数、相对前一级效率、相对 read 效率；MC 继续记录 signed 与
absolute weighted yield。

## 5. 输入格式适配

现有 Higgs 345060/ZZ 700600 使用新版 `analysis` TTree 和 GeV 分支；363490 使用
2020 `mini` TTree 和 MeV 分支。I/O 层必须按配置的 profile 把两种格式映射为同一组
canonical 字段，再进入同一个 selection 和 feature builder。profile 只允许改变：

- TTree 名称；
- MeV/GeV 单位；
- 已核对的分支别名；
- MC 归一化来源。

2020 文件没有当前流程依赖的逐事件 `xsec`、`kfac`、`filteff`、`sum_of_weights`
canonical 分支时，使用配置中逐字记录的官方 metadata：363490 的 cross section
`1.2564 pb`、k-factor `1.0`、filter efficiency `1.0`、sum of weights
`7538705.808`。这些常数必须进入配置快照和 manifest，且 DSID 必须由 ROOT 内容验证。
不得从文件名推断 DSID，也不得静默使用默认归一化。

## 6. 配置和运行隔离

保留 `config/demo.yaml` 和所有已有 run 不变。新增一份专用配置，记录 363490 路径、
DSID 和增强 selection。预处理和训练均使用不存在的新 run 目录，并沿用现有原子
claim、manifest-last、hash binding 和拒绝覆盖规则。

推荐运行结构：

```text
runs/full-baseline-363490-<date>/
runs/full-training-363490-<date>/
runs/external-validation-700600-<date>/
```

任何失败运行保留 `failure.json`，不得删除后复用同名目录。

## 7. 训练与权重

- Higgs 345060 与 ZZ 363490 按现有稳定 event identity 规则划分；
- development 使用五折 OOF 比较现有六个候选；
- one-standard-error 规则选择候选；
- loose/medium/tight 工作点只由 development OOF 背景效率确定；
- independent test 只做一次冻结评价；
- signed `physical_weight` 只用于物理产额；
- 拟合继续使用按类别平衡的非负 `abs(physical_weight)`；
- 不加入 `m4l`、DSID、事件编号、样本来源或权重字段作为特征。

363490 的物理归一化只使用其自身可信 metadata。ROOT 教程中用于近似缺失
\(gg\to ZZ\) 的额外 1.3 修正不在本基线中静默应用；该缺失作为模型限制记录，若未来
需要物理产额修正，必须另行设计并给出系统不确定度。

## 8. 外部 700600 验证

模型、树数和三个工作点全部冻结后，才加载按同一增强 selection 准备的 700600：

- 把训练运行中已经冻结评分的 Higgs independent-test 行与新评分的 700600 组合，报告
  不重新拟合的 external weighted AUC；
- 报告三个工作点的 700600 背景效率及统计区间；
- 比较 363490 test 与 700600 的 score、`mZ1`、`mZ2`、`pt4l` 和 `m4l` 分布；
- 报告生成器/发布版本迁移导致的 KS 或其他预先定义距离；
- 外部验证结果不得反向用于重选模型、树数或阈值。

如果 700600 在增强 selection 后事件过少，结果仍如实报告，不以此为理由查看真实数据
或重新调参。

## 9. 输出与物理解读

除现有 ROC、score、CV、feature importance 和 ZZ mass-sculpting 图外，新增 MC-only：

- Higgs 与 363490 的 inclusive `m4l` 分布；
- 在冻结 loose/medium/tight 工作点后的 Higgs 与 363490 `m4l` 分布；
- 363490 与 700600 的外部验证对比图。

Higgs MC 在约 125 GeV 的峰只能说明信号模拟和分析链符合预期，不能描述为在真实数据中
发现或重新发现 Higgs。图中使用物理权重时必须清楚标注归一化；同时提供 shape-normalized
版本以检查形状，二者不得混淆。

## 10. 错误处理与测试

先写失败测试，再修改实现。至少覆盖：

- 缺少 trigger/ID/isolation/IP 分支时在事件读取前失败；
- trigger 与 trigger-match 的边界；
- 电子/缪子不同 `d0sig` 边界；
- `z0 sin(theta)`、isolation 等号边界和非有限值；
- 至少四个 raw leptons 中筛出恰好四个 good leptons；
- 五个及以上 good leptons 被拒绝；
- 新 cutflow 顺序和逐级计数；
- 增强 selection 同时作用于 signal/background/data 配置路径；
- 363490 DSID、normalization 和输入 hash 绑定；
- 2020 `mini`/MeV 分支与新版 `analysis`/GeV 分支映射到相同 canonical 事件；
- 700600 外部验证不触发 fit、候选选择或工作点重算；
- `m4l` 和 provenance 字段仍不进入 `FEATURES`；
- 旧配置与旧合成测试保持兼容；
- 新旧 run 目录不可覆盖，失败状态可审计。

真实运行前跑聚焦测试与完整合成测试。真实下载和运行后，逐一核对 cutflow、CSV 行数、
manifest hash、所有 JSON 数值有限性和图片可读性。

## 11. 非目标

本任务不包括：

- 合并 363490 与 700600 的物理产额；
- 加入 \(Z+\)jets、\(t\bar t\)、triboson 或 fake-lepton 背景；
- 查看或评分真实数据的 120--130 GeV 区域；
- 根据真实数据或 700600 外部验证重新调参；
- 正式显著性、sideband fit、系统误差模型或 Higgs 发现声明。
