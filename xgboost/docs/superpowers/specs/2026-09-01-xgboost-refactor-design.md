# HiggsML XGBoost 科学行为等价重构设计

## 1. 方案摘要

本设计在 `xgboost/` 内重建一个结构清晰、MC-only、产物可审计的 XGBoost 工程。
重构保持现有科学行为等价：selection、特征定义、权重、稳定数据划分、development
五折 OOF、XGBoost 参数与候选选择语义均不得改变。允许改变的是代码架构、CLI、配置
封装、产物布局和生命周期门控。

重构完成后仅保留两个可执行程序：

```text
higgsml-preprocess
higgsml-xgboost develop|open-test
```

现有历史专用脚本、历史研究实现、真实数据处理和通用预测入口全部从可执行工程移除。
必要的冻结结论、run 路径、manifest 标识和科学限制保留在精简的历史文档中。

## 2. 当前工程事实与重构动机

当前 `xgboost/` 已具备完整的 ROOT 预处理、XGBoost 训练、OOF、工作点、manifest、
绘图和测试能力，也包含大量为既往研究单独建立的执行流。主要问题不是科学计算缺失，
而是工程边界随研究历史累积：

- `src/` 为平铺模块，domain、application service、文件系统事务和绘图职责混杂；
- 多个 `*_run.py` 分别实现相似的输出占用、哈希验证、manifest 和失败处理；
- `scripts/` 同时包含通用入口、历史入口、真实数据入口和辅助入口；
- 普通 CLI 可以覆盖特征和超参数，不适合冻结协议驱动的资格评估；
- development 与 held-out test 共存于同一处理表，逻辑隔离强于物理隔离；
- 历史冻结研究和当前可维护产品代码之间缺少明确边界。

本重构以“删除历史执行面、统一当前主链、增强生命周期隔离”为目标，不借机重新设计
算法或追逐新的科学结果。

## 3. 已批准的设计决定

1. 重构路径采用“分层重建、行为迁移”，不是原地清理，也不采用完整端口适配器架构。
2. 新代码直接位于 `src/`；不增加 `src/higgsml_xgboost/` 包装层。
3. 所有历史专用命令及其仅有实现代码完全移除。
4. 新系统严格 MC-only，只处理 Higgs MC 与连续 ZZ MC。
5. 删除真实数据读取、评分、绘图及通用 `predict` 能力。
6. 配置采用版本化 protocol；普通 CLI 只有输入、protocol、run 配置和新 run 目录参数。
7. “算法保持 XGBoost 不变”解释为科学行为等价重构。
8. 对外提供 `higgsml-preprocess` 与 `higgsml-xgboost` 两个程序。
9. Development 不合格时不发布最终模型，也不得开启 test。
10. 合格 development run 的 held-out test 只能显式开启一次。

## 4. 范围与非目标

### 4.1 本次范围

- 以 characterization 和 golden tests 锁定当前科学行为；
- 将科学计算迁入职责单一的 domain 模块；
- 建立独立的 preprocessing、training、artifacts 和 CLI 层；
- 把当前配置值转录为不可由普通 CLI 覆盖的版本化 protocol；
- 将 development 和 held-out test 发布为独立文件；
- 统一不可覆盖 run、manifest、哈希、失败收据和一次性 test-opening；
- 删除历史专用代码、真实数据代码和通用预测入口；
- 更新 README、项目总览、运行说明和历史冻结索引；
- 建立单元、集成、golden、CLI 和端到端 smoke 测试。

### 4.2 非目标

- 不改变 XGBoost 模型家族、损失或训练器；
- 不改变 selection、特征数学定义、权重、split、fold 或候选选择语义；
- 不新增、删除或事后挑选模型特征；
- 不修改 XGBoost 参数、候选网格、工作点或资格门槛；
- 不读取、哈希、预处理、评分、绘制或盘点真实数据；
- 不打开任何现有冻结 run 的 held-out test；
- 不复用或覆盖现有 run、模型、预测、图或 manifest；
- 不引入新去相关算法、重加权实验或超参数研究；
- 不增加系统误差、控制区、sideband 或质量谱 likelihood；
- 不把结果描述为 ATLAS 结果、Higgs 发现或物理测量。

## 5. 目标工程结构

