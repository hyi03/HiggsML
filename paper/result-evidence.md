# 论文结果证据索引与版本矩阵

核对日期：2026-09-23。中英文稿共同选择 [test01-source.json](evidence/test01-source.json) 指定的报告；[selected-snapshot.json](evidence/selected-snapshot.json) 固定快照、来源清单和报告身份。路径变更只由显式映射处理，不修改任何历史 manifest。

| 分析／证据版本 | 报告身份与执行 revision | 数值与完成度 | 本次可核验程度／资格 |
|---|---|---|---|
| **论文共同采用的 test01 归档**：`var/runs-test-01/h4l-off-test01-old1/evaluation/report` | `3fe3e15ffe27f8480719deaa2a84a201d6a5062ca2611b0c5f67d62f54d23e05`；report `3819547357354aa04fa2dd85e1da3afeeaeb8ffb` | 80/80 nominal；15/15 model-self、15/15 assessment、5/5 T2 valid；bootstrap 161/200 | 原快照 14 个来源文件与各自 manifest 哈希全部匹配；新导出再核验 report.json，共 15 个聚合文件。`incomplete`、非独立自审、主张资格 false |
| 旧中文恢复报告：`report-resume-6f5909a8b7f58d5e` | `9c2413c8e5582e967b54f5a046883d5510143873941d6a53f320813297d47d68`；`e066bae9a12e5bd2d02cd199bbd09a99151ea6d7` | 历史记载三处 model-self 预算阻断 | [旧索引原文](evidence/history/result-evidence-20260921.md) 保留；不再作为当前两稿数字来源，不把旧记录的验证日期当成本次复核 |
| 归档中另一 `var/runs-test-01/h4l-off-test01/evaluation/report` | `aecfa75935da0e8c393c4a4b637eecd9d008437d0ab574d500b0c06b749fd791`；`6cffa143f3ef97861b9b8849297b34e5c029475e` | 本次仅识别 manifest 身份 | 与 old1 不同，不按同名或部分数字相同替换来源 |
| 活跃目录 test03 Stage B：`runs/h4l-off-test03/report-B` | `1d1eaed51a9172421889d26e6b0bb584b5dbe8eb76a69383d67516e8e4616971`；`5275fc586ec25d41e84459e665c168dba6a31671` | 已发布报告的 36 单元全部 `not_run`，80/80 nominal | 已单独导出 12 个聚合来源；不是 test01，也不表示后台计算状态。用户说明 `runs/` 是尚未完成的运算 |
| joint-support 开发验证 | `docs/changes/h4l-off-joint-support-v1/verification.md` | 历史开发支持 200/200，`inference_run=false` | 仅开发证据；本次未运行新的正式 bootstrap/Toy/assessment/T2，未从开发成功推导正式结果 |

## 共同采用的精确绑定

| 对象 | 身份／执行版本 |
|---|---|
| Asimov | `5dac36b144f0992fcbfa0de6fe9d8019f22130b21548b8d8dcce8a4feb6ae876`；`65a9d24f1f6ef0478669f3f0969fed0837938f61` |
| Freeze | `01e623db2028849e7751c6c83c8811864833acd141be7eb521f0a773fbbd6a17`；`65a9d24f1f6ef0478669f3f0969fed0837938f61` |
| Prepared | `8c295b2881a808262e43300687b49d8f4c8cfde08c09cb54584c61a1e6c9d4da`；`a4ecb8f3799729a01bb05aa00f1f5ef7c11b854a` |
| 75 个训练模型 | 逐个核对训练 manifest 的引用身份；执行 revision 全为 `a4ecb8f3799729a01bb05aa00f1f5ef7c11b854a`，模型 ID 保留在快照 75 个非空 records 中 |
| Protocol digest | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e`；历史 median 阈值分析，不追溯改标为 joint-support |
| Access artifact | `0b8f4df7101b85fa2ce11f4e8f07fc100b41b5a13a6325293711045c642f2560`；`single_researcher_self_review`、`independent=false` |
| 文稿核查代码 | `5275fc586ec25d41e84459e665c168dba6a31671` 加本次未提交 F4/F11/F12 改动；不是上述运行的执行 revision |

原 14 文件归档核验记录为 `var/paper-evidence/test01-restoration-20260923.json`。共同采用的新派生快照在 `var/paper-evidence/test01-aligned-20260923-v2/`；`provenance.json` 列出逐文件大小、哈希、artifact、执行 revision、manifest 哈希与路径映射。它与原 `paper/evidence/data/` 快照分别保留，原字节不变。

## 数值与资格

W68/AUC 取五种子中位数；直接比较先同种子配对；Shapley 和 24 个交互从完整联盟向量重算；105 对均核验。代数比较容差 `rtol=atol=1e-12`，不属于独立统计数值验证。中文第 5.1–5.4 节表格由 `sync_manuscript.py` 生成；英文图表及宏由 `make_figures.py` 生成，二者使用同一固定快照。

在 μ=1 的 assessment 中，BC/AC/ABCD 的 68% 条件覆盖中位数为 0.6680/0.6340/0.6340；T2 对应 0.6660/0.6480/0.6500。这些数值有可复核来源，但没有因此获得独立数值验证或科学适用性资格。T2 先在各训练种子内汇总外层结果；不可把内层拟合当作独立全流程重复。

Prepared 审计只列非 assessment 四角色：背景／信号事件组分别为 train 1140/14377、validation 312/3503、calibration 575/7262、template 590/7221；template 的 signed 产额为背景 2.497852287449695、信号 2.7683194272433287。角色产额含角色重标度，不能相加当总产额。历史 `physics_sources_validated=true` 是旧软件字段，本次按 v2 保守解释，未获得物理来源确认。

| 证据维度 | 本次状态 |
|---|---|
| 软件契约与聚合代数 | 新代码测试及归档哈希／身份核对，见[验证记录](../docs/changes/evidence-alignment-20260923.md) |
| 产物发布 | 选定 report 的 manifest 为 complete |
| 正式计算完成度 | 总报告 incomplete；保留 bootstrap 161/200 与所有失败 |
| 独立数值验证 | 未完成；同实现复算和单模型闭合不替代独立参照 |
| 物理适用性与确认资格 | 未完成；self-review、已用样本和新目录名不创造独立性 |

本次未打开原始 ROOT、事件载荷或新的 assessment，未重训、拟合或生成伪实验。核验是所列聚合产物、部分谱系元数据和历史架构源码的检查，不是全部 checkpoint／上游字节的递归重验。生成证据留在忽略目录，不提交为源码；迁移复现包需同时保存快照和归档，永久外部归档尚未建立。
