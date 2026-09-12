# FR-SE-03 子集绑定判别器 v2 与实验血缘

- `FR-ID`: `FR-SE-03`
- `标题`: 子集绑定判别器 v2 与实验血缘
- `所属阶段`: M3
- `开发顺序`: 3
- `优先级`: P0
- `前置依赖`: [FR-SE-01](FR-SE-01-sample-efficiency-contracts.md)、[FR-SE-02](FR-SE-02-deterministic-training-subsets.md)
- `涉及包`: `src.research.training_subsets`、`src.research.discriminants`、`src.research.calibration`、`src.research.templates`、`src.research.inference`、`tests/research`
- `是否属于原型阶段`: 是（synthetic 软件验证）
- `来源类型`: 新需求
- `原始 SRS 章节`: 样本效率开发计划 §7、§13、§16.3、§17 M3
- `相关 FR`: FR-SE-04 批处理、FR-SE-06 容量与 CDF 对照

## 目标

从经过 receipt 验证的 prepared run 和 M2 训练子集内部加载数据，发布 `research-discriminant-v2` model run；它保持完整 validation 和旧 v1 行为，并向 raw 校准、模板与 model-self 推断提供稳定、可验证的实验/配对血缘。

## 背景与问题

当前 `train_discriminant()` 总是使用完整 train 角色，model schema 为 `research-discriminant-v1`。普通 DataFrame 无法证明 feature 和完整 validation 来自其声称的 prepared artifact；自签 model dict 也没有 manifest upstream 信任链。M2 已发布 receipt、协议、总体、membership 和摘要均可重算的子集 artifact；M3 将其接入独立的可信单模型 service，供 M4 批处理调用。

## 影响范围

新增 M2 subset selection loader/不可变值对象；新增从 verified prepared run 内部加载、训练、发布和读取 v2 model run 的 application service；新增 v2 model/lineage validator；扩展 raw 校准、模板和 model-self 推断计算接口的绑定。旧 discovery workflow、v1 artifact、历史 candidate key、assessment claim 和 held-out test 均不改变。

## 需求描述

