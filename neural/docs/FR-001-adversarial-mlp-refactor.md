# FR-001 对抗式 MLP 独立工程重构

- `FR-ID`: `FR-001`
- `标题`: 对抗式 MLP 独立工程重构
- `文档状态`: 已确认，实施中
- `日期`: 2026-09-01
- `版本`: 1.1
- `所属阶段`: 阶段 1 - Neural MC-only 主线建设
- `开发顺序`: 1
- `优先级`: P0
- `前置依赖`: [`neural_adversarial_mlp_refactor_design.md`](../../neural_adversarial_mlp_refactor_design.md)
- `涉及包`: `neural/`、`neural/src/`、`neural/config/`、`neural/tests/`、`neural/docs/`
- `是否属于原型阶段`: 是
- `来源类型`: 设计补强
- `原始 SRS 章节`: 无；以已确认的重构设计为需求来源
- `相关 FR`: 无

## 目标

在 `neural/` 中建设一个不依赖 `xgboost/` 运行时代码的独立 Python 工程，将最终 MC 预处理与质量去相关训练收敛为 `higgsml-preprocess` 和 `higgsml-train` 两个可执行程序。系统应以可复现、可审计、fail-closed 的方式完成 Base14 + Angular5 预处理、对抗式 MLP development OOF 资格判断，以及仅在额外明确授权后进行的一次性 held-out MC test-opening。

该工程只用于教育与技术方法演示，不构成 ATLAS 结果、Higgs 发现或物理测量。

## 背景与问题

现有 `xgboost/` 中并存早期 Demo、多个专用冻结研究和通用训练入口，重复承担配置解析、输入绑定、输出事务、manifest、模型选择与 test-opening。新工程不迁移历史实验执行器，而是以已确认设计为唯一主线重新实现职责清晰、可测试的最终流程，同时保持原工程及其冻结产物不变。

权威 MC 基线为：Higgs 345060 selection 后 187,128 行、ZZ 363490 selection 后 11,976 行，总计 199,104 行；development 159,395 行，held-out test 39,709 行。这些数字是全量 golden 验收目标，不是普通单元测试的前置条件。

## 影响范围

- 新建 `neural/` 独立 package、`environment.yml`、权威 `osx.yml`、开发验证 `win.yml`、版本化 protocol 与示例运行配置。
- 新建预处理、domain、training、artifact 和 CLI 模块。
- 新建单元、集成、golden、CLI 与端到端 smoke 测试。
- 新建运行手册、artifact schema 与技术报告。
- 不修改 `xgboost/` 代码、配置、数据和冻结 run。

## 需求描述

### FR-001-R1 工程与对外入口

- Conda 环境名称固定为 `pytorch`；`environment.yml` 声明跨平台直接依赖，`osx.yml` 锁定权威 `osx-arm64` 环境，`win.yml` 锁定 `win-64` 开发与测试环境。
- Windows 运行只可作为开发验证，不得声明与权威 ARM64 run 精确等价。
- `pyproject.toml` 只能发布 `higgsml-preprocess` 与 `higgsml-train` 两个 console entry point。
- `neural` 运行时代码不得导入或调用 `xgboost/src`；旧工程只可作为行为比对与只读数据来源。
- CLI 只负责参数解析和调用 application service，科学计算不得放在 CLI 或 artifact 发布层。

### FR-001-R2 MC-only 行为等价预处理

- `higgsml-preprocess` 必须只读取由 run config 指定且由 protocol SHA-256 绑定的 Higgs 345060 与 ZZ 363490 ROOT。
- Selection、输入 profile、DSID、归一化、特征定义、split 算法和预期输入哈希必须由版本化 protocol 固定；普通 CLI 参数不得覆盖科学规则。
- 预处理必须保持已确认设计中的单位转换、trigger、ID、isolation、impact parameter、四轻子重建、SFOS、Z1/Z2、`m4l` selection、MC normalization、canonical identity 与稳定 split 行为。
- 输出必须包含设计规定的 19 项模型候选特征和全部非模型字段，并保持确定的列顺序和行顺序。
- 必须同时保留 signed `physical_weight` 与按类别归一化的 `abs(physical_weight)` 训练权重语义。

