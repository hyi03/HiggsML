# FR-001 Angular19 XGBoost 科学行为等价重构

- `FR-ID`: `FR-001`
- `标题`: Angular19 XGBoost 科学行为等价重构
- `所属阶段`: 阶段 1 - XGBoost 工程重构
- `开发顺序`: 1
- `优先级`: P0
- `前置依赖`: [重构设计](../superpowers/specs/2026-09-01-xgboost-refactor-design.md)
- `涉及包`: `src/`、`scripts/`、`config/`、`tests/`、`docs/`
- `是否属于原型阶段`: 否
- `来源类型`: 技术债治理
- `原始 SRS 章节`: 无
- `相关 FR`: 无

## 目标

把现有 `xgboost/` 重构为职责清晰、MC-only、protocol 驱动、产物可审计的 XGBoost
工程。最终分类器固定使用 Base14 + Angular5 共 19 项特征，科学计算和训练行为与现有
实现等价；历史研究入口、真实数据入口和通用预测入口全部移除。

## 背景与问题

当前工程已经实现 ROOT 预处理、XGBoost、OOF、工作点、manifest 和测试，但历史研究
逐步形成多个专用脚本和重复 run 层。科学逻辑、应用编排、产物事务和绘图散布于平铺
模块，配置还允许普通 CLI 覆盖科学参数。Development 与 held-out test 共用处理表，
隔离主要依赖运行逻辑而不是文件边界。

本 FR 以已批准设计为唯一设计来源，不授权新的科学实验或调参。

## 影响范围

- 新增 `pyproject.toml`、版本化 preprocessing/XGBoost protocol 和两个 console scripts；
- 将代码重组为 `src/cli`、`src/config.py`、`src/domain`、`src/preprocessing`、
  `src/training`、`src/artifacts`；
- 预处理直接输出 Angular19，并物理分离 development/test 表；
- 新建 development 与一次性 test-opening 生命周期；
- 删除历史专用脚本、仅供历史执行流使用的实现与配置；
- 删除真实数据和通用 `predict` 代码；
- 重构测试目录并更新当前文档、历史冻结索引和命令示例。

## 需求描述

### R1 工程结构

- 新实现直接位于 `src/`，不得使用 `src/higgsml_xgboost/` 包装层。
- CLI 不包含科学计算；domain 不依赖 CLI、文件系统事务、绘图或 XGBoost。
- 不为不存在的第二种数据库、训练器或远程后端预建端口抽象。

### R2 MC-only 预处理

- 只接受 DSID 345060 Higgs MC 与 DSID 363490 连续 ZZ MC。
- 等价迁移当前 input profile、selection、normalization、权重、identity 和稳定 split。
- 直接产生固定顺序的 Base14 + Angular5 共 19 项模型特征。
- 将 development 与 held-out test 发布为独立 CSV.GZ，并记录压缩与 canonical 内容哈希。
- 不定义真实数据输入类型，也不读取、哈希、评分、绘制或盘点真实数据。

### R3 冻结 protocol 与 CLI

- 发布 `higgsml-preprocess` 和 `higgsml-xgboost` 两个程序。
- `higgsml-xgboost` 只包含 `develop` 与 `open-test`。
- 普通 CLI 不得覆盖特征、selection、权重、split、fold、XGBoost 参数、候选、工作点或
  资格门槛。
- 未知 schema、未知字段、重复字段、错误类型和非有限值必须 fail closed。

### R4 科学行为等价

- 保持现有 Base14、Angular5 数学与列顺序。
- 保持 signed `physical_weight` 与按类别归一化 `abs(physical_weight)` 训练权重。
- 保持 stable split、5-fold development OOF、XGBoost fit/early stopping 和最终树数语义。
- V1 固定现有 angular19 profile、单候选参数和三个工作点。
- 整数、identity、split、fold、schema 和终态精确相等；浮点等价规则必须在看到迁移
  差异前由 golden tests 固定。

### R5 Development 与资格门控

- `develop` 只能读取 development 文件。
- 发布候选、fold、OOF、工作点、AUC、KS、效率和 qualification 证据。
- 资格门槛固定为 weighted OOF AUC `>= 0.80`、三个 ZZ KS `<= 0.10`、三个工作点
  signal efficiency 严格高于 achieved background efficiency，且 OOF 预测完整、有限，
  每个 development 事件恰好出现一次。
- `no_eligible_candidate` 是正常终态；不得发布模型，也不得允许 test-opening。
- Eligible 时才使用全部 development 行拟合并封存最终 XGBoost 模型。

### R6 一次性 test-opening