1. `load_training_subset(...)` 从路径重新 `read_run` 验证 `prepare`、`compact-freeze`、`training-subsets` 三个 run，调用 M2 reader重算plan/membership/ledger，并按 `(fraction, draw)` 选择唯一alias。partial要求协议内整数draw；full接受协议内任一draw alias，但规范为 `draw_or_full="full"`、`sample_draw_seed=None` 和float `1.0`。低统计绝不回退到full train。
2. loader 返回不可变 `TrainingSubset`。canonical payload包含M2 artifact/prepared/population/overlay/subset/membership身份、fraction/规范draw、有序成员组、逐类/总计摘要，以及freeze artifact ID/payload SHA和经M1 loader重建的 `representation_id/groups/ordered_inputs/input_dimension` descriptor。对象另持verified run路径；public consumer仍从路径重验，不能把对象类型当信任证明。
3. 保留 `train_discriminant(frame, ...)` 既有签名、默认值、v1 payload和model ID语义。v2不接受普通DataFrame，而由 `publish_subset_discriminant(output_dir, ..., prepared, freeze_run, subset_run, base, overlay, fraction, draw, representation_id, network_seed, architecture_variant="baseline-fixed64x64x32")` 从重新验证的prepared `events.jsonl`内部调用 `load_research_data()`，只取得完整可访问MC数据，再调用内部训练核心。M4调用此service；M3不改旧CLI/workflow ingress。
4. v2 service只接收 `representation_id`，自行推导训练参数：`decay7 -> candidate M2, groups=None`；`engineered19 -> candidate M3, groups=None`；冻结compact ID -> `candidate M3` 且groups精确等于freeze descriptor。`target_lambda=0`；M3只允许 `baseline-fixed64x64x32`。调用方不能覆盖candidate/groups/lambda；表示、inputs或dimension冲突失败。
5. prepared file receipt在任何payload读取前验证；loader验证source identities和population。membership只筛选 `role=train`；从同一verified frame保留全部validation行及原始顺序。实际成员组、source row身份、逐类/总计摘要必须与selection一致；成员组缺失、出现在非train role或有额外选中组均失败。validation完整性以同一prepared loader输出为唯一参照，不接收调用方裁剪/替换。
6. 抽取共享 `summarize_training_rows()`：按canonical `(event_group_id,event_id,source_row_id)` 顺序将Python finite float逐行累加为组signed weight，再用M2同一summary算法生成逐类/总计；以canonical JSON bytes精确比较。scaler、optimizer类均值、质量分箱、工作点和fitting rows仅来自subset；早停/AUC/诊断使用完整validation。
7. v2 publisher使用 `research-run-v1` stage `sample-efficiency-train`，manifest upstream集合精确为重新验证的 `prepare`、`compact-freeze`、`training-subsets` artifact，文件至少为base `protocol.json`、`sample-efficiency-protocol.json`、`model.json`。`read_subset_discriminant_run()`重验model run和三上游路径、每个receipt、overlay snapshot、M2 selection和model语义；返回可信model及lineage对象。不得仅凭自签model dict声称run provenance。
8. `research-discriminant-v2` 根键为当前v1必填键、按base protocol条件出现的 `history_contract`，再加：`base_research_protocol_sha256`、`sample_efficiency_protocol_sha256`、`training_subset_artifact_id`、`training_subset_id`、`membership_digest`、`prepared_artifact_id`、`population_id`、`sample_fraction_target`、`sample_draw_seed`、`sample_draw_seed_or_full`、`full_endpoint_canonicalized`、`network_seed`、`representation_id`、`architecture_variant`、`trainable_parameter_count`、`training_summary_by_label`、`training_summary_total`、`train_fitted_statistics_source`、`experiment_cell_id`、`pairing_id`。禁止未知/缺失键及非有限JSON数值。
9. v2交叉不变量：`seed==network_seed`；baseline architecture为 `[d,64,64,32,1]`，参数量以实际 `sum(parameter.numel())` 重算；`train_fitted_statistics_source==training_subset_id`；representation/candidate/groups/inputs精确映射；full要求fraction `1.0`、draw `None`/`"full"`/flag true，partial要求float `<1.0`、整数draw/同值draw-or-full/flag false；summary精确等于selection。
10. v2 ID：`experiment_cell_id = SHA256(canonical([overlay_digest, training_subset_artifact_id, subset_id, representation_id, fraction, draw_or_full, network_seed, "raw", architecture_variant]))`；`pairing_id`用同一数组去掉representation。三表示共享pairing ID。`model_id`绑定除自身外完整payload。reader面对重签model仍重算所有语义字段。
11. `predict_discriminant()` 按schema分派：v1保持当前历史兼容（包括有/无 `history_contract`），v2先严格validate。v1没有部分样本身份，不能传给 `require_experiment_lineage()` 或进入完整配对接口。
12. 新增不可变 `ExperimentLineage`，schema `h4l-experiment-lineage-v1`，精确键为 `schema_version,source_model_artifact_id,model_id,base_research_protocol_sha256,sample_efficiency_protocol_sha256,prepared_artifact_id,population_id,training_subset_artifact_id,training_subset_id,membership_digest,representation_id,sample_fraction_target,sample_draw_seed,sample_draw_seed_or_full,network_seed,architecture_variant,transform,experiment_cell_id,pairing_id`。M3仅允许 `transform="raw"`。对象只能由verified model-run reader构造。
13. raw calibration bundle、每个template entry、每个model-self inference外层result在固定 `experiment_lineage` 键复制canonical dict，并从直接上游可信对象逐字段等值验证。model/mapping/threshold/template/result内容digest覆盖该字段；M4 publisher再把直接上游run写入manifest。v2 downstream key使用 `experiment_cell_id`；v1历史key不变。
14. M3阶段矩阵固定为v2 raw calibration、普通template computation和 `expectation_kind="model_self_asimov"`。physical/absolute/CDF transform、capacity architecture、assessment/mismatch、旧claim/freeze confirmation均在创建claim或读取相应payload前以 `training_subset_binding_mismatch` 拒绝，留给M6。
15. 失败矩阵：M2 cell非 `planned` 时抛 `ResearchStateError(status="training_subset_insufficient_statistics")`、exit 0；缺失/重复alias、非协议fraction/draw、伪造selection、错误run/stage/upstream、表示/summary/v2/downstream错配均抛 `ResearchError(status="training_subset_binding_mismatch")`、exit 3。所有失败在训练RNG、下游计算或claim前。训练数值终态沿用 `insufficient_statistics`/`training_failed`。

