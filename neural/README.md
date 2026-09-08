# HiggsML Neural

当前实现按 `atlas2020_4lep`（Higgs 345060 + ZZ 363490）和 `atlas2025_exactly4lep`（Higgs 345060 + ZZ 700600）两个受控 MC 配对运行。安装下载见[根 README](../README.md)，操作见 [v2 手册](docs/engineering/dataset-v2-runbook.md)。所有业务命令显式指定 `--dataset`。

正式无质量窗方案见 [inclusive 协议手册](docs/research/inclusive-protocol.md)：无窗保留、全范围训练与评价、拟合折分位数对抗器和权重归一化。现有有窗与 debug 流程继续保留。协议文件按用途命名，内部 schema 负责兼容性。

## 处理链

受控定义与文件校验 → profile/单位/归一化 → 冻结四轻子选择及 19 项特征 → development/test 分区 → 事件分组五折 OOF → 资格判断及 final fit → 同数据集 test-opening。

分类器固定 15 项输入和 7,617 参数；对抗器 1,611 参数。m4l、身份、provenance、split 和权重不进入分类器。网络、λ、epoch、早停及 Normal AUC/KS/效率规则保持冻结。

| 模块 | 职责 |
|---|---|
| `src/data_contract.py`、`config/datasets` | 与下载器共享的标准库文件身份契约 |
| `src/dataset_binding.py`、`resource_seals.py` | 数据集与科学资源快照、摘要及行身份绑定 |
| `src/config.py`、`config/profiles` | v2 协议及按输入格式组织的 branch/unit 映射 |
| `src/domain` | 冻结选择、四动量、Angular5、权重和 split |
| `src/preprocessing` | 分块读取、双分区发布、development authority gate |
| `src/training/development_reader.py` | 仅打开 development 分区；拒绝旧 mixed 单表 |
| `src/training/dataset.py`、`folds.py` | 15 维输入、fold-local scaler、物理分组防泄漏 |
| `src/training/development.py`、`trainer.py` | OOF、final fit、绑定 checkpoint/model |
| `src/training/statistics.py` | development-only 分类/fold/质量 bin 有效统计 |
| `src/training/test_reader.py`、`test_opening.py` | 同配对 gate、可选 claim、test 哈希校验与评分 |
| `src/artifacts` | canonical 序列化、不可覆盖事务、带数据集标注的图表 |

来源行身份与事件分组身份分开。相同 `channelNumber:eventNumber` 在所有来源行中保持同一 split/fold；跨 release 物理等价尚未证明，两套数据不联合训练或共享 test 反馈。

分区各有独立哈希；development 不打开 test 文件，test 阶段完成 gate/可选 claim 后才验证实际 test 字节。有窗/debug 训练权重仍按全部选后样本的类均值归一化，包含 test 权重影响；inclusive 协议改为拟合折内归一化，final fit 仅用 development。旧协议、固定计数与冻结结果仅是历史证据，不能充当新配对 golden。

- [文档索引](docs/README.md)
- [v2 运行手册](docs/engineering/dataset-v2-runbook.md)
- [Artifact schema](docs/engineering/artifact-schema.md)
- [v2 验证记录](docs/engineering/dataset-v2-verification.md)
- [重构方案](docs/engineering/dataset-isolation-refactor-plan.md)

权威平台仍为锁定的原生 ARM64。本项目只作 educational/technical demo。