### FR-001-R3 固定对抗式 MLP

- v1 分类器输入只能是设计规定的 DropTop4 + Angular5 共 15 项特征。
- `m4l`、标识、provenance 和权重列不得进入分类器；缺失值、无穷值、列顺序变化或 forbidden feature 必须导致运行关闭式失败。
- 分类器、背景质量对抗器、GRL、损失、优化器、batch、epoch、早停、warm-up、lambda ramp、随机种子和 CPU deterministic 策略必须与版本化 protocol 一致。
- 对抗器只能接收背景事件的分类器 logit，并预测设计规定的 11 个固定 `m4l` bin。

### FR-001-R4 Development OOF 与资格判断

- 原 train 与 validation 必须合并为 development，并按 canonical identity 稳定划分为五折；身份不得跨 fold 或跨 split 重复。
- 必须只评估预注册的 `lambda={0.00,0.05,0.10,0.20,0.50}`，且相同 fold 的候选复用初始化种子和 batch 顺序。
- 每个候选必须产生完整、有限、每行恰好一次的 OOF 预测，以及 weighted AUC、三个工作点 KS 和信号/背景效率证据。
- 资格必须同时满足 OOF AUC `>= 0.80`、三个 ZZ `m4l` KS `<= 0.10`，以及各工作点信号效率严格高于 achieved ZZ efficiency。
- 多个候选合格时选择 OOF AUC 最高者；绝对差不超过 `1e-6` 时选择较小 lambda。
- 无合格候选时终态必须为 `no_eligible_candidate`，不得生成最终模型或允许 test-opening。
- 有合格候选时，只可使用全部 development 数据拟合并封存 scaler 和模型；最终 epoch 数取五折最佳 epoch 的中位数并取最近整数，不得读取 test 特征或重新早停。

### FR-001-R5 显式一次性 test-opening

- `higgsml-train open-test` 必须是独立子命令，且只有在 development run 已冻结、eligible、证据哈希完整并获得用户另行明确授权时才可执行。
- 必须通过原子 claim 占用唯一 test-opening 槽位；成功或失败均写收据，重复开启必须被拒绝。
- Test 只能评价冻结模型与 OOF 冻结阈值，结论只能是 `test_reproduced` 或 `test_nonreproduction`。
- Test 结果不得触发重训、调参、改阈值、扩展候选或放宽门槛。

### FR-001-R6 Artifact、审计与不可覆盖

- 新 run 目录必须默认不可覆盖；输出目录必须位于允许的 `neural/runs/` 根下。
- 预处理、development 与 test run 必须按设计发布配置快照、指标、预测、图、manifest 和 SHA-256。
- Gzip 输出除文件哈希外还必须记录解压后 canonical CSV 内容哈希。
- Manifest 必须记录 protocol、输入、输出、软件、Git、平台、事件数、列 schema、deterministic 设置与性能信息。
- 失败 run 也必须保留失败收据，不得伪装为成功或悄然复用旧产物。

### FR-001-R7 测试与文档

- 必须覆盖设计第 12 节规定的预处理、训练、golden、集成、CLI 和端到端 smoke 测试。
- 必须验证模型输入输出 shape、精确参数量、GRL 梯度符号、背景限定、权重归一化、fold scaler 无泄漏、资格规则和 test-opening 拒绝路径。
- 必须提供 README、环境恢复命令、运行手册、artifact schema 和最终技术报告。
- 全量权威 run 必须发布五个候选的五折 OOF 证据；性能不合格是合法科学结论，不得为了得到模型而改变规则。

## 高层要求