```text
xgboost/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── preprocessing_protocol_v1.yaml
│   ├── preprocessing_run.example.yaml
│   └── xgboost_protocol_v1.yaml
├── src/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── preprocess.py
│   │   └── xgboost.py
│   ├── config.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── four_vectors.py
│   │   ├── reconstruction.py
│   │   ├── selection.py
│   │   ├── features.py
│   │   ├── weights.py
│   │   └── splitting.py
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── root_reader.py
│   │   ├── pipeline.py
│   │   └── outputs.py
│   ├── training/
│   │   ├── __init__.py
│   │   ├── dataset.py
│   │   ├── model.py
│   │   ├── folds.py
│   │   ├── trainer.py
│   │   ├── evaluation.py
│   │   ├── qualification.py
│   │   └── test_opening.py
│   └── artifacts/
│       ├── __init__.py
│       ├── manifest.py
│       ├── transaction.py
│       └── plots.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   └── fixtures/
├── data/
│   └── .gitkeep
└── runs/
    └── .gitkeep
```

各层职责如下：

- `domain`：纯科学计算；不得导入 CLI、文件系统事务、绘图或 XGBoost。
- `preprocessing`：MC ROOT I/O 与预处理用例编排。
- `training`：数据校验、fold、XGBoost 训练、OOF、工作点、资格和 test-opening。
- `artifacts`：不可覆盖事务、manifest、哈希、收据与绘图发布。
- `cli`：参数解析、异常映射和 application service 调用，不承载科学计算。

该结构只为当前单机、单算法、文件产物工作流建立必要边界，不为不存在的第二种数据库、
训练器或远程执行后端预建抽象接口。

## 6. CLI 契约

`pyproject.toml` 发布：

```toml
[project.scripts]
higgsml-preprocess = "src.cli.preprocess:main"
higgsml-xgboost = "src.cli.xgboost:main"
```

### 6.1 MC 预处理

```bash
higgsml-preprocess \
  --protocol config/preprocessing_protocol_v1.yaml \
  --run-config config/preprocessing_run.local.yaml \
  --run-dir runs/preprocess-<unique-id>
```

Run config 只允许指定 Higgs/ZZ ROOT 路径、chunk size 和资源参数。Selection、样本
metadata、特征、权重、split 算法及内容约束位于 protocol。CLI 不提供这些科学规则的
覆盖项。

### 6.2 Development 训练

```bash
higgsml-xgboost develop \
  --input-run runs/preprocess-<id> \
  --protocol config/xgboost_protocol_v1.yaml \
  --run-dir runs/xgboost-development-<unique-id>
```

`develop` 只读取 development 文件，完成既有五折 OOF、候选比较、工作点冻结和资格
判断。所有候选证据均发布。只有合格时，才使用全部 development 行拟合并封存最终
XGBoost 模型；最终树数继续取所选候选五个 fold 的 `best_iteration + 1` 中位数并按
现有规则取整。

### 6.3 显式 test-opening

```bash
higgsml-xgboost open-test \
  --development-run runs/xgboost-development-<id> \
  --run-dir runs/xgboost-test-<unique-id>
```

`open-test` 验证 development manifest、protocol、预处理输入、模型、工作点和 OOF
证据均未改变，并要求状态为 eligible。命令通过原子 claim 占用唯一开启槽位；成功或
失败均留下收据，后续重复开启被拒绝。Test 只评价冻结模型，不参与任何训练或决策。

### 6.4 明确删除的 CLI 能力

- 不提供 `--overwrite`；
- 不提供特征开关和 feature profile 覆盖；
- 不提供 XGBoost 参数、候选网格、seed、fold 或工作点覆盖；
- 不提供 `predict`；
- 不提供真实数据入口；
- 不发布历史研究子命令或兼容 wrapper。

## 7. Protocol 与配置契约

### 7.1 预处理 protocol

`preprocessing_protocol_v1.yaml` 固定：

- schema version；
- Higgs 与 ZZ 的可信 channel/DSID metadata；
- ROOT tree 与字段 profile；
- 单位转换；
- selection 配置；
- 特征定义和列顺序；
- signed `physical_weight` 与训练权重语义；
- canonical event identity；
- train/validation/test 稳定划分算法与 seed；
- 禁止模型字段；
- 输入内容约束及需要记录的 SHA-256。

### 7.2 XGBoost protocol

`xgboost_protocol_v1.yaml` 固定：