- `open-test` 必须校验上游 manifest、protocol、输入、模型、工作点和 OOF 全部绑定。
- 通过原子 claim 保证一个 development run 只能开启一次 test；失败也消耗开启权。
- Test 只评价冻结模型，不得触发训练、调参、改阈值或回写 development 决策。

### R7 Artifact 与失败语义

- 所有 run 目录全新且不可覆盖，不提供 `--overwrite`。
- 输出在读取输入前原子占用；路径逃逸、symlink、输入替换和未知布局均拒绝。
- 失败 run 写失败收据但不写成功 manifest。
- Manifest 绑定 protocol、配置、代码、软件、输入、输出、schema、计数和哈希。

### R8 历史执行面移除

- 删除历史专用 CLI、真实数据 CLI、通用 `predict` 及仅服务于它们的实现。
- 删除前通过依赖图与测试映射确认共享科学函数已经迁移。
- 必要历史结论以只读索引保留，不再展示已删除命令为当前入口。

## 高层要求

- 遵守 `AGENTS.md` 的科学安全与不可变 run 约束。
- 不修改或复用现有冻结 runs、models、predictions、plots 和 manifests。
- `m4l`、identifier、provenance 和 weight 字段不得进入模型。
- 不使用真实数据监督训练，不用 held-out test 做任何选择。
- 结果只能描述为教育/技术 Demo。
- 用户授权按全部 Sprint 自动执行；不设置中途人工确认，但独立文档/代码评审与
  review-confirm 证据不得跳过。

## 输入

- `preprocessing_protocol_v1.yaml`；
- 本地 `preprocessing_run` YAML，只含 ROOT 路径和资源参数；
- DSID 345060 Higgs ROOT 与 DSID 363490 ZZ ROOT；
- `xgboost_protocol_v1.yaml`；
- 全新的 run 目录。

## 输出

- 不可变 preprocess run：development/test 表、cutflow、summary、manifest；
- development run：OOF、候选/fold 指标、工作点、qualification、图及可选模型；
- test run：test scores、指标、图和 manifest；
- FR、Sprint、评审确认、验证与提交证据。

## 失败与降级

- 输入、配置、protocol、schema 或哈希不符时立即失败，不做隐式修复。
- 不合格候选保留完整证据并正常结束，不降级门槛。
- 缺少真实 ROOT 时允许完成合成/微型 fixture 验证，但不得声称权威 ROOT 已复现。
- 任一 Sprint 的文档评审、代码评审、验证或提交失败时停止后续 Sprint 并记录阻塞点。

## 不纳入范围

- 新模型、去相关算法、重加权或参数搜索；
- 真实数据、sideband、系统误差和统计拟合；
- 自动执行真实规模训练或 held-out test-opening；
- 兼容历史 CLI 的 wrapper；
- 修改冻结 run 或把历史失败结论改写为成功。

## 最小验证方式

- 每个 Sprint 的专项 pytest；
- `python -m pytest -q`；
- 两个 CLI 的 `--help` 与错误路径 smoke；
- 微型 ROOT preprocess -> develop -> eligible fixture open-test；
- 原实现与新实现的 characterization/golden 等价检查；
- 被删除模块/命令不可导入、不可执行检查。

## 验收要点

- 目标目录、CLI 和 protocol 与批准设计一致。
- 模型特征恰好为固定顺序的 19 项。
- Development 不读取 held-out test 文件。
- 不合格 run 无模型且无法开启 test。
- Eligible run 的 test 只能开启一次。
- 不存在真实数据和通用 predict 执行面。
- 完整测试通过，未执行的权威 ROOT/真实训练/test-opening 边界被明确记录。
- 全部 Sprint 各自完成文档评审确认、代码评审确认、验证和独立提交。

## 备注

路径解析（相对 `xgboost/`）：

- `FR_DIR=docs/1-Requirement`
- `FR_BACKLOG_DIR=docs/1-Requirement/backlog`
- `FR_DONE_DIR=docs/1-Requirement/Done`
- `DESIGN_DIR=docs/2-Design`
- `SPRINT_DIR=docs/3-Plan`
- `SPRINT_DONE_DIR=docs/3-Plan/Done`
- `REVIEW_DIR=docs/4-Reviews`
- `REVIEW_DONE_DIR=docs/4-Reviews/Done`
- `VERIFICATION_COMMANDS=python -m pytest -q`，来源为 `xgboost/AGENTS.md`

实施拆分为 `sprint-m1-01` 至 `sprint-m1-06`，必须严格顺序执行。设计阶段映射为：
M1-01 合并阶段 1（worktree/基线）与阶段 2（骨架/protocol）；M1-02 至 M1-06 分别对应
设计阶段 3 至阶段 7。
