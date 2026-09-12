# Sprint M4-01

## 1. Sprint 目标

交付 [FR-SE-04](../../1-Requirement/Done/FR-SE-04-learning-curve-batch-workflow.md)：新增隔离的学习曲线CLI与application workflow，完成确定性plan、full端点去重、M2/M3全链批处理、共同template grid、T1 model-self Asimov和完整ledger。

## 2. 前置依赖

- M3 commit `8bd4cb1`。
- [M3 code-review-confirm](../../4-Reviews/sprint-m3-01-code-review-confirm.md) 与 [artifact schema §9](../../sw-dev/artifact-schema.md#9-子集绑定判别器与实验血缘)。
- 已验证ResearchProtocol、SampleEfficiencyProtocol、prepared、compact freeze、已发布training-subsets、旧templates gate与其receipt-bound T1 evidence。

## 3. 纳入范围

纳入 `src/research/sample_efficiency_workflow.py`、`src/cli/sample_efficiency.py`、`scripts/h4l_learning_curve.py`、批次schema/readers、focused tests和相关文档。

## 4. 暂不纳入范围

M5统计报告、M6 capacity/CDF/confirmation、M7正式数据与authority验证不纳入；原因是M4只冻结批次执行和完整性artifact，避免统计解释或确认访问反向改变实验计划。

## 5. 工作范围

### 5.1 计划、CLI与安全路径

- [x] 定义严格batch配置、plan/common-grid/stage envelope/ledger/summary schema，分离scientific与execution identity。
- [x] 实现计划生成：M2 alias、full去重、固定排序、三表示×network seed、stage路径和资源摘要。
- [x] 实现薄CLI/独立脚本；公开`python -m`和脚本入口，显式dataset/base protocol，plan-only只重验已发布M2并保持零写入。
- [x] 实现clean proof：与plan-only/执行互斥，只删除ownership marker+空staging的未启动占位，逐组件拒绝reparse/symlink及任何run/failure/未知内容。

测试：参数面、plan计数/顺序/identity、full去重、零写入、越界/链接/占用目录/危险clean、旧`h4l_run.py` characterization。

### 5.2 批处理与artifact链

- [x] 重验M2 subsets与旧gate/T1 snapshot，发布sealed plan；按plan调用M3 model publisher并保留每个cell终态。
- [x] 发布raw calibration run，从全部成功cell的verified template frame一次构建并发布有完整participant upstream的共同grid run。
- [x] 在共同grid发布template与T1 model-self Asimov inference run。
- [x] 发布外层batch ledger/summary，reader重验全部receipt、upstream、lineage、metric pointer、状态机、计数和complete gate。
- [x] M4只允许workers=1和parent publication；拒绝workers>1，执行资源不进入科学identity。

测试：缩小synthetic E2E、共同grid participant/ID唯一、T1固定μ=1/68% pointer、直接upstream、失败/blocked stage不丢失、未知/重复/缺失cell、receipt/lineage/path重签攻击、assessment decode sentinel。

## 6. 验收标准

- synthetic缩小协议覆盖三表示、多fraction/draw/network seed并证明full端点去重。
- 全部planned cell均有唯一ledger终态，成功链共享一个grid ID且直接upstream可重验。
- plan-only零写入，clean只触及被当前batch ID证明的未发布目标；旧发现脚本行为不变。
- assessment/held-out test不被读取，Windows结果不升级为authority或科学验证。

## 7. 验证要求

- `conda run -n pytorch python -m pytest -q tests/research/test_sample_efficiency_workflow.py tests/research/test_h4l_learning_curve_script.py tests/research/test_sample_efficiency_training.py tests/research/test_sample_efficiency_lineage.py tests/research/test_training_subsets.py tests/research/test_templates.py tests/research/test_inference.py`
- `conda run -n pytorch python -m pip check`
- `conda run -n pytorch python -m pytest -q`

Windows synthetic只证明软件路径，不替代ARM64 authority、完整ROOT或科学数值验证。

## 8. 实施顺序

1. 文档双评审、review-confirm并应用接受项。
2. 先写focused tests，再实现plan/reader、workflow和CLI。
3. 代码双评审、code-review-confirm并修复接受项。
4. focused、pip check、全量pytest；归档FR/Sprint并仅提交M4文件。

## 9. 风险控制

- batch plan拥有全部科学坐标，CLI和批次配置不能覆盖fraction/seed/representation/architecture；路径/resources只进入execution plan ID。
- manifest-last、路径 containment、symlink与complete run拒绝共同保护clean和publication。
- 旧workflow不接入新参数；具名cell terminal保留，binding或未知错误停止批次。
- M4强制workers=1；父进程按canonical plan顺序发布，多worker留给后续平台验证。

## 10. 交付结论

FR/Sprint文档与代码均完成双评审和逐项确认；接受项落实；验证通过；FR/Sprint归档；提交消息固定为`feat: complete sprint-m4-01 code and change base on reviews`。

当前阶段：completed。文档与代码双评审、逐项确认和接受项均已完成；focused 45 passed/68 warnings，pip check通过，全量680 passed/122 warnings。Windows synthetic未升级为ARM64 authority、完整ROOT或科学数值验证。