- schema version；
- 当前获准的特征列及顺序；
- 当前 XGBoost 公共参数；
- 当前候选参数及展开顺序；
- `n_estimators`、early stopping、seed、线程与 tree method；
- development fold 数与分配算法；
- 候选选择及 tie-break 语义；
- loose、medium、tight 工作点；
- AUC、KS 和效率资格门槛；
- 最终树数规则；
- 允许生成的产物及 schema version。

V1 的唯一迁移权威是当前通用入口 `scripts/higgsml.py`、`src/experiment_config.py`、
`src/experiment_runner.py` 和 `config/experiment_training.yaml`，不是任何历史专用研究流。
V1 固定当前通用配置的 Base14：

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ
```

V1 固定一个当前默认候选：`learning_rate=0.05`、`max_depth=3`、
`min_child_weight=5`、`subsample=0.8`、`colsample_bytree=0.8`、
`reg_alpha=0.1`、`reg_lambda=2.0`；公共训练参数固定为 `n_estimators=1000`、
`early_stopping_rounds=50`、`random_seed=42`、`n_jobs=1`、`tree_method=hist`、
`folds=5`。Loose、medium、tight 目标背景效率分别为 `0.50`、`0.20`、`0.10`。

这些值必须从当前实现逐项转录，并先由 characterization tests 证明等价。转录过程中
不得“顺便”修正、优化或现代化科学参数。未来增加候选、Angular5 或改变任一参数均需
新 protocol 版本、新设计和新 run path。

### 7.3 配置优先级

新系统不存在科学参数的多层覆盖。优先级只有：

1. 版本化 protocol 定义科学行为；
2. run config 定义本地路径和资源；
3. CLI 指定采用哪些文件及新 run 目录。

未知字段、重复字段、错误类型、非有限数值或未知 schema version 均 fail closed。

## 8. 数据契约与科学行为等价

### 8.1 输入与范围

预处理 V1 只接收 channel/DSID `345060` 的 Higgs MC 和 `363490` 的连续 ZZ MC；输入
profile、官方 normalization metadata、selection 和 lepton-quality 规则从当前
`config/dsid363490.yaml` 的 MC 部分等价迁移，其中的真实数据配置不迁移。每个 ROOT
输入在读取前后验证常规文件状态与内容记录，不允许以文件名猜测 channel number。
真实数据不属于新 package 的输入类型。

### 8.2 必须保持的行为

- 当前 MeV/GeV 处理；
- 当前四轻子重建、SFOS 配对和 Z1/Z2 决策；
- 当前逐级 selection 与 cutflow；
- 当前特征数学定义、名称和列顺序；
- 当前 MC normalization；
- signed `physical_weight` 用于物理产额；
- XGBoost 使用按类别归一化的 `abs(physical_weight)`；
- 当前 canonical identity 和稳定 split；
- 当前 development fold 分配；
- 当前 XGBoost fit、early stopping、候选比较和最终树数语义；
- 工作点继续只由 development OOF ZZ 的绝对物理权重确定；
- `m4l`、标识、provenance 和权重字段不得进入模型。

### 8.3 预处理输出

```text
runs/preprocess-<id>/
├── config.yaml
├── processed/
│   ├── development.csv.gz
│   └── test.csv.gz
└── artifacts/
    ├── cutflow.json
    ├── mc_summary.json
    └── manifest.json
```

分文件发布只改变存储边界，不改变事件的 split 归属或行内容。为避免 gzip metadata
造成伪差异，manifest 同时记录压缩文件 SHA-256 与解压后 canonical CSV 内容哈希。

## 9. Training 数据流与资格门控

```text
Higgs/ZZ ROOT
  -> higgsml-preprocess
  -> immutable preprocess run
  -> development.csv.gz
  -> higgsml-xgboost develop
  -> five-fold OOF and candidate evidence
  -> frozen working points and qualification
  -> eligible: final XGBoost model
  -> higgsml-xgboost open-test
  -> test.csv.gz read exactly once for evaluation
