# H → ZZ* → 4ℓ Demo 下一阶段路线图

## 当前工程阶段说明（2026-09-01）

用户已批准
[XGBoost 科学行为等价重构设计](../superpowers/specs/2026-09-01-xgboost-refactor-design.md)
及 FR-001/Sprint M1-01 至 M1-06。当前先执行该工程重构；它固定使用现有 Angular19 与
既有 XGBoost 科学行为，不构成新的去相关训练研究，也不授权调参、放宽资格门槛、
真实规模训练、held-out test-opening 或真实数据访问。

本文以下去相关方法建议继续作为未来科学研究路线保留，不应被解释为否定当前已批准的
工程重构，也不应被工程重构解释为相应科学研究已经完成。

## ARM64 Angular5 + DropTop4 结论（2026-08-26）

预先批准的一次性 MC-only 15 特征研究（DropTop4 加五个 Angular5 角变量）已经在原生
ARM64 完成。R2 因 x86_64/Rosetta 重新计算的浮点量与 ARM 权威表不精确相同而停止
（`mZ1` 最大绝对差异 `9.66e-13`）；R3 使用独立 ARM64 path 且不引入容差。identity 和
enrichment 保留 `199104` 行、2 个 legacy duplicate groups/4 行和唯一的 canonical
identity。

六个 development-OOF iterations 都没有同时满足 AUC >= `0.80` 与 loose/medium/tight
三个 KS <= `0.10`。iteration 0 的 AUC `0.805150881259955` 合格但三个 KS 失败；iteration
5 的 AUC `0.7665404021047497` 失败但三项 KS `0.07381807828236636` / `0.090638729937013` /
`0.08836325258185229` 合格。所有 signal-efficiency gates 都通过，却不能绕过 AUC/KS
政策。终态为 `no_eligible_iteration`、`selected_iteration: null`、`test_opened: false`；
8-file no-selection allowlist 已审计，故没有模型、test 指标或预测 artifact，也没有访问
真实数据。

相对冻结的十特征 DropTop4 + 重加权最终轮（AUC `0.7588712973047708`、最大 KS
`0.09720271279351`），Angular5 最终轮略有改善（AUC `0.7665404021047497`、最大 KS
`0.090638729937013`），但仍不可选择。完整轨迹、效率、收据和历史 Full14/重加权/KNN
比较见 [执行报告](../superpowers/plans/2026-08-26-drop-top4-angular5-r3-arm64-report.md)。

本报告不授权下一阶段训练。不得追加 iteration、改变 features/bins、放宽 AUC/KS、打开
held-out test 或读取真实数据；下一项工作只能是新的、结构不同且预注册的 MC-only 设计。

## DropTop4 KNN flatness 决定（2026-08-25）

预先批准的一次 MC-only 原生平坦度训练已在新 run
`runs/decorrelation-drop-top4-363490-2026-08-24` 完成。五个候选全部不合格：AUC
均低于 `0.80`，且没有候选让 loose/medium/tight 三项 KS 同时不高于 `0.10`。
终态为 `no_eligible_candidate`，held-out test 未开启，真实数据保持封存。

本研究到此冻结，不追加系数、不改变特征、不放宽门槛，也不复用 run path。下一项
工作是单独预注册一个结构上不同的方法，例如对抗式质量去相关目标，或明确的
template/sideband 统计模型；在新设计获批前不启动训练。完整数值和哈希见
[执行报告](../superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md)。

## Full14 封存决定（2026-08-23）

Full14 XGBoost 已封存为失败的历史参考；不是可部署模型，也不是未来真实数据候选。
停止 Full14 + OOF 质量依赖阈值研究，不再以阈值变换、校准、追加重加权或调参补救
现有 Full14。其冻结 run、模型、manifest、预测和指标只能用于历史比较；不得打开
held-out test，不得读取 periodA。

下一阶段只考虑另行预先设计的原生质量去相关训练。每项新研究必须使用
新配置和新 run path，并保持 AUC >= 0.80、三个工作点 KS <= 0.10 以及 OOF 合格后才允许一次
test-opening 的既定规则。使用相同 14 个输入变量的全新去相关目标也必须重新立项和
批准，不能作为当前 Full14 的延续。

