# Sprint M3-01

## 1. Sprint 目标

交付 [FR-SE-03](../../1-Requirement/Done/FR-SE-03-subset-bound-discriminant-v2.md)，让研究训练器严格消费 M2 子集，发布可向 raw 校准、模板与 model-self 推断传播的 `research-discriminant-v2` 实验/配对血缘，同时保持 v1 行为。

核心目标：

- 建立已验证 subset selection 到训练 frame 的关闭绑定。
- 建立 v2 model schema 与跨下游的稳定 experiment/pairing identity。

## 2. 前置依赖

- M1 commit `7f21ad4`；M2 commit `881b4f4`。
- `h4l-training-subset-plan-v1`、membership/ledger reader、现有 `train_discriminant()`/`predict_discriminant()`。
- [M2 code-review-confirm](../../4-Reviews/sprint-m2-01-code-review-confirm.md) 与 [artifact schema §8](../../sw-dev/artifact-schema.md#8-训练子集计划)。

协同说明：

- M3 只提供单模型训练和血缘原语；M4 才负责编排完整 learning-curve 批次。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-SE-03` 子集绑定判别器 v2 与实验血缘。

涉及包和目录：

- `src/research/training_subsets.py`
- `src/research/discriminants.py`
- `src/research/calibration.py`、`templates.py`、`inference.py`
- `tests/research/test_training_subsets.py`、`test_discriminants.py`、新增 M3 focused tests
- `docs/sw-dev/artifact-schema.md` 与本 Sprint 评审记录

## 4. 暂不纳入范围

- learning-curve CLI/batch、统计聚合、capacity/CDF、assessment confirmation、正式 ROOT/ARM64。

原因：

- 分别由 M4—M7 处理；M3 先冻结单单元接口和血缘，避免编排反向定义模型 schema。

## 5. 工作范围

### 5.1 工作包：Subset selection 与训练过滤

目标：

- 只能从完整重算通过的 M2 artifact 取得不可变 selection，并将其精确应用于 train。

实现任务清单：

- [x] 新增 `TrainingSubset` 与 `load_training_subset()`，校验partial/full alias、planned状态、freeze descriptor和全部binding。
- [x] 新增非CLI v2 publisher/reader service，从verified prepared run内部加载完整frame；过滤train后用共享算法重算membership/summary，保持validation完整。
- [x] 在 subset train 上重新拟合所有 train-derived 统计；绑定错误绝不回退。

测试要求：

- [x] 覆盖三表示共享 membership、train 精确过滤、validation 不变、full 规范化、低统计拒绝。
- [x] 覆盖prepared feature/source-row/validation字节篡改、缺组、额外/非train组、摘要/协议/表示篡改和伪造selection。

### 5.2 工作包：Discriminant v2 与下游血缘

目标：

- 生成可重算、可配对、不会与其他 fraction/draw 冲突的模型和 downstream identity。

实现任务清单：

- [x] 发布 `research-discriminant-v2` 全字段，重算 experiment/pairing/model ID和参数量。
- [x] 更新 predictor 同时严格读取 v1/v2；旧调用继续生成原 v1 bytes。
- [x] 新增严格不可变lineage提取/复制/验证，接入raw calibration bundle、template entry和model-self inference result计算接口；明确直接上游来源。
- [x] v2 downstream key使用experiment cell；v1 key不变；non-raw/capacity/assessment在claim或payload访问前拒绝。
- [x] 更新 artifact schema。

测试要求：

- [x] v1 characterization、v2 roundtrip、不同维度/种子/子集 ID、三表示 pairing 和字段篡改。
- [x] 校准→模板→model-self result逐层复制血缘；跨模型/跨subset替换、重签payload仍拒绝；v2 assessment前置拒绝。

## 6. 验收标准

- 满足 FR-SE-03 全部验收点；M2 artifact 是部分 train membership 的唯一来源。
- 不读取 assessment，不修改历史发现语义，不把任何 identity/weight/mass 血缘字段加入 classifier inputs。
- 文档与代码双评审确认完成，接受项落实。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pip check`
- `conda run -n pytorch python -m pytest -q`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/research/test_training_subsets.py tests/research/test_discriminants.py tests/research/test_sample_efficiency_training.py tests/research/test_sample_efficiency_lineage.py tests/research/test_calibration.py tests/research/test_templates.py tests/research/test_inference.py`
- Windows synthetic 结果仅为软件验证，不能称为 ARM64 authority、完整 ROOT 或科学数值验证。

## 8. 实施顺序

1. 文档双评审与 review-confirm，应用接受/部分接受项。
2. 先写 M3 focused tests，再实现 subset loader、v2 model 和 downstream lineage。
3. 代码双评审与 code-review-confirm，修复接受项。
4. focused、pip check、全量 pytest；归档 FR/Sprint；只 stage M3 文件并独立提交。

## 9. 风险控制

- 保留 v1 默认参数和 payload 分支，使用 characterization 防止历史模型漂移。
- v2 selection 必须由 receipt/语义重算后的 M2 loader 构造；实际 frame 再重算一次。
- 使用正式 canonical 字段和 digest 传播血缘，不依赖目录名或自由 manifest context。
- 严格 MC-only；assessment/held-out test 不进入本 Sprint。

## 10. 交付结论

当前阶段：completed。双文档评审、review-confirm、实现、双代码评审和code-review-confirm均已完成。Windows synthetic 验证：focused 51 passed/7 warnings，`pip check`无破损依赖，全量673 passed/61 warnings。ARM64 authority、完整 ROOT 与科学数值验证未运行。提交消息固定为 `feat: complete sprint-m3-01 code and change base on reviews`。
