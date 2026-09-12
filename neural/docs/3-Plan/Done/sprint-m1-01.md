# Sprint M1-01

## 1. Sprint 目标

交付 [FR-SE-01](../../1-Requirement/Done/FR-SE-01-sample-efficiency-contracts.md) 的软件契约与 characterization tests，启动 [总体计划](../../sw-dev/h4l-compact-kinematics-sample-efficiency-development-plan.md) M1。M1 正式科学预注册状态单独 pending；本 Sprint 完成不等于 M1 科学门或整体 M1—M7 完成。

## 2. 前置依赖

neural/AGENTS.md、研究课题、总体计划、现有 research protocol/representation registry、artifact-schema。图索引已存在但 protocol snippet 行号过时，必要代码读取回退到已定位文件。

## 3. 纳入范围

FR-SE-01；`src/research/sample_efficiency_protocol.py`、`config/research_sample_efficiency_protocol_v1.json`、新增 `tests/research/test_sample_efficiency_protocol.py` 和 `test_sample_efficiency_characterization.py`。更新 `docs/sw-dev/artifact-schema.md`、`docs/sw-dev/research-software-design.md`、`docs/README.md` 与总体计划状态链接；只登记M1两种纯payload的软件状态、摘要和信任边界，不宣称后续发布/权威验证完成。

## 4. 暂不纳入范围

M2—M7 runtime、正式候选/容差选择、真实/held-out/assessment 数据访问。正式科学参数没有获批值，不能进入编码默认值。此次提交只实现 M1 软件子范围。

## 5. 工作范围

### 5.1 严格协议与 freeze

- [x] 实现不可变 canonical wrapper、strict JSON loader 和所有层级 schema 检查。
- [x] 实现 compact freeze payload builder/validator；canonical groups、registry 输入顺序、digest、历史及总体排除集校验。
- [x] 实现 overlay 与 base/prepared/population/freeze 的显式交叉绑定。
- [x] 固定访问/配对/失败政策；显式校验 fractions、分离 seeds、容量和 CDF 点位、非劣性/评价重采样及 Q* 政策。
- [x] 模板含必填 null，不可作为正式协议加载；记录执行器尚未实现。

测试覆盖合法 synthetic 实例、防御性副本、canonical key order、每个层级遗漏/未知/重复字段、bool 伪数值、非有限、无序/重复、错配、候选篡改和缺冻结。

### 5.2 旧行为 characterization

- [x] 记录 v1/v2/v3 读写与 digest；未知旧协议字段继续拒绝。
- [x] 验证现有 train-only scaler/类权重拟合与完整 validation、模型输入和参数量公式；复用既有训练测试，新增缺口测试。
- [x] 固定现有 candidate key 和 h4l_run plan-only 的 90 train/100 calibration 计划与无执行行为。
- [x] 复用并运行已有 claim-before-decode/失败后禁止 redesign 测试，避免创建科学确认资源。

## 6. 验收标准

FR 验收点都有测试或明确引用既有测试；所有需要执行的规则都有版本 ID，未知算法拒绝。正式科学选择 pending 时仍无隐式默认。旧 runtime 源码与冻结 artifact 不变。

## 7. 验证要求

工作目录 neural/，环境 pytorch。系统 PATH 无 conda，查找其真实安装位置后以绝对路径运行等价命令。

1. `conda run -n pytorch python -m pytest -q tests/research/test_sample_efficiency_protocol.py tests/research/test_sample_efficiency_characterization.py tests/research/test_discriminants.py tests/research/test_workflow_guards.py tests/research/test_h4l_workflow_scripts.py tests/research/test_data.py`
2. `conda run -n pytorch python -m pip check`
3. `conda run -n pytorch python -m pytest -q`

命令来源 neural/AGENTS.md；只做 Windows synthetic 验证，ARM64 authority 和 scientific numerical validation 均未运行。

## 8. 实施顺序

FR/Sprint → 双模型独立文档评审 → review-confirm → 修订文档 → 契约测试/实现 → 双模型代码评审 → code-review-confirm → 接受项修复 → 专项/全量验证 → 仅 stage 相关文件并提交 `feat: complete sprint-m1-01 code and change base on reviews`。

## 9. 风险控制

纯模块不读事件和 run；receipt 信任验证留给后续 workflow，不把 payload 自摘要当作来源证明。正式预注册 pending 时不启动后续实验。原工作树干净；保持无关修改。所有评审输出在 REVIEW_DIR。采用当前任务内两个独立原生子代理（gpt-5.6-sol/high、gpt-5.5/high），遵循平台禁止为子任务创建用户侧任务的要求。

## 10. 交付结论

当前阶段：completed-software-scope。双文档评审与 [文档确认](../../4-Reviews/sprint-m1-01-review-confirm.md) 已完成，接受项已落实为FR精确schema表与绑定规则。双代码评审及 [代码确认](../../4-Reviews/sprint-m1-01-code-review-confirm.md) 也已完成；唯一接受的代码修正（freeze manifest ID 不得被 payload digest 替代）已添加检查和回归测试。修正后的专项/全量验证通过，FR/Sprint归档到各自Done目录。本记录随 `feat: complete sprint-m1-01 code and change base on reviews` 提交；确切提交ID以包含本文的Git记录为准，避免自引用摘要。M2—M7 未启动；M1 科学预注册仍待实际候选、绑定、容差来源和预算证据。

验证记录（Windows/pytorch，实际Conda入口 `D:/apps/anaconda3/Scripts/conda.exe`）：

| 检查 | 结果 |
|---|---|
| 编辑前旧 discriminants/workflow guards/h4l scripts | 54 passed，68.98s |
| 新契约测试初始红灯 | 新模块不存在，ModuleNotFoundError，随后实现 |
| 新契约及 characterization | 73 passed，10.14s |
| §7 专项含旧协议回归 | 156 passed，55.78s |
| 代码评审修复后 §7 专项 | 157 passed，51.37s |
| pip check | No broken requirements found |
| 首轮全量 pytest | 644 passed，60 warnings，332.23s；警告来自既有 pytest 收集与 pyhf/jsonschema 弃用 |
| 修复后最终全量 pytest | 645 passed，60 warnings，316.08s；警告类型与首轮相同 |
| 归档后文档路径与 diff | 39个本地文档链接存在；git diff --check通过 |

复用守卫测试为 `test_h4l_workflow_scripts.py::test_run_plan_covers_all_combinations_without_creating_run`、`test_workflow_guards.py::test_claim_precedes_payload_decode_and_failed_opening_blocks_training` 和 `test_durable_claim_refuses_redesign_and_requires_explicit_same_freeze_repeat`；旧协议矩阵另运行 `test_data.py`。当前来源仅 synthetic，没有打开实际研究/held-out/assessment 数据。工作期间出现的根 AGENTS.md 外部修改须保留并排除提交。

代码评审恢复记录：gpt-5.5 报告首次生成；gpt-5.6-sol 首次代码评审超过10分钟仍无报告，已中断并以相同模型/high发起唯一一次重试，重试成功且作者已修正文案乱码。两个报告均核验为本次非空文件，之后才执行 code-review-confirm 和代码修正。

评审报告保留评审时的活动路径及行号；FR/Sprint在通过全部软件门后移至Done，评审文件仍在REVIEW_DIR。无未处理的接受项。Repository ARM64 authority 与 scientific numerical validation 均未运行；无正式ROOT实验或确认状态发布。
