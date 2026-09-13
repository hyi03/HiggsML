# 软件架构

## 系统边界

当前项目是单一的 H4l Python package：`src/higgsml/`。它只接受受控 MC，执行协议绑定的数据准备、表示学习、校准、模板构建与 `mu` 推断。真实数据、跨数据集混训、冻结后反馈调参和覆盖既有 run 均不在系统边界内。

## 模块分层

| 模块 | 路径 | 责任 |
|---|---|---|
| CLI 与编排 | `src/higgsml/cli.py`、`src/higgsml/workflow.py` | 参数与退出码、阶段依赖、输入绑定 |
| 物理域 | `src/higgsml/physics/` | 四动量、重建、选择、Angular5、权重与事件组划分 |
| 建模 | `src/higgsml/modeling/` | 表示注册、判别器、条件 CDF 校准、矩阵元接口 |
| 统计推断 | `src/higgsml/inference/` | 模板、likelihood、区间、诊断、压力测试与报告 |
| 样本效率 | `src/higgsml/sample_efficiency/` | 冻结候选、子集、学习曲线、配对聚合与确认边界 |
| 配置与身份 | `src/higgsml/config.py`、`data_contract.py`、`dataset_binding.py`、`resource_seals.py` | 严格加载、摘要和资源/协议绑定 |
| 不可变产物 | `src/higgsml/artifacts.py`、`_manifest.py`、`_transaction.py` | canonical 序列化、staging、manifest-last 与失败收据 |

依赖方向为 CLI/编排指向建模和物理域。CLI 不承载科学计算；协议定义科学规则，运行参数只提供路径、资源和显式阶段选择。

## 数据流与反馈边界

```text
dataset contract + profile + H4l protocol
                    │
             audit / prepare
                    │
 train ── calibrate ── templates ── freeze
                                      │
                              assessment / infer
                                      │
                                   report
```

`prepare` 按物理事件组生成 train、validation、calibration、template、assessment 五个互斥角色。Assessment 只能在协议状态冻结后读取，结果不得回流修改表示、checkpoint、CDF、分箱、模板或 likelihood。

## 失败关闭与发布

每阶段必须写入 `runs/` 下尚不存在的目录。事务先写同父目录 staging，校验完成后原子发布；成功 manifest 最后写入。成功、失败和诊断 run 都不可覆盖。主要退出码为：`0` 正常终态、`2` 用法错误、`3` 输入或绑定错误、`4` 路径/事务错误、`5` 拒绝访问、`70` 未分类内部错误。

配置快照、输入摘要、协议、上游 artifact、代码/环境和随机种子进入 lineage。数据 URL、大小和 SHA-256 只在 `config/datasets/` 维护，避免文档副本漂移。

## 验证边界

当前软件支持五角色数据、可变表示、MELA 适配、条件 CDF、共同模板、freeze、`mu` inference 和样本效率实验。软件测试与合成验证不能证明完整 MC 科学结论；原生 ARM64 重放、完整 MC 运行、外部矩阵元参考和跨 release 物理等价仍需分别提供证据。详见[当前科研状态](../validation/current-status.md)和[运行手册](../reproducibility/runbook.md)。