## 1.2 DropTop4 + 质量分箱迭代重加权后的推荐方向（2026-08-12）

在冻结的 1.1 Full14 重加权之后，已完成一次唯一的 MC-only 组合比较：移除
`lep3_pt`、`lep4_pt`、`mZ1`、`mZ2` 四个最强质量代理，并保持相同的 11 个质量 bin、
最多五次校正、AUC >= 0.80 和全部三工作点 KS <= 0.10 门槛。新 artifact 为
`runs/mass-reweighting-drop-top4-363490-2026-08-12`，其 manifest SHA-256 是
`e41473e74cdf662d0d7e71ea753edc2a272f0d7526a429b4b354576e32d2d27e`。

终态精确为 `no_eligible_iteration`，`selected_iteration` 为 `null`，
`test_opened` 为 `false`，因此 held-out MC test 和 periodA 都保持未开启。完整的
六轮 development-OOF 轨迹为：

| 迭代 | AUC | KS（loose / medium / tight） |
|---:|---:|---:|
| 0 | 0.7996529199780816 | 0.1754125886831281 / 0.2776300864689386 / 0.34469234042569663 |
| 1 | 0.7909840349437066 | 0.14116831342466396 / 0.22668300278758247 / 0.2563535629356366 |
| 2 | 0.7840745577657593 | 0.12466822176125592 / 0.1785279696252552 / 0.1845589106499591 |
| 3 | 0.7719399667136062 | 0.09349705772211825 / 0.1297707080628676 / 0.12623889191144305 |
| 4 | 0.7634006325078653 | 0.08043449205869585 / 0.11308325067710806 / 0.1169067754006049 |
| 5 | 0.7588712973047708 | 0.07416808989370494 / 0.09720271279351 / 0.09406967019374574 |

第 5 轮首次让三项 KS 同时不高于 0.10，但 AUC 0.7588712973047708 低于 0.80；六轮
没有任何一轮通过 AUC 门槛。该结果说明删去质量代理和当前背景重加权确有互补的
去塑形效果，却仍付出不可接受的判别力代价。

| 方法 | OOF AUC | 最大 OOF ZZ KS | 状态 |
|---|---:|---:|---|
| Full14 | 0.8852959102354316 | 0.4579540115915921 | 冻结参考 |
| Drop top four，无重加权 | 0.7996529199780816 | 0.34469234042569663 | 冻结参考 |
| Full14 + 重加权，第 5 轮 | 0.8523982143190011 | 0.24583464407366806 | 冻结参考；无合格迭代 |
| Drop top four + 重加权，第 5 轮 | 0.7588712973047708 | 0.09720271279351 | 新结果；无合格迭代 |

推荐的下一实验是预先设计去相关训练目标（uBoost 风格或对抗式目标）并保留相同的
OOF 资格门槛和一次 test-opening 规则；不要继续以事后删特征、增加迭代或改变 bin
来追逐该结果。Task 6 的一次程序性 Minor 也已记录：拒绝重跑前的广泛 SHA-256
inventory 对冻结 `data_events.csv.gz` 做了字节读取；它没有解压、解析、显示、绘图、
训练或改变该文件，对 MC-only 科学结果没有影响，但以后 hash 清单必须显式排除它。

## 1.1 质量分箱迭代重加权后的参考结果（2026-08-12）

1.0 的真实 DSID 363490 消融已经完成，结论是 `no_eligible_profile`：三个简单删特征
方案都无法同时满足固定的 OOF AUC >= 0.80 和全部工作点 KS <= 0.10。held-out test
和真实数据均未开启。后续不应继续堆叠事后挑选的删特征组合，也不应降低门槛。

1.1 的真实质量分箱迭代重加权也已完成，冻结路径为
`runs/mass-reweighting-363490-2026-08-11`，终态为
`no_eligible_iteration`。六轮 OOF 的 AUC 从 0.885296 降至 0.852398，仍高于 0.80；
最大 KS 从 0.457954 降至 0.245835，但 loose/medium/tight 最终 KS
0.173197/0.214474/0.245835 仍全部高于 0.10。因此 test 没有开启，不能进入 periodA。

