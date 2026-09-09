# 软件架构

## 1. 系统边界

**当前代码已实现。** `neural/` 是独立 Python package，不以 `xgboost/src` 为运行时依赖。包提供三个产品入口：`higgsml-preprocess`、`higgsml-train` 和 `higgsml-test`。CLI 层只负责参数、日志与稳定退出码适配，科学计算和发布事务位于 application/domain 层。

所有产品路径只接受受控 MC 数据集。真实数据、跨数据集联合训练、test 反馈调参以及对冻结 run 的覆盖均在系统边界之外。

## 2. 当前分层

| 层 | 主要模块 | 责任 |
|---|---|---|
| CLI | `src/cli/` | 参数解析、显式 dataset 选择、错误到退出码映射 |
| 资源与配置 | `src/data_contract.py`、`dataset_binding.py`、`config.py`、`resource_seals.py` | 严格加载 YAML/JSON、资源摘要、数据集和协议绑定 |
| Domain | `src/domain/` | 四动量、选择、Angular5、权重、事件 split；不负责 I/O 发布 |
| Preprocessing | `src/preprocessing/` | ROOT 分块读取、profile 映射、重建、双分区和 authority comparator |
| Training | `src/training/` | development reader、fold-local scaler、MLP/adversary、OOF、资格、final fit、test-opening |
| Artifacts | `src/artifacts/` | canonical 序列化、摘要、staging、原子发布和失败收据 |

依赖方向应从 CLI 指向 application，再指向 domain/serialization。ROOT 读取器和 artifact writer 是边界适配器；domain 算法不应自行解析命令行或决定磁盘路径。

## 3. 数据流与信任边界

```text
受控 dataset JSON + profile + protocol + run config
                       │
             摘要、schema、身份校验
                       │
                 ROOT MC 读取
                       │
       重建/选择/19 项变量/权重/事件身份
                       │
          development 与 test 独立发布
                │                   │
      development-only reader       │（不在开发阶段打开）
                │                   │
        五折 OOF → 资格 → final fit │
                └────冻结绑定───────┘
                              test-opening
```

Development reader 是训练侧唯一持久输入 binder：它验证 preprocess manifest 与 development artifact，但不打开、stat 或重新散列 test 表。Test-opening 在 dataset、协议、lineage、资格、模型、scaler 和工作点全部通过后才读取 test 字节。

## 4. 失败关闭与不可变发布

每次运行必须使用允许根目录下尚不存在的新路径。事务先写同一父目录下的 staging，再原子发布；已有成功、失败或 partial run 都不可覆盖。成功 manifest 最后写入，失败只发布经过清理的 `failure.json`，不得同时伪造成功 manifest。

CLI 稳定退出码为：`0` 成功，`2` 用法错误，`3` 输入/schema/hash/protocol 绑定错误，`4` 事务错误，`5` test-opening 被拒绝，`70` 未分类内部错误。进程退出码不是科学状态；科学状态由 artifact 明确记录。

## 5. 复现与证据等级

配置快照、输入摘要、canonical 内容摘要、软件/平台信息和 lineage 必须进入 manifest。压缩 CSV 同时记录压缩文件摘要与解压后 canonical 内容摘要。数据定义的精确 URL、大小与 SHA-256 只在 `config/datasets/` 维护，避免文档副本漂移。

Windows 与 synthetic 测试可证明软件行为；锁定原生 ARM64 才能产生 authority 级平台证据。Authority reference 必须预先独立登记，首次输出不能自认证为 golden。模型、运行产物和本地配置不得提交 Git。

## 6. 规划边界

**最新方案规划中。** H4l 方案需要独立的 `src.research`、`higgsml-research`、ResearchProtocol、五角色研究数据、可变表示、MELA、条件 CDF、模板和 μ inference。其目标架构见 [`research-software-design.md`](research-software-design.md)，不能借用当前五折 OOF 或 `eligible` 状态冒充完成。

**需要外部或权威验证。** 当前架构的锁定 ARM64 重放、完整 MC 科学运行、跨 release 物理等价和外部矩阵元参考仍需独立证据。
