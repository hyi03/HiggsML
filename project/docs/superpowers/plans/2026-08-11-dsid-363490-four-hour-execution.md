# DSID 363490 Four-Hour Execution Runbook

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute the existing implementation plan and preserve independent review gates.

**Goal:** 在约四小时无人值守窗口内，尽可能完成 DSID 363490 的真实预处理、统计门禁、MC 训练、125 GeV 质量峰检查、DSID 700600 冻结外部验证、文档和最终审计。

**Architecture:** 本文件不替代 `2026-08-11-dsid-363490-training.md`，只规定无人值守阶段的时间顺序和停止条件。所有物理条件、命令、固定 run 名和安全发布合同仍由原计划控制；每一步只在前一步产物通过 manifest/hash 审计后继续。

**Tech Stack:** Python 3.9、uproot、pandas、XGBoost、pytest、Matplotlib、YAML/JSON manifests。

## Global Constraints

- 不降低或动态调整 trigger、trigger matching、Tight ID、isolation、`d0/z0`、`pT/eta`、SFOS、`Z1/Z2` 或 `m4l` selection。
- `m4l` 只用于审计和绘图，不能进入 14 个训练特征。
- 不读取真实数据的 `120--130 GeV` 事件内容，不产生真实数据分数。
- 不加入未在配置声明的 `1.3` `gg->ZZ` 修正。
- 363490 仅来自 CERN Open Data record 15005；700600 只作冻结外部验证，不参与训练或阈值选择。
- 任何 run 目录只使用一次；失败目录不删除、不覆盖、不复用。
- viability gate 固定为：每个 development fold 和 independent test 至少 20 个 selected 363490 事件，否则训练前停止。
- 所有工作写入 task report、checkpoint、manifest 和 SDD ledger；不执行 Git stage/commit。

## 当前状态（2026-08-11 07:50 EDT）

- Downloads 与项目内 363490 ROOT 的 SHA-256 相同：`76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`。
- 官方 ROOT 已验证为 `mini` 树、554279 rows、全部 DSID 363490、19 个所需分支齐全。
- 完整预处理 PID 18044 已运行约 11 分钟；run 目录按 manifest-last 合同尚未发布，不能重跑或中断。

## 时间段 1：0--60 分钟 — 完成预处理与统计门禁

- [ ] 每不超过 60 秒确认 PID 18044 仍运行或已自然结束，不发送中断信号。
- [ ] 进程结束后要求 `runs/full-baseline-363490-2026-08-11` 有完整固定布局、manifest 最后发布且无 `failure.json`。
- [ ] 审计三个输入哈希、配置哈希、DSID、每级 cutflow、selected row counts、有限数值、权重和事件身份。
- [ ] 只用 MC 聚合计算 fold/test 的 363490 计数；每组必须 `>=20`。
- [ ] 若失败，保存失败产物并做只读根因诊断；只有代码缺陷经 TDD+独立复核修复后，才允许用一个明确的新 run 名执行一次。

## 时间段 2：60--150 分钟 — 完整 MC 训练与 125 GeV 峰

- [ ] viability gate 通过后，只执行一次 `scripts.train_full_mc`。
- [ ] 审计候选选择、final tree count、OOF/test AUC、working points、KS/mass-sculpting warnings、identity summary 和所有输出哈希。
- [ ] 只目视七张 MC 图；明确检查 Higgs `m4l` 是否在约 125 GeV 集中、ZZ 是否平滑。
- [ ] 不把 MC 峰描述为数据发现或显著性结论。

## 时间段 3：150--210 分钟 — 冻结 DSID 700600 外部验证

- [ ] 使用已冻结模型和 working points；训练、CV、fit、阈值重建接口必须零调用。
- [ ] 审计 700600 selected count、external AUC、loose/medium/tight 背景效率及不确定度、KS distances 和三张外部比较图。
- [ ] 比较训练 run 前后哈希，必须完全相同。
- [ ] 对三个完成命令各做一次同路径 refusal，确认在 ROOT/model/table loading 前拒绝且产物哈希不变。

## 时间段 4：210--240 分钟 — 文档、全套测试与最终交接

- [ ] 从真实 manifest/metrics/cutflow 复制数字，更新 README、AGENTS 和物理/roadmap 文档。
- [ ] 写并运行恰好一个 DSID 363490 docs test，禁止旧的“700600 是训练背景/471 是当前结果”表述。
- [ ] 运行 focused tests 和完整 pytest，记录准确 pass count。
- [ ] 完成 protected-state、14-feature/no-`m4l`、无真实数据评分、所有 manifests/hashes 的最终审计。
- [ ] 做一次全局独立 code/artifact review；有 load-bearing finding 时只进行一轮集中修复和 scoped re-review。
- [ ] 写中文物理交接：样本数、cutflow、AUC、working points、外部效率、125 GeV MC 峰、warnings 和剩余物理限制。

## 无人值守决策规则

- 数据或统计门禁不足：停止训练，报告具体 cut stage；不放宽 selection。
- 已批准命令失败：保留失败 run；先诊断，再经 TDD/复核修复；绝不复用同名目录。
- 网络或外部服务失败：不换非官方镜像，完成所有可离线审计并精确记录 blocker。
- 四小时到达但安全运行仍在自然执行：不强制终止；留下当前 PID、阶段、最后检查时间和下一步。
