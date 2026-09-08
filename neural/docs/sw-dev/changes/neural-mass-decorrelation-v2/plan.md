---
change_id: neural-mass-decorrelation-v2
status: superseded
previous_status: awaiting_approval
superseded_by: ../../../research/H4l-Research-Project-Proposal-2026-09-08.md
source: 本次对话中经用户明确批准的后继优化 spec 草案
updated_at: 2026-09-08T19:22:08+08:00
---

# Atlas2020 质量去相关代码优化计划

> **已被新项目方案替代，仅供历史参考。**
>
> 根据用户于2026-09-08在本次对话中的明确指示，本计划不再作为独立开发任务或新项目的前置条件。当前研究与开发方向以[《H→ZZ*→4ℓ 中质量条件判别信息的可解释分解与稳健信号提取》项目方案](../../../research/H4l-Research-Project-Proposal-2026-09-08.md)为准。
>
> 以下原计划正文及审批记录保留，用于追溯历史决策；其中的 `awaiting_approval`、执行顺序和验收条件均描述当时状态，不表示本计划仍待实施。此替代标注不构成对新方案代码实施的批准。

## Summary

采用三阶段、预注册、遇到首个 eligible 即停止的优化路线：

1. 扩展 adversarial λ；
2. 用 soft-flatness 替换 adversary，保留 AUC-only checkpoint；
3. 保持 soft-flatness，改用 KS-aware checkpoint。

现有15项特征、AUC/KS/效率门槛、数据划分、权重、质量分箱及历史协议全部保持不变。禁止读取 held-out test，禁止后续追加候选或放宽门槛。

## Interface and Design Changes

- 新增 schema `4.0` 的三个独立协议：
  - Stage A：`λ={0,0.5,1,2,5,10}`。
  - Stage B/C：`μ={0,0.1,0.3,1,3,10}`。
- 协议以 `decorrelation.method`、`checkpoint.selection` 和结构化 `candidates` 表示科学行为；不再把 soft-flatness 强度称为 λ。
- 新增通用候选字段：`candidate_id`、`decorrelation_method`、`decorrelation_strength`。同协议内按最高 eligible OOF AUC选择；`1e-6` 内优先较小强度，再按候选 ID 排序。
- 新 artifact/model schema：
  - epoch 指标增加 validation AUC、三个 KS和效率。
  - Stage A 保存现有 adversarial MLP payload。
  - Stage B/C 保存 classifier-only payload。
  - test-opening 按 model schema 校验和加载，但本轮不执行 test。
- CLI 保持不变；全部科学选择只能来自 hash-bound protocol。旧协议和旧 artifact 继续原样读取，不做迁移。

## Implementation Work Packages

1. **固化生命周期文档**
   - 在允许写入且计划获批后，保存已批准 spec 和本计划到 `neural/docs/engineering/changes/neural-mass-decorrelation-v2/`。
   - 记录本轮用户批准来源、时间、Git 基线和既有失败 run；不得修改该 run。

2. **版本化协议和候选模型**
   - 在 `src/training/config.py` 增加 schema 4.0 严格解析、三种 protocol ID、结构化候选和旧 schema 适配。
   - 保留旧 `TARGET_LAMBDAS` 语义，仅供旧协议验证；新协议不得依赖全局候选常量。
   - 新增三个密封 YAML；任何字段、顺序、类型或候选漂移均 fail closed。

3. **实现 soft-flatness**
   - 背景 batch 内对 `q={0.5,0.2,0.1}` 从 detached logits 求加权高分分位阈值。
   - 固定 `temperature=0.5`，计算 `sigmoid((logit-t_q)/0.5)`。
   - 损失为有效质量 bin 上 `((e_bq-e_q)^2/(q*(1-q)))` 的平均值。
   - 零权重 bin 排除并计数；少于两个有效 bin 时返回 differentiable zero。
   - Stage B/C 使用 `L_cls + μ_effective·L_flat`，沿用5 epoch warm-up和10 epoch ramp；不初始化或保存 adversary。

