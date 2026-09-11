# Research 性能重构实施记录

实施日期：2026-09-11。设计与对照版本：[重构方案](research-performance-refactor-design.md)，`66784d3af0a4b73c6001acc94404da3540040866`。

本次修改限定于研究模块、研究 CLI、资源配置和测试。未读取真实数据、实际 held-out 或实际 assessment，也未启动完整 MC 实验。历史分类器、科学协议、训练/toy 预算及 frozen/failed run 不变。

## 实现范围

| 阶段 | 已实现 | 交付边界 |
|---|---|---|
| A | 固定 Git 基线的合成对照脚本；wall/CPU、采样 RSS、版本/源码摘要、数值与身份对照；运行阶段计时 | ROOT prepare 分别记录 identity、payload、selection、feature、write 时间及请求数/区间长度分布；生产端到端验收仍需代表性输入 |
| B | 最大连续 development 区间、长区间切分、identity 回填、稳定 source/entry 顺序 | 仅串行 ROOT reader；应用请求范围通过合成测试，底层解释边界见下文 |
| C | 分块事件维 CDF 插值；训练 tensor、background mask、验证数组和诊断分箱/排序缓存 | 不降低逐 epoch 评分、threshold 重算频率；保留 200 epoch 与随机排列 |
| D | 稀疏物理组矩阵、独立占用矩阵、完整协方差；公共网格增量合并；stress 固定编码重加权 | 校准缓存区间成员与 moments，只重新计算合并区间，仍重新检查跨 score-bin；未强行统一两种权重公式 |
| E | `profile_intervals` 共用一次无条件 MLE；旧 `profile_interval` 包装；各区间独立失败 | Asimov、toys、assessment 和 modeled stress 接入；未启用 fixed-POI warm start |
| F | 普通/assessment toy 并行，T2 outer 推断并行；任务有界、固定输入、按序收集、进程线程限制 | 默认串行。T2 校准/映射准备按原顺序留在父进程，成功后才消费 inner seed；worker 内不再创建推断池 |
| G | JSONL 逐行写入/分块加载，先读 identity；角色按唯一组求值；安全扫描中累计 population 摘要；ME 流式行对象、supplement binding 索引；T2 raw-score 缓存；joint-cell 与 auxiliary 布局复用 | 只缓存当前调用的固定输入；模板/模型复用后在发布前重新检查上游模板摘要，原 artifact 发布校验保留 |

ROOT 读取进程池、候选/seed 训练进程池、fixed-POI warm start 和 P3 固定小循环未默认启用。研究 CLI 的 train 本来一次只训练一个候选；本次未增加多候选调度入口。需要另行 profiling 的项目仍保持原实现。

## 资源接口

研究 CLI 各阶段可传入 `--resources config/research_resources.example.json`。省略时使用同样默认值：

```json
{"workers":1,"worker_threads":1,"root_max_entries":4096}
```

- `workers`：推断进程数。普通/assessment 推断按 toy 并行；T2 按准备完成的 outer replica 并行。每次最多 `workers` 个待处理任务，父进程独占发布。
- `worker_threads`：每个子进程的 Torch/BLAS 线程上限；不改变既有串行训练线程环境。
- `root_max_entries`：单次合法 development 区间的行数上限，任何数值都不允许跨 test 间隙。

未知字段、布尔值、非整数或非正资源值拒绝。资源记录存入 manifest 的 `resources`，实现标识为 `performance_implementation=research-refactor-v1`；它们不进入科学协议、model/mapping identity。成功阶段还记录 `performance`，ROOT prepare 记录 `root_prepare_metrics`。

并行使用 `research-parallel` 可选依赖；当前 Windows/ARM64 锁文件已包含对应版本的 cloudpickle 和 threadpoolctl，本次不修改权威环境锁。只安装基础包的其他环境可用 `python -m pip install '.[research-parallel]'` 补齐；默认串行不加载这些可选依赖。

CDF 与 joint-cell toy 投影使用约 8 MiB 的核心临时数组分块预算；T2 raw-score 缓存使用约 64 MiB 上限，超出后沿用评分路径。模板始终使用稀疏 group/bin 数据，避免 dense groups × bins 中间矩阵；artifact 仍输出完整 bins × bins covariance。这些是局部工作数组/缓存预算，**不是整个进程 RSS 限额**：DataFrame、最终 toy 结果、进程运行时及完整 covariance 仍需常驻内存。

## 数值、身份与故障行为

