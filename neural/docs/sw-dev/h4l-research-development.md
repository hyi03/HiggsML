# H4l 研究开发与验证记录

日期：2026-09-08。来源：[项目方案](../research/H4l-Research-Project.md)。用户本轮已批准开发。
代码基线 `d5b86f7`，当前 `neural` 分支。创建独立工作树因沙箱禁止写 Git ref 而失败，按回退规则在当前目录实施；
未提交或推送。项目方案原有科学草案状态不被改写成已取得科研成果。

## 开发覆盖

| 工作包 | 交付 | 科学边界 |
|---|---|---|
| P0/P1 | 受控输入审计、逐轻子导出、角色隔离、采样校正、G0 | 实际源物理定义/历史反馈审计尚需外部证据 |
| P2/P3 | 1/8/10/20维模型、固定200轮对抗及配对 λ=0、物理/绝对权重CDF、阈值 | 合成数值验证不代表MC性能 |
| MELA | 输入输出、adapter摘要、固定官方源码API适配器、规范decay7坐标、独立参考校验、Linux/WSL运行器 | 实际后端构建与物理参考尚待提供 |
| P4 | 共同质量网格、分组signed模板、T0/T1、G1、Asimov/toys、配对、T2、压力工具 | T1实际MC近似与覆盖适用性未验证 |
| P5/归因 | 完整候选状态报告、五种子主比较、覆盖误差、逐种子精确Shapley及交互 | 未执行主比较或论文实验 |
| 工程 | 十个阶段入口、不可覆盖事务、协议/上游摘要、冻结assessment、文档与测试 | ARM64权威验收单列not_run |

后续 R1–R4 的完整消融、DisCo/树/四动量训练、学习曲线、新模拟批次、物理系统变化与论文实验，
按方案在先导后独立预注册。当前交付包含表示子集、归因、配对重采样和报告所需的基础能力，
没有把这些未运行实验标成完成。

## 验证记录

开发前旧流程基线：Windows/AMD64，390 passed、4 skipped，204.26秒。
新增研究局部验证：覆盖角色payload毒化、逐事件ROOT读取边界、模型完整200轮/确定性、CDF约束解析解、
模板协方差、pyhf单箱解析区间与辅助观测、配对伪实验、Shapley恒等式、产物篡改及不可覆盖。
合成四轻子从重建、角色划分、M0c/M2/M3、CDF到共同模板、T0推断及报告链路已运行；
无T1证据时，G1、候选扩展及assessment冻结保持阻断。

交叉评审发现并要求回归覆盖：角色哈希须先于payload解码、有限MC空箱不冒充结构零、
T2 bootstrap保留draw multiplicity、ME实际adapter摘要绑定、G1校验实际协方差、
候选失败状态进入报告、M6强度限定、assessment后防止同协议回调、共同事件配对。
最终独立评审提出的三个问题已修复并完成限定复核：冻结后补充 ME assessment 分数且保留冻结身份、
内部异常保留可报告 manifest 与退出码70、压力测试共同参考在 assessment 前绑定为 `M3:42`。
复核运行3项回归并单独验证 CLI 异常退出码；该复核未发现范围内剩余软件阻断。

最终 Windows/AMD64 验证使用 `C:/Users/whchen/anaconda3/envs/pytorch/python.exe`：

| 检查 | 结果 |
|---|---|
| 研究全集（pyhf 0.7.6） | 94 passed，63条依赖弃用警告，77.90秒 |
| 完整 neural 回归 | 484 passed、4 skipped，64条警告，234.08秒 |
| 基础环境不安装可选 pyhf | 83 passed、11 skipped，23.12秒；skip仅涉及pyhf数值流程 |
| `pip check` | No broken requirements found |
| wheel 构建 | `higgsml_neural-0.2.0-py3-none-any.whl` 成功 |
| wheel 内容核验 | 17个研究源码/协议文件与当前文件逐字节一致；入口存在 |
| 独立限定复核 | 三项问题关闭；3 passed；CLI_EXIT70 |
| 改动检查 | `git diff --check`通过；新增文本文件无行尾空白；3份新文档本地链接有效 |

pyhf 及其新增依赖仅安装在忽略的 `runs/research-deps`，通过 `PYTHONPATH` 用于验证。
数值测试缺少可选依赖时明确 skip，身份、协议与失败守卫仍运行。
原有 `TestOpeningResult` pytest 收集警告与 pyhf 的 `jsonschema.RefResolver` 弃用警告不等于测试失败。
旧流程4项跳过均因当前 Windows 不允许创建符号链接；不是已通过的符号链接安全验证。
本地证据保存在 `runs/h4l-development-notes/` 的 `final-focused.xml`、`final-full.xml`、
`final-full-rerun.xml`、`base-research.xml`、`final-review.md` 和 `final-rereview.md`；这些运行产物不提交。
首轮全套回归为483 passed、4 skipped、1 failed：原包契约测试仅允许三个旧入口。
已将新研究入口纳入精确契约，局部3项通过；没有放宽旧入口或删除断言。

## 明确未运行

- 未下载或读取真实数据；未打开历史held-out test特征。
- 未运行真实MC训练/先导、未重写冻结或失败run。
- 未执行原生osx-arm64权威验收或bound full-data golden。
- 未声明MELA物理验证、signed-MC T1近似验证、外部稳健性验证或论文结果。

## 实施选择

默认数值门槛、共同合箱/CDF算法与T2预算保存为独立软件协议，供合成验证和审阅。
进入真实assessment前需冻结适用于该MC来源的证据与协议；若默认选择不适用，必须创建新协议并重新验证，
不能根据旧assessment结果调整后仍沿用独立验证声明。
研究新模型允许显式m4l，旧15维模型、资格条件、历史协议与test-opening保持原有语义。
