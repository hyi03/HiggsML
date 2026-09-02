# Sprint M1-03 Document Review

**Reviewer:** opencode-go/kimi-k2.7-code
**Review Date:** 2026-09-02
**Review Type:** Document review

## Reviewed Inputs

- `docs/3-Plan/sprint-m1-03.md`
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `config/xgboost_protocol_v1.yaml`
- `docs/3-Plan/sprint-m1-02.md`
- `docs/4-Reviews/sprint-m1-02-review-confirm.md`
- `docs/4-Reviews/sprint-m1-02-code-review-confirm.md`
- `AGENTS.md`

## Overall Conclusion

`sprint-m1-03.md` 正确识别了 M1-03 的核心边界：只消费 development 数据、实现
`higgsml-xgboost develop`、五折 OOF、冻结工作点、资格门控以及 eligible-only 最终模型
发布。计划与 FR-001、批准设计和 `config/xgboost_protocol_v1.yaml` 在高层一致，且正确将
held-out test-opening 与历史代码删除排除在 M1-03 之外。

但计划对若干关键科学/工程边界的描述仍显笼统，可能在实施时被不同实现者以不同方式解释。
主要缺口集中在：KS 与工作点的计算对象、AUC/权重定义、CLI 禁止覆盖项、上游 manifest 绑定
细节、development run 产物布局、以及测试验证方式。建议在下表问题修正后再进入实施。

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Correctness | §5.2 "迁移 weighted AUC、KS 和效率计算" | 未说明 KS 是在 OOF ZZ 的 `m4l` 分布上计算。 | 设计 §9 明确要求"loose、medium、tight 三个 OOF ZZ `m4l` KS 均不高于 `0.10`"；FR-001 R5 规定背景 KS 门槛。 | 在 §5.2 中明确：KS 使用 development OOF 中 ZZ 样本的 `m4l` 分布与对应 OOF score 阈值计算。 |
| High | Requirement | §5.2 / §5.3 | 未明确工作点只能由 development OOF ZZ 的绝对物理权重确定。 | 设计 §8.2："工作点继续只由 development OOF ZZ 的绝对物理权重确定"；FR-001 R5 禁止用 signal 或 test 数据选择阈值。 | 在 §5.2 增加条款：工作点仅依据 OOF ZZ score 和 `abs(physical_weight)` 计算，不得使用 signal efficiency 反推阈值，也不得消费 test 数据。 |
| High | Requirement | §5.3 / §7 | 未要求 develop CLI 拒绝 `--overwrite`、特征覆盖、XGBoost 参数覆盖等科学参数覆盖。 | 设计 §6.4 明确列出"不提供 `--overwrite`""不提供特征开关""不提供 XGBoost 参数、候选网格、seed、fold 或工作点覆盖"；FR-001 R3 要求普通 CLI 不得覆盖科学参数。 | 在 §5.3 增加实现任务：develop CLI parser 只允许 `--input-run`、`--protocol`、`--run-dir` 等管理参数；并增加专项测试验证非法覆盖被拒绝。 |
| Medium | Correctness | §5.1 "class-balanced abs weight" | 未精确定义"class-balanced"是按 Higgs / ZZ 类别分别归一化。 | AGENTS.md："XGBoost 的 `train_weight` 使用归一化的 `abs(physical_weight)`"；设计 §8.2："XGBoost 使用按类别归一化的 `abs(physical_weight)`"。 | 在 §5.1 明确：`train_weight = abs(physical_weight)`，并在 Higgs 类与 ZZ 类内分别归一化到各自权重和。 |
| Medium | Consistency | §7 专项验证 | 使用 `-k "training or develop or qualification"` 过滤测试。 | M1-02 评审确认（GLM M-4）已指出 `-k` 依赖未来测试命名、可能静默漏测；M1-02 §7 因此改为显式文件列表。 | 将专项验证改为显式测试文件路径列表；在文件创建后更新为实际路径，不再以 `-k` 作为唯一门。 |
| Medium | Requirement | §5.3 "连接上游 manifest/hash 绑定" | 未具体说明要绑定 M1-02 preprocess run 的哪些字段。 | FR-001 R7 要求 manifest 绑定 protocol、配置、代码、软件、输入、输出、schema、计数和哈希；设计 §10.1 显示 development run 消费 preprocess run。 | 明确 development manifest 必须记录：上游 preprocess run 路径、preprocess manifest SHA-256、`development.csv.gz` 的 compressed/canonical 双重哈希、以及上游 protocol/run-config 身份。 |
| Medium | Correctness | §5.1 "迁移稳定五折" | 未说明 fold 分配的确定性依据与分层策略。 | 设计 §8.2 要求保持"当前 development fold 分配"；FR-001 R5 要求 OOF 预测完整、有限且每个 development 事件恰好出现一次。 | 在 §5.1 增加：fold 按 canonical identity 确定性分配，并在 Higgs/ZZ 间分层，确保五折互斥、并集覆盖全部 development 行。 |
| Medium | Requirement | §6 验收标准 | "不合格 run 无 `model/`" 未同时禁止 `state/test_opening.json` 与部分 model 产物。 | 设计 §10.1：`model/` 仅在 eligible 时出现，`state/test_opening.json` 由 `open-test` claim 创建；FR-001 R5 要求不合格时不得开启 test。 | 补充：不合格 run 不得创建 `model/` 目录、`model/model.json` 或 `state/test_opening.json`。 |
| Medium | Documentation | §5.3 / §6 | 未枚举 development run 的产物布局。 | 设计 §10.1 列出 `config.yaml`、`artifacts/`、`predictions/oof_scores.csv.gz`、`model/`（eligible）、`plots/`、`state/test_opening.json`。 | 在 §5.3 或 §6 中完整复现设计 §10.1 的 development run layout，并明确每个文件的生成条件。 |
| Medium | Test | §5.3 / §7 | "证明 test artifact 未读取" 缺少具体验证方法。 | FR-001 R5 与设计 §9 均要求 development 不读取 held-out test；§9 已提到 spy/deny fixture。 | 在 §5.3 测试要求中增加：使用文件访问 spy/deny fixture，将 test CSV.GZ 路径暴露给 develop 调用并断言无任何 open/read 行为；或验证 develop 只打开 `development.csv.gz`。 |
| Medium | Correctness | §5.2 "迁移 weighted AUC" | 未说明 weighted AUC 使用的权重是 `physical_weight` 而非 `train_weight`。 | FR-001 R5 要求"weighted development OOF AUC"；设计 §9 的资格指标使用物理权重。 | 明确 OOF AUC 按 `physical_weight` 加权计算，与 `train_weight` 仅用于 XGBoost fit 区分。 |
| Medium | Correctness | §5.2 "实现 eligible/no_eligible_candidate 决策" | 未明确效率比较是在每个工作点上 signal efficiency 严格高于 background efficiency。 | 设计 §9："每个工作点的 signal efficiency 严格高于 achieved background efficiency"。 | 在 §5.2 增加：在每个工作点阈值上分别计算 OOF signal efficiency 与 background efficiency，并断言 signal eff > background eff。 |
| Low | Clarity | §4 "暂不纳入范围" | "Held-out test-opening 与历史代码删除" 混为同一项。 | 设计阶段映射：test-opening 为阶段 5（M1-04），历史代码删除为阶段 6（M1-05/M1-06）。 | 拆分为两条："Held-out test-opening（M1-04）" 与 "历史代码删除（M1-05/M1-06）"。 |
| Low | Clarity | §6 验收标准 | `manifest 明确 test_opened: false` 未说明是 development-run manifest 字段。 | M1-02 代码评审确认（No.7）已从 preprocessing manifest 删除 `test_opened`，避免混淆生命周期语义。 | 增加注释：此处的 `test_opened` 属于 development run 的 manifest/state，表示尚未被 `open-test` claim。 |
| Low | Documentation | §10 交付结论 | 交付结论为空，未预填证据小节。 | M1-02 §10 预填了文档评审、代码评审、环境/验证、artifact 与提交证据小节。 | 参照 M1-02 预填 §10 的文档评审、代码评审、验证/环境、artifact、提交证据等子节。 |
| Info | Traceability | §2 / §5.3 | 可更明确引用已提交的 M1-02 preprocess 合同。 | M1-02 评审确认固定了 development/test schema、canonical hash、manifest 绑定等合同。 | 在 §2 或 §5.3 增加引用：`docs/4-Reviews/sprint-m1-02-review-confirm.md` 与 `docs/4-Reviews/sprint-m1-02-code-review-confirm.md` 为上游消费合同。 |
| Info | Risk | §9 风险控制 | 未显式声明不修改/复用冻结 Full14 run。 | AGENTS.md "当前冻结状态" 规定 Full14 已封存，不得继续调参、复用或打开 held-out test；下一阶段为原生去相关训练。 | 在 §9 增加：M1-03 仅迁移 Angular19 V1 行为，不修改、复用或读取冻结 Full14 run，也不提前实现去相关训练。 |
| Info | Requirement | §5.3 / §6 | 未说明最终模型序列化格式。 | 设计 §10.1 显示 development run 的模型为 `model/model.json`。 | 在 §5.3 增加：eligible 时以 XGBoost JSON 格式保存最终模型到 `model/model.json`。 |
| Info | Test | §5.1 测试要求 | 未引用训练行为 golden authority 来源。 | 设计 §7.2 列出 V1 训练迁移权威：`scripts/higgsml.py`、`src/experiment_config.py`、`src/experiment_runner.py`、`config/experiment_training.yaml`、`ANGULAR19_PROFILE`、`src/angular5.py`。 | 在 §5.1 测试要求中引用上述 authority，并说明 golden 对比在迁移前锁定当前行为。 |

## Needs Immediate Action

- 修正 High 项：明确 KS 计算对象、工作点 authority、CLI 科学参数禁止覆盖。
- 修正 Medium 项：精确化权重定义、fold 分配策略、上游 manifest 绑定字段、development run layout、
  test 文件未读取验证方法、AUC 权重、效率比较规则。
- 修正 Low/Info 项：拆分 out-of-scope、澄清 `test_opened` 语义、预填 §10 证据小节、引用 M1-02 合同、
  声明冻结 Full14 边界。

## Can Be Deferred

- `open-test` 的完整实现属于 M1-04；M1-03 只需为 `open-test` 准备可验证的绑定 artifact。
- 权威 345060/363490 ROOT 的大规模训练等价验证只能在具备授权输入的环境执行；M1-03 仍可用微型 fixture
  完成行为迁移与资格门控逻辑验证，并明确记录未执行边界。
- 历史执行面物理删除由 M1-05/M1-06 完成；M1-03 可用 import/CLI 边界保证新 training 层不依赖旧代码。

## Final Status

文档在应用上表 Accept 项修正后可接受，可自动进入 Sprint M1-03 实施，无需再次人工确认。
