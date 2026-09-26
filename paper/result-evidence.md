# 论文结果证据索引

核对日期：2026-09-26。正式 LaTeX 稿采用 test05 的已发布报告；
[selected-snapshot.json](selected-snapshot.json) 固定结果快照、来源清单和报告身份。
依据为实际运行产物、绑定协议和执行代码，不将旧 docs 的陈述当作结果证据。
`paper/evidence/` 为本地 Git 忽略目录，可保留额外来源清单和历史核验记录；论文默认构建不读取该目录。

## 当前版本与绑定

报告路径：`runs/h4l-off-test05/evaluation/report`。报告、Asimov、freeze、prepared 及训练
产物均记录执行提交 `c5cdfa8dfab1733ee1cb2c0b4fbca087ab222a4f`，生成时工作区为 clean。
本次论文导出在同一 HEAD 加论文工具的未提交改动上执行，provenance 的 `source_dirty=true`
描述导出环境，不代表历史科学运算使用了这些改动。

| 对象 | Artifact ID |
|---|---|
| report | `baede583dc2ef36330af1184d266833f3e64a3179fc8d5ce8bff1b6867307cb5` |
| asimov | `45805304950d8ad926f551d7a914fb7ed88cfd6267877aace79f613fffd6c78c` |
| freeze | `21e5e6aaeea553c274eeceaffefff6afeb60a2f3ce85146933198ac9244bd2a1` |
| prepared | `2933b92e8df4909c579499b6f57147830fd72a878bcdd3377689be479dfa23cb` |
| registration | `9784a9de8a2b64cafd3ca540e51c26c98570dda1ef29e565975b50799abcb0c5` |
| template | `649a09a23bff2317c2924261caa74ee4d9f06072af7d62498141726d2dec982d` |
| access | `1551fbf5b4751212703e8ecd6d15358aaf16ff4491685614ad93bb27c9b38385` |

核心协议 SHA-256 为 `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e`。
阈值方法是另行绑定的 `joint-support-v1`，不能只按核心协议哈希把历史 median 方法与当前结果视为同一分析。
快照目录为 `var/paper-evidence/test05-20260926/`；provenance 保存 15 个聚合来源的
大小、SHA-256、artifact、执行版本及 manifest 哈希，并记录所有训练身份。

2026-09-23 版本矩阵与旧快照选择保留在本地 `paper/evidence/history/`，原样保留历史含义。
旧 test01 的 161/200 bootstrap 和 test03 Stage B 状态均不是当前稿的结果来源。

## 数值映射

W68/AUC 取五种子中位数；直接比较先同种子配对；Shapley 和 24 个交互从完整联盟向量重算；
105 对比较均核验。代数容差 `rtol=atol=1e-12` 不代表独立统计数值验证。
论文图表及宏由 `make_figures.py` 从固定快照生成。当前 LaTeX 使用的六张 PDF 图和四个 TeX 输入已保存到 Git；
普通 PDF 编译直接读取这些文件。MC 百分位范围只读取完整预算的 bootstrap 字段，不以训练种子区间替代。

BC/AC/ABCD 的 W68 中位数分别为 1.511617/1.515244/1.535930；M0off 为 1.663723。
AC−BC、AC−ABCD、BC−ABCD 的 95% MC 配对宽度差范围均跨零，不能写成显著优于。
B、C 的 Shapley 95% MC 范围为正；A、D 跨零。200 个副本固定训练网络，不涵盖独立重新训练
或选择后区间校准；每侧 2.5% 尾部仅约 5 个次序统计量。

μ=1 的 model-self/assessment/T2 条件覆盖中位数（68%）分别为：

| 候选 | model-self | assessment | T2 |
|---|---|---|---|
| M0off | 0.6500 | 0.6280 | 0.6370 |
| AC | 0.6680 | 0.6380 | 0.6535 |
| BC | 0.6780 | 0.6580 | 0.6635 |
| ABCD | 0.6560 | 0.6460 | 0.6495 |

T2 先在各训练种子内汇总外层结果；不可把内层拟合当成独立全流程重复。图中的范围为五种子最小–最大，
不是覆盖率的置信区间。名义 template signed 产额为背景 2.497852287449695、信号 2.7683194272433287。
角色产额含角色重标度，不能跨角色相加。

## 方法与资格

`joint-support-v1` 显式指定质量边界 [105,140] GeV。非空候选为两个 score 类别各一个质量箱，
M0off 为包容计数。阈值由 calibration 背景提出 19 个分位候选，同时满足 calibration/template
支持条件后选择最接近中位数的点，不优化 W68。名义 75/75 取中位数；bootstrap 的 15000 次选择
中有 112 次偏离中位数、0 次失败。T2 固定 template、重采样 calibration 并重新选择阈值。

| 证据维度 | 当前状态 |
|---|---|
| 正式计算完成度 | 80/80 nominal；36/36 evaluation valid；200/200 bootstrap valid |
| Toy 候选拟合 | model-self 120000、assessment 120000、T2 160000，全部有效 |
| 登记及选择后覆盖 | exploratory_posthoc；selection_aware_coverage=unvalidated |
| 独立数值／物理适用性验证 | 未完成；同实现复算不能替代独立参照 |
| assessment access | single_researcher_self_review，independent=false |
| 主张资格 | primary_claim_eligible=false；类别分配敏感性 pending |

此前同次数据审查对三个 test05 根目录的 403 个 manifest 和 884 个绑定文件完成身份、大小及哈希检查，
并从保存的 Toy 区间重算 4160 组覆盖统计，未发现不一致。完整记录在本地忽略目录
`artifacts/test05-publication-review-20260926/review.md`。这不包含原始 ROOT 重新下载校验，
也不是独立物理或统计实现验证。论文导出器只检查其选定聚合来源，不能把完整性审查范围归给导出器。

本次没有重训、重拟合、改变冻结阈值、生成新 Toy 或打开新的 assessment population。
生成证据留在忽略目录，不提交为源码；迁移时须同时保存快照与运行产物，永久外部归档尚未建立。
