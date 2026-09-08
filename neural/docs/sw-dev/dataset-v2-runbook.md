# 数据集隔离 v2 运行手册

当前运行接口只支持 `atlas2020_4lep`（345060 + 363490）与 `atlas2025_exactly4lep`（345060 + 700600）。两个成员须来自同一 release/collection。下载器保留官网文件名；所有业务命令的 `--dataset` 必填。旧混用协议、单表和模型不能通过新入口运行，需重新预处理和训练。

## 环境与下载

仓库根执行 `python scripts/init_data.py` 下载/校验两套 MC；可用 `--dataset atlas2020_4lep` 或 `--dataset atlas2025_exactly4lep` 只处理一套。成员定义和摘要由代码固定；receipt 只证明下载字节校验。具体文件名、来源、锁恢复规则和迁移记录见 [init-data-verification.md](init-data-verification.md)。

进入 `neural/` 后使用 `pytorch` Conda 环境。安装命令入口：

```powershell
conda run -n pytorch python -m pip install --no-deps -e .
conda run -n pytorch python -m pip check
```

`osx.yml` 是原生 `osx-arm64` 权威环境锁；`win.yml` 用于 Windows 开发验证。Windows 验证不能替代 ARM64 全量 authority gate。

## 预处理

本手册的正常命令展示有窗兼容流程；新增正式无窗流程、拟合折权重及分位数分箱见 [inclusive 协议手册](../research/inclusive-protocol.md)。协议文件已改为用途名称，旧冻结 run 保留原记录。

`config/preprocess_run.example.yaml` 只允许 `schema_version: "2.0"`、`data_root`、`resources.chunk_size_events`。相对 data root 按配置文件所在目录解析；样本路径由数据集定义构造，不允许分别指定 Higgs/ZZ 路径。

诊断时可显式使用 `config/preprocess_protocol_debug.yaml`。该协议将 `selection.m4l_window_gev` 设为 `null`，表示不执行 m4l 分析质量窗。训练时必须显式传入 `--debug`；debug 状态不根据任何协议文件名推断。此模式不验证 `--input-run` 中记录的文件/canonical/protocol/run-config SHA，也不执行 `--protocol` 的封存快照校验，但仍要求输入可解析、数据集身份一致、表结构有效且只读取 development 分区。debug 接受任意有限 m4l；低于 105 GeV 的背景进入首个 adversary overflow bin，高于 160 GeV 的背景进入最后一个 overflow bin。数据集定义、原始 ROOT 和下载 receipt 的校验仍属于预处理阶段。显式 `--debug` 训练发布 `debug_diagnostic` 状态，必须使用新的 run 目录；仅可通过 `higgsml-test --debug` 进行诊断评价。

```powershell
conda run -n pytorch higgsml-train --debug --dataset atlas2020_4lep --input-run runs/atlas2020_4lep/preprocess-debug-001 --protocol config/adversarial_mlp_protocol_debug_v2.yaml --run-dir runs/atlas2020_4lep/development-debug-001
```

```powershell
conda run -n pytorch higgsml-preprocess --dataset atlas2020_4lep --protocol config/preprocess_protocol_mass_window.yaml --run-config config/preprocess_run.example.yaml --run-dir runs/atlas2020_4lep/preprocess-001
```

每次运行必须更换尚不存在的输出目录。新输出包含：

```text
config.yaml
processed/development_events.csv.gz
processed/test_events.csv.gz
artifacts/cutflow.json
artifacts/mc_summary.json
artifacts/manifest.json
```

两张表的列相同，development 仅有 train/validation，test 仅有 test。新增 `source_file_id` 和 `event_group_id` 是审计字段，禁止进入分类器。每个分区各有压缩文件 SHA-256、canonical 内容 SHA-256、大小和行数。

2020 两个样本使用 `open_data_2020` profile，2025 两个样本使用 `release22` profile。科学参数与 profile 资源按精确字节摘要固定。保持原来的四轻子选择、19 项重建特征、15 项模型特征、105–160 GeV 质量窗与 signed/absolute 权重职责。

2020 归一化采用官方固定版本样本表的有效截面和生成样本权重和；不重复乘过滤效率。ZZ 的新绑定为 1.2578 pb、sumw 7538705.8077，与历史混用协议的 1.2564 pb / 7538705.808 不同，属于新配对的输入归一化绑定，不宣称旧产额逐值等价。2025 按绑定 ROOT 的 xsec、kfac、filteff、sum_of_weights 展开并检查文件内稳定性。

split 仍为 `channelNumber:eventNumber` 的 BLAKE2b 6:2:2 分桶。fold 改为该事件分组字符串的 SHA-256 前 8 字节大端整数 `% 5`；来源文件和行号不参与 fold。同一组的多条来源行保持同 split/fold。跨 release 物理等价关系尚未证明，不联合训练或合并 OOF。

## Development 训练