4. **重构 trainer 与 checkpoint**
   - 为 Stage A 保留逐字节等价的现有 GRL/adversary 训练路径。
   - `ValidatedFold` 增加仅来自 development validation 的 `m4l` 和 metric weight；不得触及 test reader。
   - Stage A/B 继续按 validation AUC和现有 `1e-4` improvement 保存 checkpoint。
   - Stage C 按以下固定层级选择：
     1. 完整满足 validation eligibility 的 epoch 中选最高 AUC；
     2. 否则在 AUC和效率合格的 epoch 中选最大 KS 最小者；
     3. 否则回退最高 AUC。
   - 同层级相等时依次选择更高 AUC、更早 epoch；patience 仍为20，并由当前层级的有效改善重置。

5. **版本化发布和模型读取**
   - `development.py` 按通用 candidate 编排 OOF、qualification、tie-break、日志和 artifact。
   - 修正无 eligible 时质量雕刻图只显示最高 AUC候选的歧义：标题明确 candidate，且为全部候选分别发布诊断图或明确索引。
   - test-opening 严格分派旧 adversarial payload与新 classifier-only payload；未知 schema、额外字段、状态维度或哈希漂移全部在 test decode 前拒绝。

6. **按预注册门执行 development**
   - 运行 Stage A；出现 eligible 即停止。
   - Stage A 无 eligible 才运行 Stage B；出现 eligible 即停止。
   - Stage B 无 eligible 才运行 Stage C。
   - Stage C仍无 eligible 时发布 `no_eligible_candidate` 并终止本优化，不追加超参数、不改特征、不降低 KS。
   - 每阶段使用全新不可覆盖目录；不得打开 `test_events.csv.gz`。

## Test and Acceptance Plan

- 单元测试：
  - soft weighted quantile、三个工作点、手算 flatness、梯度方向、temperature、零权重和缺失 bin。
  - 三层 checkpoint 选择、tie-break、patience 和非有限输入。
  - schema 4.0 字段/类型/顺序/hash mutation；旧 schema exact compatibility。
- 集成测试：
  - 三协议各完成 deterministic synthetic 五折运行。
  - 相同 seed/protocol exact 重现；不同强度在 warm-up 阶段一致、ramp 后分离。
  - classifier-only checkpoint、manifest、OOF和 test-opening synthetic gate 完整绑定。
  - spy 证明 development 不读取 test，失败路径不发布模型。
- 回归验证：
  - `python -m pip check`
  - 相关测试模块后执行 `python -m pytest -q`
  - `git diff --check`
  - 旧协议 fixtures、历史模型读取和旧 test-opening 拒绝语义不得变化。
- 科学验收：
  - 仅完整 `atlas2020_4lep` development OOF 可判 eligible。
  - AUC≥0.80、三个 KS≤0.10、三项信号效率严格高于背景效率。
  - Windows结果只记录为 development 证据，不替代 locked native ARM64 authority。
  - eligible 不等于 test reproduced；test-opening 保持未运行。

## Risks and Assumptions

- 最高风险为 High：训练目标、checkpoint和 artifact/model schema发生版本化变化。
- 通过新 protocol/model ID隔离回滚；旧 run 无迁移、无覆盖。
- 特征消融明确排除，后续如需进行必须另立 spec。
- 不采用“只扩展 λ”作为最终唯一方案，因为当前 tight KS距门槛过远且 adversarial CE不直接约束高分尾部。
- 不采用 distance correlation，因为其批次平方复杂度更高且不直接对应三个工作点。
- 不调整 qualification 门槛、工作点、数据集配对或 test规则。

## Approval Record

- Spec：用户在本次对话的 Spec Gate 中明确选择“批准 spec”；该草案尚未单独保存为 `spec.md`。
- Plan：`awaiting_approval`。用户要求将计划输出为文档，未单独明确批准代码实施计划。
- 文档输出依据：用户请求“将此计划输出为一个文档”，随后要求“执行文件输出生成”。
- 本次输出仅保存上述计划，不执行代码实现、测试训练或 test-opening。