下一项应另行设计更强的去相关方法，例如 uBoost 风格目标，或转向预先定义的
template/sideband 统计模型；不得在本次结果后增加轮数、改质量分箱或放宽门槛。
只有未来方法在 development OOF 通过同一冻结门槛，才允许一次 test 复现。即使
test 复现成功，任何真实数据或盲化 sideband 协议也仍须另行独立审查；它们不受当前
1.2 授权。控制区、系统误差和质量谱 likelihood 同样属于未来的独立统计分析阶段。

当前下一阶段是质量去相关训练研究；不得事后放宽 AUC/KS 门槛或打开真实数据。
在 1.1 质量分箱迭代重加权失败后，这具体意味着重新设计去相关目标或统计模型，
而不是重跑、延长或放宽已经冻结的迭代研究。

> 新设备或新 Codex 会话应先阅读根目录 `AGENTS.md`，确认数据、环境、当前基准和不可破坏的分析约束，再执行本路线图。

## 1. 下一阶段目标

下一阶段不是立即追求“看到 125 GeV 峰”，而是先把当前技术 Demo 升级成：

- 数据选择真实生效；
- MC 归一化可以解释；
- 结果对抽样和随机种子稳定；
- 训练、验证和真实数据应用可以重复；
- 每项物理结论都有对应检查和不确定度。

推荐先完成阶段 A 和 B，再增加数据量或优化模型。否则更多数据只会放大当前选择与权重的不确定性。

## 2. 阶段 A：修正分析基线

### A1. 接通事件选择配置

**代码状态（2026-08-10）：** 已实现并通过合成事件单元/集成测试；支持
fixed/sliding Z₂ 下限和逐级、分样本 cutflow。Task 4A 已全量运行真实 ROOT，并在
`runs/full-baseline-2026-08-10` 冻结 aggregate cutflow 和 selection 数。

把 `config/demo.yaml` 的 `selection` 真正传入预处理流程，并实现：

- 四个轻子要求；
- 分级 lepton \(p_T\) 切选；
- lepton \(\eta\) 接受度；
- \(Z_1\)、\(Z_2\) 质量窗；
- 宽松的 \(m_{4\ell}\) 分析窗，例如 105–160 GeV；
- 数据分支允许时再加入 isolation、impact parameter 和 trigger。

验收标准：

- 每个切选都有单元测试和 cutflow；
- 修改 YAML 后事件数按预期变化；
- MC 和 data 使用相同的可比选择。

### A2. 重做数据摘要

**代码状态（2026-08-10）：** data/MC 分离 schema、逐样本校验、SHA-256、软件/Git
manifest 和独立 run 目录已实现并通过测试。Task 4A 已生成真实 ROOT 的 schema 1.1
manifest；历史 `outputs/data_summary.json` 未改写。

将摘要拆成：

- 每个样本的原始读取数、重建成功数和各级 cutflow；
- MC 的 signed sum of weights、absolute sum of weights 和负权重比例；
- data 只报告事件数，不与 MC 权重相加；
- ROOT 文件、配置、软件环境和 Git 状态。

验收标准：

- `data_summary.json` 不再混合 data 单位权重和 MC 物理产额；
- 每个最终事件都能追溯到来源样本和处理配置。

## 3. 阶段 B：Task 4A 与 Task 4B 已完成

### Task 4A：全量预处理和归一化验证（完成）

2026-08-10 已使用 `--full` 读取 Higgs `419943`、ZZ `11260`、data `29275` 条，
selection 后分别为 `350928`、`471`、`226`。配置快照、三个输入 SHA-256、schema
1.1 manifest、MC 归一化有限性、CSV 行数、零重复 data run/event 对和六文件运行
布局均已验证。运行前后旧 `data/raw/`、`data/processed/`、`outputs/` 的路径、大小、
修改时间完全一致。

### Task 4B：全量 MC 训练和训练政策（完成，2026-08-11）

已实际运行：