```

候选训练与选择完全沿用现有语义。资格门控不改变候选训练结果，只决定最终模型是否可以
被发布及 test 是否可以开启。资格条件保持当前冻结政策：

- weighted development OOF AUC 不低于 `0.80`；
- loose、medium、tight 三个 OOF ZZ `m4l` KS 均不高于 `0.10`；
- 每个工作点的 signal efficiency 严格高于 achieved background efficiency；
- OOF 预测完整、有限，且每个 development 事件恰好出现一次。

若 V1 的固定候选不合格，终态为 `no_eligible_candidate`，发布完整失败证据但不发布
模型，也不允许 `open-test`。V1 不包含运行时网格或多候选 tie-break。未来 protocol
若预注册多个候选，必须明确复用当时获批的候选排序语义；不得在结果产生后补充规则。

## 10. 产物契约

### 10.1 Development run

```text
runs/xgboost-development-<id>/
├── config.yaml
├── artifacts/
│   ├── candidate_metrics.csv
│   ├── fold_metrics.csv
│   ├── qualification.json
│   ├── working_points.json
│   └── manifest.json
├── predictions/
│   └── oof_scores.csv.gz
├── model/                       # only when eligible
│   └── model.json
├── plots/
└── state/
    └── test_opening.json        # created by open-test claim