## 高层要求

严格MC-only；不读取真实数据、held-out test或assessment payload。保持 `src.research` 隔离和固定训练日程，不把 `m4l`、identity、role、weight或血缘字段加入classifier features。旧artifact不改写，v1/v2显式分支读取；科学身份进入受digest和manifest upstream保护的正式字段。

## 输入

已验证的base/overlay、prepared/compact-freeze/M2 training-subsets run路径；冻结representation ID、fraction/draw、network seed和基线architecture variant。v2不接受调用方DataFrame。

## 输出

不可变 `TrainingSubset`；`sample-efficiency-train` run及严格 `research-discriminant-v2` model；不可变 `ExperimentLineage`；raw校准、模板、model-self推断计算payload中的正式lineage字段。

## 失败与降级

低统计subset保留在M2 ledger并以 `training_subset_insufficient_statistics` 科学终态停止。alias/成员/摘要/协议/总体/表示/run/downstream血缘错误为 `training_subset_binding_mismatch`。不得自动换draw、扩大fraction、改seed、放宽阈值或回退到v1/full。

## 不纳入范围

独立learning-curve CLI和batch ledger（M4）；统计聚合/绘图/Q*（M5）；capacity、CDF与独立确认（M6）；正式ROOT/ARM64运行（M7）。本Sprint不修改现有 `h4l_run.py`/`workflow.py` ingress，也不添加CLI参数。

## 最小验证方式

先运行 `pytest -q tests/research/test_training_subsets.py tests/research/test_discriminants.py tests/research/test_sample_efficiency_training.py tests/research/test_sample_efficiency_lineage.py tests/research/test_calibration.py tests/research/test_templates.py tests/research/test_inference.py`，再运行 `python -m pip check` 和全量 `python -m pytest -q`，均在 `neural` 目录和Conda `pytorch` 环境执行。

## 验收要点

- 同一M2 selection的三表示只改变表示字段，membership/pairing一致；不同fraction/draw/network的experiment ID不冲突，full规范化。
- v2数据只从verified prepared run内部加载；实际train组精确等于membership，完整validation来自同一run；train-fitted统计只来自subset。
- prepared feature/source-row/validation字节篡改、receipt自洽的selection/model字段重签、membership/摘要/overlay/upstream/role篡改与伪造对象均在训练/RNG前拒绝。
- v1既有fixture/model ID/predict保持；v2 roundtrip和重签语义篡改拒绝。
- raw calibration、template、model-self inference逐层验证lineage；v2 non-raw/assessment在claim/payload访问前拒绝。

## 备注

路径：FR_DIR=`docs/1-Requirement`、FR_DONE_DIR=`docs/1-Requirement/Done`、SPRINT_DIR=`docs/3-Plan`、SPRINT_DONE_DIR=`docs/3-Plan/Done`、REVIEW_DIR=`docs/4-Reviews`（均相对 `neural`）；验证命令来自 `neural/AGENTS.md`。当前阶段为 completed。Windows synthetic 验证结果：M3 focused 51 passed、`pip check`通过、全量673 passed/61 warnings；未执行 ARM64 authority、完整 ROOT 或科学数值验证。
