# Sprint M5-01

## 1. Sprint 目标

交付 [FR-SE-05](../../1-Requirement/Done/FR-SE-05-paired-aggregation-reporting.md)：从 verified M4 batch 生成完整 cell记录、严格配对学习曲线、event-group评价bootstrap、分层误差、观测范围Q*与六类报告文件。

## 2. 前置依赖

- M4 commit `8ac1df1`。
- [M4 code-review-confirm](../../4-Reviews/sprint-m4-01-code-review-confirm.md) 与 [artifact schema §10](../../sw-dev/artifact-schema.md#10-学习曲线批次与共同网格)。
- 完整且可由 `read_learning_curve_batch()` 重验的 M4 batch。

## 3. 纳入与排除

纳入 `src/research/sample_efficiency.py`、报告CLI/脚本、report artifact reader/publisher、JSONL/JSON/CSV/PNG/Markdown、focused tests与`artifact-schema.md` §11。M6 capacity/CDF/confirmation和M7平台authority不纳入。

## 4. 工作项

- [x] 冻结 report contract、record/summary/curve exact schema与ID；每个 plan cell保留一行。
- [x] 从 verified model/inference pointers提取 W68/AUC/实际组数，严格重算 engineered19 配对差与比。
- [x] 实现版本化 validation event-group paired bootstrap、batch resample-plan ID和带权Mann–Whitney AUC，跨模型共享replicate multiplicity；聚合AUC误差逐replicate先汇总cell。
- [x] 聚合 failure rate、pair completeness、network/subset/evaluation/calibration/template误差层。
- [x] 实现只在观测相邻点包围/命中时生效的 Q* 单调线性规则。
- [x] 从已验证 summary rows生成 CSV/PNG/Markdown；实现 report publisher与全链 reader重放。
- [x] 增加薄CLI/脚本且不暴露科学参数；保持 assessment/held-out test关闭。

## 5. 重点测试

- 完整 synthetic M4 batch到六类M5输出及reader重放。
- cell顺序扰动、缺失/重复/terminal、receipt自洽指标/配对/聚合/CSV篡改均拒绝。
- 不同键不配对，缺baseline保留；full endpoint不伪造subset variance。
- bootstrap按组而非行、相同replicate跨模型配对、seed隔离、golden multiplicity/tie AUC/quantile、0/1有效replicate状态。
- Q*精确命中、相邻包围、多个区间取首个、重复actual count、不完整点与不达标无外推。
- M4输入替换/use-time payload替换、terminal无model的组数来源、PNG plot spec/Markdown重签漂移拒绝。
- CLI exact config/参数面、production runs root、fresh-child输出、旧M4/旧reporting兼容与assessment poison sentinel。

## 6. 验证与退出

先运行M5 focused tests，再运行`python -m pip check`和全量`python -m pytest -q`。文档/代码各经gpt-5.6-sol/high与gpt-5.5/high独立评审和逐项确认；接受项落实后归档FR/Sprint，并以`feat: complete sprint-m5-01 code and change base on reviews`单独提交。

Windows synthetic不构成ARM64 authority、完整ROOT或科学数值验证。

当前阶段：completed。文档与代码双评审及逐项确认已完成；focused报告3 passed/105 warnings、CLI 3 passed，pip check通过，全量686 passed/227 warnings。Windows synthetic未升级为ARM64 authority、完整ROOT或科学数值验证。