```

### 10.2 Test run

```text
runs/xgboost-test-<id>/
├── artifacts/
│   ├── test_metrics.json
│   └── manifest.json
├── predictions/
│   └── test_scores.csv.gz
└── plots/
```

Manifest 记录 protocol/config、输入与输出哈希、代码版本、软件环境、行数、schema、特征、
候选、工作点、资格决定和上游 run 绑定。一个 run 只有在最终 manifest 原子发布后才算
成功。

## 11. 失败处理与不可变性

- run 路径必须全新，且位于允许的 `runs/` 根下；
- 输出目录在任何输入解析前原子占用；
- writer 不覆盖任何已存在目录项；
- symlink、路径逃逸、未知文件布局和被替换输入均被拒绝；
- protocol、输入和上游 manifest 在关键阶段重复校验；
- 失败 run 写入终态失败收据，不写成功 manifest；
- `no_eligible_candidate` 是成功执行后的科学终态；
- 已发布 manifest 和冻结 run 不可变；
- test-opening claim 一旦成功占用，后续成功或失败均不得再次开启；
- test 结果不触发重训、改阈值、改候选或回写 development 决策。

## 12. 历史代码与文档处置

最终实现中删除：

- 所有历史专用 `scripts/*.py`；
- `evaluate_data.py`、通用 `predict` 及真实数据路径；
- 仅为 Angular5 enrichment、identity、mass ablation、mass-bin reweighting、
  decorrelation、external ZZ 和旧 full-training run 服务的执行模块；
- 与被删除入口一一对应、且不再保护当前主链行为的测试；
- 可由新 protocol 和主链替代的重复配置。

删除前必须完成依赖图和测试映射，确认共享科学函数已经迁移并由新测试覆盖。不得仅凭
文件名判断模块可删除。

历史文档收敛为只读索引，至少保留：

- 研究名称、日期和冻结终态；
- run 路径与关键 manifest/hash 标识；
- 是否发布模型、是否开启 test、是否访问真实数据；
- 关键 AUC/KS 结论；
- 不得继续调参、覆盖产物或把结果解释为物理测量的边界。

历史文档不得继续展示已删除命令为当前可运行入口。

## 13. 测试设计

### 13.1 Characterization 与 golden tests

在迁移前锁定：

- selection 边界、cutflow 和事件计数；
- SFOS 配对、Z1/Z2、四动量和特征值；
- signed/absolute 权重及类别归一化；
- canonical identity、split 和 fold；
- protocol V1 与当前配置的逐项对应；
- XGBoost 候选参数、OOF、候选选择和最终树数；
- 工作点、AUC、KS、效率和资格决定；
- 模型保存、加载和预测。

### 13.2 单元测试

- protocol schema、未知字段和禁止覆盖；
- 缺失列、非法列序、NaN、无穷值和 forbidden feature；
- ROOT branch、channel/DSID 和单位校验；
- artifact 原子占用、no-clobber、哈希和 manifest；
- eligible、no-eligible 和异常中止；
- test-opening 的哈希变化、重复调用与失败后重试拒绝。

### 13.3 集成与端到端测试

- 微型 ROOT fixture 执行完整 preprocess；
- preprocess run 驱动小型 `develop`；
- 相同输入重复预处理的 canonical 内容哈希一致；
- 小型 XGBoost 训练保存后预测一致；
- `no_eligible_candidate` 不生成模型；
- eligible fixture 只允许一次 `open-test`；
- CLI `--help`、成功退出码和错误退出码；
- 被删除命令和模块不可导入、不可执行。

### 13.4 等价精度政策

整数、类别、身份、split、fold、列名、列顺序和资格终态必须精确相等。确定性字符串、
JSON schema 和 protocol 内容必须精确相等。浮点特征、OOF 分数、指标和模型预测使用在
迁移前由 golden tests 固定的精度规则；不得在看见重构差异后放宽容差。若当前权威
平台要求 bitwise equivalence，则对应检查保持 bitwise，不改成近似比较。

## 14. 实施阶段

### 阶段 1：隔离 worktree 与建立行为基线

- 在用户批准本设计后创建独立 Git worktree；
- 记录 worktree、分支、Git 状态和 Python 环境；
- 运行现有完整测试并保存基线；
- 添加 characterization/golden tests，不改变生产行为。

验收：现有测试及新增行为基线通过，未读取真实数据，未修改冻结 run。

### 阶段 2：工程骨架与 protocol

- 添加 `pyproject.toml` 和目标 package 结构；
- 转录 preprocessing/XGBoost protocol V1；
- 建立两个 CLI 的 parser、帮助和空 application service 边界；
- 建立统一 artifact transaction 与 manifest 基础设施。

验收：两个 `--help` 可运行；protocol schema 测试和 artifact 事务测试通过。

### 阶段 3：Domain 与预处理迁移

- 迁移四动量、重建、selection、特征、权重和 split；
- 迁移 MC ROOT reader 与 pipeline；
- 发布分离的 development/test 文件；
- 用 characterization、微型 ROOT 和现有权威计数验证等价。

验收：事件、cutflow、列、特征、权重和 split 满足等价政策。

### 阶段 4：XGBoost development 迁移

- 迁移 frame 校验、fold、候选训练、OOF、选择和最终树数；
- 迁移工作点、AUC/KS/效率与资格；
- 只在 eligible 时发布最终模型；
- 发布完整 development artifact。

验收：候选、fold、OOF、工作点和模型预测满足等价政策；test 文件未被读取。

### 阶段 5：一次性 test-opening

- 实现上游 binding、完整哈希复核与原子 claim；
- 加载冻结 XGBoost 模型并发布 test 指标；
- 覆盖重复开启、篡改、缺失证据和失败终态。

验收：只有 eligible、完整、未开启的 development run 能消费其绑定 test 一次。

### 阶段 6：删除历史执行面

- 依据依赖图删除历史脚本、实现、配置和冗余测试；
- 删除真实数据和通用 predict 代码；
- 保留精简历史冻结索引；
- 更新所有当前文档和命令示例。

验收：源码和文档中不存在可执行历史入口；共享科学行为仍由新测试覆盖。

### 阶段 7：全链验证与交付

- 运行聚焦测试、完整 pytest、CLI smoke 和静态导入检查；
- 在可用时运行权威 MC ROOT 预处理等价验证；
- 不自动执行真实规模训练或 `open-test`；
- 记录已验证项、未验证项和证据边界。

验收：全部授权检查通过，未授权的运行保持未执行并被明确报告。

## 15. 总体验收标准

重构只有在以下条件全部满足时才算完成：

1. 新代码直接使用 `src/` 分层结构，没有 `src/higgsml_xgboost/`。
2. 对外只有 `higgsml-preprocess` 和 `higgsml-xgboost` 两个程序。
3. 新系统只接受 Higgs/ZZ MC，不包含真实数据或通用 predict 执行面。
4. 普通 CLI 不能覆盖任何科学参数。
5. 现有 selection、特征、权重、split、fold 和 XGBoost 训练语义通过等价验证。
6. Development 不读取 test 文件，test 不参与训练、选择、工作点或资格判断。
7. 不合格 run 发布完整证据但不发布模型，也不能开启 test。
8. 合格 run 的 test 只能显式开启一次，篡改或重复开启均被拒绝。
9. run 不可覆盖，成功、失败和科学不合格终态均有明确收据。
10. 历史专用代码已删除，必要冻结结论保留为只读文档。
11. 现有冻结 runs、models、predictions、plots、manifests 和用户未提交修改未被改变。
12. 所有结论都注明测试、环境、输入和未执行验证的边界。

## 16. 实施前门禁

本设计文档获用户明确批准后，下一步才是：

1. 创建独立 worktree；
2. 编写决策完备的实施计划；
3. 按小工作包实施并验证。

设计批准不自动授权真实规模训练、held-out test-opening 或任何真实数据访问。这些动作
若未来需要，必须另行获得明确授权。
