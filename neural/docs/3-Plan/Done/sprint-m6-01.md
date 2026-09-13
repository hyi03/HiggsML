# Sprint M6-01

## 1. 目标

交付 [FR-SE-06](../../1-Requirement/Done/FR-SE-06-controls-and-confirmation.md)：唯一容量变体、精简physical CDF机制检查，以及独立总体claim-before-decode非劣性确认。

## 2. 前置

- M5 commit `af05f65`；verified M4 batch与M5 report。
- 冻结SampleEfficiencyProtocol、compact freeze和base protocol。
- 本机无正式独立controlled-MC输入时，只运行synthetic software validation，正式结果标external pending。

## 3. 工作项

- [x] 实现capacity width registry、enabled坐标计划、受控模型/指标artifact和disabled零训练。
- [x] 实现注册点physical CDF mapping、接受率命中误差/质量形变、terminal与reader。
- [x] 实现confirmation identity-only scanner、独立总体检测、exclusive durable claim和repeat规则。
- [x] 实现严格evaluation input decoder、linear percentile CI、边界判定和confirmation artifact reader。
- [x] 实现controls/confirmation CLI与exact config，不暴露科学覆盖或候选选择参数。
- [x] 更新artifact schema §12及故障/外部pending说明。
- [x] capacity partial fraction遍历全部draw、full canonical去重；专用model/reader保持M3/M4/M5 reader隔离。
- [x] CDF只复用M4 final grid，按冻结公式重放absolute-weight category误差与mass-bin形变。
- [x] confirmation使用receipt-bound exclusion identity sets、同一文件handle、attempt先占位再durable claim的状态机。
- [x] synthetic只发布rule状态；controlled-MC缺受信package/ARM64证据时发布external_pending。

## 4. 测试

- width golden、半整数ties-lower、参数量、协议外坐标/宽度拒绝。
- disabled controls不调用模型/数据；enabled只遍历registered points且保持pairing。
- CDF mapping/acceptance/shape golden、支持失败与raw主report不可变。
- identity重复/错误role/已浏览population/lineage重合在decode sentinel前拒绝。
- claim文件在decode前可见并持久；同key显式repeat允许，不同freeze/config拒绝；claim root link拒绝。
- confirmation payload receipt/schema/digest/replicate/seed篡改拒绝；CI等号通过与大于不确认。
- synthetic端到端、focused、`pip check`、全量pytest。
- focused命令：`python -m pytest -q tests/research/test_sample_efficiency_controls.py tests/research/test_sample_efficiency_confirmation.py tests/research/test_sample_efficiency_controls_script.py`。
- 回归命令：`python -m pytest -q tests/research/test_sample_efficiency_protocol.py tests/research/test_training_subsets.py tests/research/test_sample_efficiency_training.py tests/research/test_sample_efficiency_workflow.py tests/research/test_sample_efficiency_report.py tests/research/test_artifacts.py tests/research/test_assessment.py`。
- 负例矩阵：capacity协议外坐标/进入baseline reader，CDF receipt重签/raw替换，identity partial overlap/subset/superset/BOM/CRLF/多delimiter/空类/超长行，同一路径替换与decode sentinel，claim冲突/并发/repeat漂移，以及claim后decode/fsync/rename fault。

## 5. 退出

完成文档双评审→review-confirm→实现→代码双评审→code-review-confirm→修复→验证→归档。仅提交M6文件，消息为`feat: complete sprint-m6-01 code and change base on reviews`。

## 6. 验证与交付记录

- 文档双评审与 `review-confirm` 已完成；代码双评审与 `code-review-confirm` 已完成，Accept/Partial 的 M6 内整改均已落实。
- M6 focused：`19 passed, 111 warnings`。
- M1—M5 回归：`105 passed, 180 warnings`。
- `python -m pip check`：`No broken requirements found.`
- 全量：`705 passed, 338 warnings`。
- `py_compile`、`git diff --check` 通过。
- Windows synthetic 仅证明软件契约、访问顺序与状态机；正式 independent controlled-MC producer/numerical replay、完整 ROOT 和 native ARM64 authority 仍为 M7 `external_pending`。

当前阶段：completed。FR/Sprint 归档，并以 `feat: complete sprint-m6-01 code and change base on reviews` 单独提交。
