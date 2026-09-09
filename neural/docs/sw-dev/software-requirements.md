# 软件需求

本文汇总长期有效的软件需求，不记录 Sprint、负责人、完成日期或单次验收结果。科学数值定义由 `config/` 与 [`../research/`](../research/) 承载。

## 1. 数据与科学安全

| ID | 要求 | 状态 |
|---|---|---|
| DATA-01 | 所有产品路径必须 MC-only，拒绝真实数据和无法绑定的数据成员。 | 当前代码已实现 |
| DATA-02 | 每次业务调用必须显式选择受控 dataset；不同 release/collection 不得重标记、混训或共享 test 反馈。 | 当前代码已实现 |
| DATA-03 | 输入必须绑定到已审核定义、文件身份、字节摘要、profile 和科学协议；未知或重复字段失败关闭。 | 当前代码已实现 |
| DATA-04 | `source_file_id + source_entry` 标识来源行，`event_group_id` 标识物理事件组；同一事件组不得跨 split 或 fold。 | 当前代码已实现 |
| SAFE-01 | 分类器只使用冻结的 15 项特征；`m4l`、身份、provenance、split、label 和权重不得进入 classifier。 | 当前代码已实现 |
| SAFE-02 | Development 不能读取 test 分区；held-out test 不得用于训练、候选选择、阈值或协议调整。 | 当前代码已实现 |
| SAFE-03 | 冻结 run 和失败 run 不可覆盖；真实数据开放、门槛放宽或测试反馈复用需要新的明确授权和设计。 | 当前代码已实现 |

## 2. 产品与接口

| ID | 要求 | 状态 |
|---|---|---|
| API-01 | Package 必须保持独立，三个稳定产品 CLI 分别承担 preprocess、development training 和 frozen test evaluation。 | 当前代码已实现 |
| API-02 | CLI 仅作适配；同一 application 能力应可由测试直接调用，不把科学逻辑嵌入参数解析。 | 当前代码已实现 |
| API-03 | YAML/JSON 必须严格加载，拒绝未知键、缺失键、重复键、错误类型及不匹配的内部 schema。 | 当前代码已实现 |
| API-04 | 退出码保持 `0/2/3/4/5/70` 的稳定语义；错误日志和收据不得泄露 test 行、特征、分数或阈值。 | 当前代码已实现 |

## 3. 预处理

| ID | 要求 | 状态 |
|---|---|---|
| PRE-01 | 两套受控 MC 配对通过各自 profile 归一为同一 domain 输入，并执行冻结选择、重建、19 项工程变量和权重计算。 | 当前代码已实现 |
| PRE-02 | 输出必须按物理事件身份确定性分为 development/test，并发布独立文件和摘要。 | 当前代码已实现 |
| PRE-03 | 有窗/debug 输出 31 列并持久化 `train_weight`；inclusive 输出 30 列且不持久化该列。 | 当前代码已实现 |
| PRE-04 | 下载器必须使用固定 HTTPS URL、exclusive create、流式摘要、大小校验和原子改名；已存在目标不得静默复用或覆盖。 | 当前代码已实现 |

## 4. 训练与评价

| ID | 要求 | 状态 |
|---|---|---|
| TRAIN-01 | Development 使用事件组五折 OOF；scaler 只在各拟合折拟合，validation 不参与优化。 | 当前代码已实现 |
| TRAIN-02 | 候选集合、网络、损失、λ schedule、早停、工作点和资格门由 hash-bound 协议固定。 | 当前代码已实现 |
| TRAIN-03 | 只有允许终态发布 final model/scaler；`no_eligible_candidate` 和 `insufficient_statistics` 不得伪造正式模型。 | 当前代码已实现 |
| TEST-01 | Test-opening 只加载冻结模型、scaler 和阈值；不训练、不调参，并要求 preprocess/development/test 的 dataset 与 lineage 一致。 | 当前代码已实现 |
| TEST-02 | 带 authorization reference 的 test-opening 必须使用持久化 one-shot claim；claim 后成功或失败均为终态。 | 当前代码已实现 |
| TEST-03 | Debug 是显式诊断入口，状态必须为 `debug_diagnostic`，不得升级为正式资格或 test reproduction。 | 当前代码已实现 |

## 5. Artifact、质量与可维护性

| ID | 要求 | 状态 |
|---|---|---|
| ART-01 | 运行使用 staging + 原子发布，manifest-last；成功和失败证据互斥。 | 当前代码已实现 |
| ART-02 | Artifact 必须记录配置、输入、dataset、协议、lineage、SHA-256、canonical 表摘要、软件和平台。 | 当前代码已实现 |
| QA-01 | 单元测试使用 synthetic micro-ROOT 覆盖 profile、选择、身份、分区、绑定、事务和拒绝路径，不依赖 held-out test。 | 当前代码已实现 |
| QA-02 | 软件验证按 method × platform × data_scope × authority 表达；不同证据等级不得互相替代。 | 当前设计要求；权威结果需外部验证 |
| QA-03 | Authority golden 必须来自预登记独立 reference；空 registry 时不得自认证。 | 当前代码已实现；reference 需外部提供 |

## 6. 下一阶段研究软件需求

| ID | 要求 | 状态 |
|---|---|---|
| RES-01 | 新建与 legacy 产品隔离的 `src.research` 和 `higgsml-research`，只消费 development-only 研究导出。 | 最新方案规划中 |
| RES-02 | ResearchProtocol 固定 train/validation/calibration/template/assessment 五角色及反馈边界。 | 最新方案规划中 |
| RES-03 | 支持 decay7、engineered19、mass-only、MELA、条件 CDF、共同模板和 μ inference，并分别绑定算法与产物。 | 最新方案规划中 |
| RES-04 | MELA、似然、覆盖、外部 MC/系统变化和锁定 ARM64 必须有独立或权威验证后才可形成科学结论。 | 需要外部或权威验证 |

所有输出仍只能描述为 educational/technical demo。