```bash
.venv/bin/python -m scripts.train_full_mc \
  --input-run runs/full-baseline-2026-08-10 \
  --config config/full_training.yaml \
  --run-dir runs/full-training-2026-08-11
```

以下是已被 DSID 363490 1.0 取代的历史 Task 4B/700600 基准。完成运行的
manifest schema 为 `1.0`；全量 MC `351399`，development OOF `281249`，
independent test `70150`。one-standard-error 规则选择 `depth2_child20`，最终树数 `124`；
OOF weighted AUC `0.7819012512935757`，test weighted AUC `0.844677675856134`。

- 工作点阈值：loose `0.4421731233596802`，medium `0.6183240413665771`，tight `0.6919658780097961`。
- OOF 达到的 ZZ / signal efficiency：loose `0.5004580267548995 / 0.8806158272151767`，medium `0.20065226444487125 / 0.5799549950508799`，tight `0.1005088836655481 / 0.4257204708429173`。
- independent-test 达到的 ZZ / signal efficiency：loose `0.4253686842730043 / 0.8807478236049668`，medium `0.11723106326431036 / 0.602126444983588`，tight `0.0556776426566235 / 0.43029827315541624`。

总 warning 为 `true`，唯一原因是 `background_ks_distance`，对应 background KS distance `0.1903422555517139`；
signal KS distance `0.023516517743828735`，mass-sculpting warning 为 `false`。
selected ZZ 总数 `471`（`391 development`、`80 test`），所以背景指标及 OOF/test
差异有很大的统计不确定性。
五张批准图均只使用 MC；质量图只包含 ZZ，不能显示或验证 Higgs 125 GeV 峰。

Task 4B 未读取或评分真实数据，也不声称在真实数据中观察到 125 GeV Higgs 峰。
该历史阶段收尾测试为 `383 passed`。当前下一步以本页开头的 1.2 MC-only 强去相关
训练设计为准；held-out test、periodA 和其他真实数据仍不在当前授权范围内。

## 4. 阶段 C：扩充真实数据（历史/延期；当前 1.2 不授权）

下列内容保留为历史路线图和未来独立盲化协议的输入，不是当前工作授权。当前只有
`data16_periodA`；历史 5,000-entry 模型的高分样本只有 16 个事件；Task 4B 没有读取
或评分这些真实数据。1.2 期间不得读取、评分、打开或扩充任何真实数据 period。

仅在未来独立批准的盲化协议之后，才可考虑：

- 加入更多 data periods；
- 对每个 period 独立做数据质量检查；
- 检查 run/event 唯一性，防止重复；
- 合并前比较各 period 的关键变量；
- 保存每个 period 的 cutflow 和最终事件数。

验收标准：

- 合并后无重复事件；
- 各 period 的分布没有无法解释的异常；
- data 和 MC 的预选择分布具有可追踪的比较图。

## 5. 阶段 D：改进模型验证

### D1. 稳定性

- 用多个随机种子重复训练；
- 报告 AUC、KS 和阈值的均值与波动；
- 在 validation 内使用 bootstrap 或交叉验证评估阈值不确定度；
- 检查 `0.93` 是否只是当前小样本的统计波动。

### D2. 超参数

只在 train/validation 上调整：

- 树深；
- 学习率和树数量；
- min child weight；
- subsample 和 column sampling；
- L1/L2 正则化。

Test 集继续保持冻结，只在模型方案固定后评价一次。

### D3. 分数解释

- 明确 XGBoost score 不是校准概率；
- 如确实需要概率解释，使用独立 calibration 数据；
- 同时提供多个工作点，而不是只展示一个阈值；
- 报告每个工作点的信号效率、背景效率和预期产额。

验收标准：

- 模型保存和重新加载后预测一致；
- 不同随机种子的性能波动可接受；
- 阈值的选择规则在查看真实数据质量峰前固定。

## 6. 阶段 E：检查质量塑形

虽然 \(m_{4\ell}\) 没有作为模型输入，其他运动学特征仍可能与它相关。