- 合箱通过 `G_new = G @ A` 后计算协方差，保留跨箱组贡献；group count 用占用关系的并集。抵消为零的组仍占用 bin。
- 校准保留物理组平方和及 bootstrap multiplicity；合箱后仍可能触发跨 score-bin 拒绝。
- 不按文件顺序修改 population hash：仍然对去重、排序后的 `(event_group_id, label, split, dataset)` 原结构编码并摘要，包含尚未解析 payload 的 assessment identity。
- ROOT 导出直接复用写入时累计的 population digest；复制调用者提供的 JSONL 时，仍在最终副本上复核 identity，避免复制前后的文件变化使旧缓存与已发布内容不一致。
- T2 不能在校准失败时预先消耗 inner seed。父进程按原序执行前置校准和映射，固定输入交给 worker。ResearchError 保留 replica 终态；未预期 worker 异常传播至父进程和原事务失败处理。
- 新增测试检查 worker=1/2 输出、错误后进程回收、配对 observation、共享 MLE 次数和单一置信区间失败。
- 加法顺序变化可能产生新的科学 payload digest。对照脚本单独报告完整 digest 是否相同，不以数值近似相等冒充相同 artifact。所有后续实验使用新 run。

## ROOT 解释边界：仍需绑定来源验收

在安装的 uproot 5.7.5 上检查了 `AsDtype.basket_array`、`Numerical.final_array` 和 `AsJagged`，并运行了只含合成数据的 mixed-basket 探针。一个请求仅返回 1 entry，但解释阶段能出现覆盖整个 basket 的数值视图；数值实现先建立视图，`final_array` 再对所请求范围切片并转换。Jagged 路径还会处理 offsets，带 header 的路径会操作整块字节缓冲。

因此，应用层 `entry_start/entry_stop` 不跨 test **不能独立证明**所有绑定分支都满足严格的“不解释 held-out payload”契约。这个问题也存在于基线逐 entry reader，不能把批量请求优化写成已解决它。新的 docstring 已去掉未经证明的解码保证。

本次仅完成合成 ROOT 的请求范围、身份、顺序和吞吐对照；没有以真实绑定 ROOT 测试该边界。**B 阶段完整受控 MC 验收尚未完成**，需核实实际分支 interpretation 与项目访问契约后再放行生产性能实验。这不授权整块 payload 解码后筛选，也不授权打开 held-out。

## 验证与复测

最终 Windows 验证：`conda run -n pytorch python -m pytest -q` 为 **532 passed，60 warnings，332.74 s**；`python -m pip check` 返回 `No broken requirements found`；`git diff --check` 通过。警告来自现有 pyhf/jsonschema 弃用提示及 TestOpeningResult 的测试收集提示。新增 18 个参数化专项用例覆盖读取范围、协方差、合箱、插值、共享拟合、并行、故障及序列化。

本次三次重复的中位耗时比（基线 / 优化后）：

| 合成工作负载 | 比值 | 一致性结果 |
|---|---:|---|
| 1,000 entry scalar/jagged ROOT reader | 约 5.2× | 事件内容和顺序相同 |
| 200,000 事件 CDF 插值 | 约 12.5× | 预设数值容差内一致 |
| 14,000 行校准拟合 | 约 1.27× | 完整 payload digest 相同 |
| 两候选公共质量网格 | 约 2.7× | 完整 payload digest、合箱历史相同 |
| 三组单箱 Asimov | 约 1.16× | 完整 payload digest 相同；无条件 MLE 6→3 次；耗时存在首轮初始化影响 |
| 72 行、M6 完整 200 epoch | 约 1.20× | 完整模型 payload、history、checkpoint 和选择轮次相同 |

合成测量原始记录见 [research-performance-synthetic-results.json](research-performance-synthetic-results.json)。记录包含三次耗时、范围、RSS 样本、软件版本和实施文件摘要，科学数值比较预设 `rtol=atol=1e-12`，离散状态与选择要求相同。200 epoch 基准核对完整 history、checkpoint 和选择轮次；ROOT 吞吐样例不包含完整选择/特征重建。

从 `neural/` 运行：

```powershell
conda run -n pytorch python -m pytest -q tests/research/test_performance_refactor.py
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
conda run -n pytorch python -m scripts.research_performance_benchmark --output <新的结果路径.json>
```

基准不覆盖已有结果文件。测量时避免同时运行测试/训练。计时在同一进程中重复，未清空操作系统缓存；首次导入、初始化和内存分配会影响首轮。RSS 每 10 ms 采样，包含保留分配，不等于隔离子进程测得的操作峰值。小型拟合的加速可能接近波动，应以 MLE 调用数减少和更复杂模型测量分别判断。

Windows 测试不能代替锁定 ARM64 权威验证、独立物理参考、完整 MC 数值一致性和科学结论。项目仍为 MC-only educational/technical demo。