```powershell
conda run -n pytorch higgsml-train --dataset atlas2020_4lep --input-run runs/atlas2020_4lep/preprocess-001 --protocol config/adversarial_mlp_protocol_mass_window.yaml --run-dir runs/atlas2020_4lep/development-001
```

训练在解码事件前比对数据集、协议、manifest 和分区身份；不打开 test 分区，test 的哈希仅保存为上游 receipt 的预期值。五折 scaler、模型、OOF、最终 scaler/model 与 manifest 均绑定数据集。manifest 的 `statistics` 报告 development 的分类、fold 与背景质量 bin 的事件数、负权重数、绝对权重和、平方和及有效样本量。

训练权重仍沿用每类全部选后 MC 的绝对物理权重均值归一化，包含 test 权重对该均值的影响；本次没有改变这项冻结定义。只能声明 development 不读取 test 特征/分区文件，不能宣称所有权重统计也排除了 test。

网络、λ 列表、早停、epoch、Normal AUC/KS/效率资格和阈值冻结规则不变。无合格候选是正常科学终态 `no_eligible_candidate`，不会生成 final model，也不能开启 test。Debug v2 仍只允许运行前修改 AUC/KS 两项门槛；精确 protocol bytes 与哈希保存在新 run 中。

## Test-opening

正式模式只有同一数据集的 eligible 冻结 development run 才可评价 test。开启前遵守项目的授权边界；以下命令展示接口，不代表自动授权读取任意 run 的 test。

```powershell
conda run -n pytorch higgsml-test --dataset atlas2020_4lep --train-run runs/atlas2020_4lep/development-001 --run-dir runs/atlas2020_4lep/test-001
```

可追加 `--authorization-reference <公开审计引用>` 启用持久化一次性 claim；省略时保持原有可重复评价模式，每次仍须使用新输出目录。数据集错配、模型/scaler/阈值身份不符在 claim 前拒绝。test 分区在完成 gate/可选 claim 后才校验哈希和解码，发现篡改按失败终态处理；一次性 claim 不允许重试绕过。

2025 的命令完全相同，将所有数据集名称与上游/输出路径一致替换。模型不能跨数据集用于本项目的 test-opening，即使特征列相同。test 结果不得反馈到另一套可能重叠数据的开发或候选选择。

## 验证、历史与失败

```powershell
conda run -n pytorch python -m pytest -q
```

业务退出码：参数错误 2；输入/schema/绑定错误 3；run 事务错误 4；资格/test 拒绝 5；意外内部错误 70。成功或声明的正常科学终态返回 0。下载器仍使用 0/1/2。

历史 v1 protocol 原字节与冻结/失败 runs 保留，当前加载器不做旧 manifest 推断或 mixed 回退。`config/validation/registry.json` 在独立基准登记前保持为空，authority gate 明确拒绝自行认证；当前 gate 只比较 development 特征及结构计数，不解码 test 特征。

此次软件与数据验证的实际结果见 [dataset-v2-verification.md](dataset-v2-verification.md)。所有结果均为 educational/technical demo，不能描述为 ATLAS 结果、Higgs discovery 或 physics measurement。

## 显式 debug 诊断评价

`higgsml-train --debug` 保留所有候选的资格结果和失败原因。若存在合格候选，仍按原规则选择；若没有，则按最高 development OOF AUC 选择，AUC 差值在协议的 `auc_tie_atol` 内时优先较小 λ。final fit 仍仅使用 development 数据，epoch 仍取所选候选五折 best epoch 的中位数。无论是否合格，显式 debug 训练均发布 `debug_diagnostic`，普通 test 入口拒绝该状态。

```powershell
higgsml-train --debug --dataset atlas2020_4lep --input-run runs/atlas2020_4lep/preprocess-debug-001 --protocol config/adversarial_mlp_protocol_debug_v2.yaml --run-dir runs/atlas2020_4lep/development-debug-002
higgsml-test --debug --dataset atlas2020_4lep --train-run runs/atlas2020_4lep/development-debug-002 --run-dir runs/atlas2020_4lep/test-debug-002
```

已有 `no_eligible_candidate` run 没有 final model/scaler，追加 `--debug` 也不能直接评分。须按上例在新目录重跑训练；不会修改旧 run，也不会在 test 阶段补训或选择候选。

`higgsml-test --debug` 忽略已有模型的 run/candidate eligible 资格判定及候选排名复核；只要存在已绑定的模型、scaler 和冻结阈值，非 eligible 模型也可诊断评分。它跳过预处理 lineage/分区哈希比对与训练协议封存快照校验，允许任意有限 m4l。仍校验 development 产物哈希、协议精确字节、数据集身份、固定 15 项特征、模型/scaler/阈值绑定、test 分区结构及行数。它不修改 AUC/KS 门槛，不根据 test 更新模型或阈值。metrics、manifest 和配置标记 debug，状态为 `debug_diagnostic`，不能解释为正式 test reproduction。可选授权引用仍启用一次性 claim；所有运行仍使用新输出目录。结果仅用于 educational/technical demo，不得反馈到开发选择。