历史 Task 4B 的 471 个 ZZ 事件曾给出不可靠的 `mass-sculpting warning=false`。
DSID 363490 的 11,976 个 selected ZZ 事件已取代它，并确认 full-14 模型存在强质量
塑形（OOF 最大 KS 0.457954）。三种简单删特征方案均未通过固定 AUC/KS 门槛，因而
1.0 的正确终态为 `no_eligible_profile`，test 未开启。

下列是未来、独立批准的 MC 验证/盲化协议内容，不是当前 1.2 的授权：

- 增加 ZZ MC 有效统计量，按生成器、系统变化和数据 period 重复诊断；
- 增加 score–\(m_{4\ell}\) 二维图、分箱稳定性和工作点变化测试；
- 只在未来独立批准的 Task 4C 盲化协议中检查 sideband 的 data/MC 一致性；
- 保持 signal region 盲化，并用自动回归测试锁定冻结工作点。

验收标准：

- 背景 \(m_{4\ell}\) 形状随 score 的变化被量化；
- 没有证据表明分类器人为制造窄峰；
- 所有检查有图、有数值和自动回归测试。

## 7. 阶段 F：从分类图升级到统计分析（未来独立阶段；当前 1.2 不授权）

高分直方图只能用于直观展示。更严谨的结果需要：

- 仅在未来独立统计协议中定义 signal region 和 sidebands；
- 建立信号与背景的 \(m_{4\ell}\) 模型；
- 对质量谱做统计拟合；
- 加入 MC 统计、归一化、实验和理论系统误差；
- 报告 expected/observed significance 或 limit；
- 保存完整 likelihood、拟合配置和诊断图。

在完成这些步骤之前，不应把高分事件数或单张质量图解释为 Higgs 观测显著性。

## 8. 阶段 G：工程化与自动化

建议增加：

- 微型 ROOT 集成测试数据；
- 一条完整 smoke test；
- 固定依赖版本或 lock file；
- CI 中运行 `pytest` 和小模型训练；
- 配置、数据摘要、指标和模型的 schema version；
- ~~命令行 `--run-dir`，把配置快照、processed CSV 和 aggregate JSON 隔离到新运行目录；~~（已实现）
- ~~运行 manifest，记录时间、配置哈希、输入文件校验和和软件版本。~~（生成逻辑和测试已完成）

验收标准：

- 新环境可根据 README 一次完成安装和 smoke test；
- 同一输入与配置产生可重复结果；
- 旧输出不会被误认为当前模型结果。

## 9. 推荐执行顺序

### 第一批：必须先做

1. ~~接通 selection 配置并补测试；~~（Task 4A 全量真实 ROOT 回归完成）
2. ~~为预处理增加 cutflow；~~（Task 4A aggregate artifact 已冻结）
3. ~~分开 data 与 MC 摘要并生成 run manifest；~~（Task 4A schema 1.1 artifact 已冻结）
4. ~~全量预处理并验证 MC 归一化字段；~~（Task 4A 完成）
5. ~~制定全量训练的类别平衡、抽样和权重政策；完成 MC-only 训练与审计。~~（Task 4B 完成）

### 第二批：形成可信训练（历史待办；当前 1.2 仅授权 MC-only 去相关设计）

6. 未来独立盲化协议下扩充 data periods（未实现；当前不授权）；
7. 增加微型 ROOT 端到端测试；
8. 做多随机种子训练和阈值稳定性（未实现）；
9. 扩展 Task 4B 已完成的基础 MC-only score–mass/质量塑形审计：增加 ZZ 统计量、
   系统变化、二维/分箱稳定性和自动回归测试；
10. 未来独立设计冻结模型的 Task 4C 盲化真实数据应用（未实现；当前不授权）。

### 第三批：形成物理结果（未来独立阶段；当前 1.2 不授权）

11. 建立 signal region、control/sideband；
12. 加入系统误差；
13. 对 \(m_{4\ell}\) 做统计拟合；
14. 生成可复现的最终报告。

## 10. 下一次开发建议

下一次最合适的具体任务是预先设计去相关训练候选与固定验收协议。只有 development
OOF 通过现有 AUC/KS 门槛，才允许一次 held-out test 复现。该工作不授权读取或评分
真实数据，也不授权根据任何 test/data 结果重调模型、候选或工作点。