- 所有实现必须遵守仓库根 [`AGENTS.md`](../../AGENTS.md) 的科学安全、冻结 run、证据边界与教育/技术演示措辞约束；`neural/AGENTS.md` 只能补充更具体规则，不能放宽根规则。
- 科学规则与环境依赖写入版本化 protocol/lock；运行配置只允许承载路径和资源参数。
- Domain 计算、I/O、pipeline、训练、资格判断、test-opening 与 artifact 发布保持单一职责边界。
- 所有会影响资格或 test-opening 的输入均须内容寻址并在使用前校验。
- Test 对 development 单向依赖；development 的任何阶段都不得读取 test 特征值。
- 原始 ROOT 通过外部只读路径使用，不复制到源码仓库。
- 冻结 run 和旧工程产物不可变；新实验必须使用新的配置和唯一 run path。

## 输入

- Higgs 345060 ROOT，预期 SHA-256：`5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0`。
- ZZ 363490 ROOT，预期 SHA-256：`76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`。
- `preprocess_protocol_v1.yaml`、本地 preprocess run config。
- `adversarial_mlp_protocol_v1.yaml`、已完成的 preprocess run。
- 对 `open-test` 而言：eligible 且冻结的 development run，以及另行明确的用户授权。

## 输出

- 预处理 run：canonical MC 表、cutflow、MC summary、配置快照和 manifest。
- Development run：候选/折指标、qualification、working points、OOF 分数、图、manifest；仅 eligible 时包含模型和 scaler。
- Test run：冻结模型的 test 指标、预测、图和 manifest。
- Development run 中唯一的 test-opening 审计状态/收据。

## 失败与降级

- 输入哈希、schema、列顺序、有限性、身份唯一性、配置或 artifact 绑定失败时终止，不尝试猜测、修复或兼容降级。
- 输出目录已存在、越过允许根目录或事务发布不完整时终止并保留失败证据。
- 无合格候选是正常终态，不生成模型，不访问 test。
- 无资格、证据被篡改、已有 claim 或缺少显式授权时拒绝 `open-test`。
- CPU deterministic 能力不可满足时不得宣称权威精确复现；跨平台运行只能作为开发验证。

## 不纳入范围

- 任何真实数据的读取、哈希、预处理、评分、绘图或结论。
- 历史 Full14、删特征消融、质量重加权、KNN flatness 执行器迁移。
- OmniLearn/PET、扩散生成、异常检测、likelihood-ratio estimation。
- 系统误差、控制区、sideband、质量谱 likelihood 或正式物理统计结论。
- 以失败结果为由增加候选、调结构、放宽 AUC/KS 门槛或自动开启 test。

## 最小验证方式

- 权威平台：`conda-lock install --name pytorch osx.yml`
- Windows 开发平台：`conda-lock install --name pytorch win.yml`
- `conda run -n pytorch python -m pip check`
- `conda run -n pytorch python -m pytest -q`
- 两个 CLI 的 `--help` smoke test。
- 微型 ROOT 全链、确定性小型训练和 test-opening 关闭式失败集成测试。
- 在具备权威只读 ROOT 时执行全量预处理 golden；development 全量训练须作为独立、可审计运行。

## 验收要点

- `neural/` 可独立安装，运行时不导入 `xgboost/src`，且只有两个对外程序。
- 全量预处理得到 199,104 行、规定的 19 项特征和完整 provenance，Higgs/ZZ 数量分别为 187,128/11,976。
- v1 模型只消费固定 15 项特征，禁止字段与 test 数据均无法泄漏进 development 决策。
- 五候选五折 OOF、工作点、资格门槛、tie-break 和终态均严格遵循 protocol。
- 无合格候选时没有模型和 test artifact；有合格候选时仍需显式、单次 test-opening。
- 所有成功与失败结论均可由配置、哈希、指标、图、manifest、收据和自动化测试追溯。
- `xgboost/` 与其冻结数据、配置、run 完全未修改。

## 备注

- 本 FR 的实施拆分为 `sprint-m1-01` 至 `sprint-m1-06`，必须按顺序完成。
- `open-test` 不因本 FR 或任一 Sprint 文档的存在而获得授权；届时仍须用户单独明确批准。
- 文档路径按本次任务显式解析为 `FR_DIR=SPRINT_DIR=neural/docs/`；当前只完成文档编写，尚未完成评审确认、实现、验证或交付。
