# FR-SE-02 确定性训练子集 Artifact

- `FR-ID`: `FR-SE-02`
- `标题`: 确定性训练子集 Artifact
- `所属阶段`: M2
- `开发顺序`: 2
- `优先级`: P0
- `前置依赖`: [FR-SE-01](Done/FR-SE-01-sample-efficiency-contracts.md)
- `涉及包`: `src.research.training_subsets`、`src.research.artifacts`、`tests/research`
- `是否属于原型阶段`: 是（synthetic软件验证）
- `来源类型`: 新需求
- `原始 SRS 章节`: 样本效率开发计划 §6、§13、§16.2、§17 M2

## 目标

从已绑定 prepared research run 的 identity-first 事件记录生成事件组级、按label分层、确定性嵌套的训练子集，并发布可重算验证的 summary、membership和ledger。

## 背景与问题

模型内临时抽样不能证明三表示共享成员资格，也会混淆draw/network seed。M2将成员资格提升为一级artifact；M3才消费它训练模型。

## 影响范围

新增 `training_subsets.py` 及测试，复用 `ResearchRun`/`LoadedRun`。只读取 `events.jsonl` identity envelope，不解码payload，特别是不解码assessment。

## 需求描述

1. 输入必须是通过 `read_run` 和文件receipt验证的 `prepare` run、已验证base/overlay/freeze；prepared artifact/population与overlay精确绑定。
2. reader先通过LoadedRun验证整文件receipt，再第一遍严格验证header schema/dataset/base protocol digest、每行identity字段全集、canonical重编码、唯一source_row_id、dataset/role/label/group一致性并重算identity digest。第二遍仅对已确认role=train的行解码payload中的`physical_weight`和`m4l`；assessment、validation、calibration和template payload永不解码。
3. 对每个draw和label按 FR-SE-01 canonical JSON数组计算SHA-256，以 `(hash,event_group_id)` 排序；fraction<1取floor前缀，1.0取全部。组内所有来源行共同入选。
4. fraction之间嵌套；不同表示只引用相同subset_id/membership_digest。完整端点跨draw规范为`full`，membership只发布一次；ledger保留每个draw到相同full subset的引用。
5. membership JSONL首行为`{"schema_version":"h4l-training-subset-membership-v1"}`，随后记录精确键`draw_or_full,fraction,label,event_group_id`，按其canonical值排序。`membership_digest=SHA256(canonical(records))`；`subset_id=SHA256(canonical([overlay_digest,prepared_artifact_id,draw_or_full,fraction,membership_digest]))`。partial用整数draw，full用字符串`full`且仅一组记录。ledger为`h4l-training-subset-ledger-v1`，每个原始(draw,fraction)一行；full aliases共享subset_id/digest，alias_id绑定`[subset_id,original_draw,1.0]`。
6. summary schema为`h4l-training-subset-plan-v1`，绑定base/overlay/freeze/prepared/population/identity digest，包含每subset逐类与总计。每个event group的signed weight为其所有train行physical_weight之和；`sum_signed=sum(group_weight)`、`sum_abs=sum(abs(group_weight))`、`sumw2=sum(group_weight^2)`、`neff_abs=sum_abs^2/sumw2`，行数/组数与m4l min/max同时记录。m4l范围仅审计，不添加未注册阈值。
7. 每类group数小于min_groups或neff_abs低于min_effective_count、或sum_abs<=0时该subset记录`training_subset_insufficient_statistics`，不重抽；否则`planned`。非有限weight/mass、身份/重算不一致抛 `ResearchError(status="training_subset_binding_mismatch")`。run只要输入身份有效就以complete发布全部cell，即使全是低统计终态。
8. publisher必须接收已验证prepared run和`compact-freeze` run；验证freeze.json receipt并重建M1 freeze。manifest upstreams含两者，另发布`sample-efficiency-protocol.json` snapshot。reader逐文件验证receipt、两个upstream artifact ID、双协议/freeze绑定，并重算全部ID、摘要、嵌套性。

## 高层要求

MC-only；不读取held-out或assessment payload；旧run不可改；不为旧artifact补造身份。科学算法来自overlay，不接受运行时覆盖。

## 输入

prepared与compact-freeze `LoadedRun`、ResearchProtocol、SampleEfficiencyProtocol、全新输出目录。

## 输出

`training-subsets.json`、`training-subset-membership.jsonl`、`training-subset-ledger.json`和`research-run-v1` manifest。

## 失败与降级

预期低统计保留ledger终态；绑定、receipt或schema错误失败关闭；未知异常由上层映射70。不补抽、不插补。

## 不纳入范围

训练、模型v2、CLI/batch、统计报告和确认。

## 最小验证方式

`pytest -q tests/research/test_training_subsets.py`，随后pip check和全量pytest。

## 验收要点

确定性、行序不变、不同seed差异、嵌套、分层、组不拆分、full去重、assessment poison、receipt/摘要篡改和失败语义均有测试。

## 备注

路径沿用M1：FR_DIR=`docs/1-Requirement`、SPRINT_DIR=`docs/3-Plan`、REVIEW_DIR=`docs/4-Reviews`（均相对neural）；验证来自AGENTS.md。文档与代码双评审、逐项确认、接受项修复、focused/pip check/全量测试和独立提交门均已完成。验证仅为 Windows synthetic 软件证据，不代表 ARM64 authority、完整 ROOT 或科学数值验证。
