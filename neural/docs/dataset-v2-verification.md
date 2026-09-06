# 数据集隔离 v2 执行与验证记录

日期：2026-09-05。平台：Windows，Conda `pytorch`。这是软件实现及 MC 输入验证记录，不能替代 native osx-arm64 的权威验证。

## 实现范围

已实现两个受控配对、统一必填 `--dataset`、profile 与类别解耦、v2 分区与身份绑定、development/test reader、物理分组 fold、模型/scaler/OOF/claim 传递、development 统计以及当前文档和资源打包。共享下载器的独立实现及用户授权的一次性旧 MC 移动详见 [init-data-verification.md](init-data-verification.md)。文件保留官网原名。

新入口拒绝旧混用配置、旧单表、旧模型及跨数据集组合。旧 v1 协议原字节与历史/失败/冻结 run 保留；`xgboost/` 未改动。四轻子选择、重建、15 个网络特征、网络、λ/epoch 和 Normal 资格规则不变。fold 身份算法明确升级，不能认为新 OOF 与旧 OOF 逐值等价。

## 输入与归一化证据

四文件精确 SHA-256/大小与定义摘要见下载记录；tree entry counts、映射分支类型、身份分组数及 2025 文件内归一化字段一致性见 [dataset-input-evidence.json](dataset-input-evidence.json)。该审计只解码 MC 身份和归一化字段，没有解码轻子特征。后续预处理独立地按冻结规则生成全部 MC 分区，不应把元数据审计的“不读取特征”声明套用到预处理。

| 数据集 | Higgs 输入数 | ZZ 输入数 | Profile |
|---|---:|---:|---|
| atlas2020_4lep | 164716 | 554279 | open_data_2020 |
| atlas2025_exactly4lep | 419943 | 11260 | release22 |

2020 独立官方归一化来源：

<https://raw.githubusercontent.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/8ad2015be6d350060c3a183aff5802570bc9ada4/infofile.py>

此固定 commit 文件已通过直接 HTTPS 核实，SHA-256 为 `aa048f447d4f836dff5db7f38724823c9bc3304889607d32ae9692cdaff61241`。科学资源保留来源 master URL，此处补充实际验证的不可变 revision。

| 样本 | 有效截面 pb | 生成样本 sum of weights |
|---|---:|---:|
| 2020 Higgs 345060 | 0.0060239 | 27881776.6536 |
| 2020 ZZ 363490 | 1.2578 | 7538705.8077 |

2020 以有效截面方式使用，k-factor/filter efficiency 为 1，避免重复相乘。新 ZZ 输入绑定与历史 1.2564 pb / 7538705.808 存在已说明的差异。2025 采用文件中的 xsec × kfac × filteff / sum_of_weights；精确 float 表示及唯一值见 JSON 证据。

## 软件验证

- 针对性验证：77 项通过（新隔离、micro-ROOT、事务、test-opening）；随后 reader/隔离验证 34 项通过；补充双 profile 合成单位对照后 micro-ROOT 模块 15 项通过。
- 最终全套 pytest：**353 passed, 1 warning in 229.66s**。唯一警告为导入的 `TestOpeningResult` dataclass 不能作为 pytest 类收集，无测试失败。
- `python -m pip check`：No broken requirements found。
- `git diff --check`：通过。
- `pip wheel --no-deps --no-build-isolation .`：构建 `higgsml_neural-0.2.0-py3-none-any.whl` 成功；解压后在非仓库 cwd 使用独立 PYTHONPATH，两个数据集及 Normal v2 训练协议加载成功。

测试覆盖合成双 profile 预处理、错配在解码/claim 前拒绝、development 对 test 文件的访问哨兵、test 分区篡改、来源成员身份、物理组交集、五折确定性训练、资格终态、一次性和无 reference 模式。合成 test 测试不代表实际 MC test 已开启。

## Windows 全量预处理

两个新 run：

- `runs/atlas2020_4lep/preprocess-v2-windows-20260905-01`
- `runs/atlas2025_exactly4lep/preprocess-v2-windows-20260905-01`

截至 2026-09-05 17:34（Asia/Shanghai），两项仍在运行，尚未发布成功 manifest，未声明全量预处理通过。进程 PID 分别为 32980（2020）、33760（2025）；本地日志为 `neural/.preprocess-2020.log`、`neural/.preprocess-2025.log`。后续应仅从 manifest/cutflow 和 development 分区核对结果，不打开 test 事件表，再补记选后计数、耗时与峰值内存。上述新 run 不作为独立 golden。

## 尚未完成的科学验证

- 未在锁定 native osx-arm64 上运行全量预处理和 authority gate。独立 reference registry 保持为空，gate 明确拒绝自认证。
- 未进行两套真实数据的完整 development 候选训练或开启实际 held-out test；不能报告 AUC/KS、资格通过或 test 复现。
- 分支映射及合成等价输入只证明程序接口/单位处理；真实跨 profile 物理定义等价与跨 release 生产事件映射未证实。两套数据独立运行，不联合训练、不合并 OOF、不共享 test 反馈。
- 训练权重保留全部选后每类绝对权重均值归一化，包含 test 权重；development 不打开 test 分区，但不能声称所有训练权重统计也与 test 无关。
- 2025 ZZ 仅 11260 个上游事件。背景统计不足须按现有资格规则如实报告，不降低门槛。

所有结果仅为 educational/technical demo。
