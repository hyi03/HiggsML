# HiggsML Neural

本目录用于实现基于 PyTorch 的对抗式 MLP 训练流程。项目保持严格 MC-only，使用固定的 15 项分类器特征，并通过背景质量对抗器降低分类分数对 `m4l` 的依赖。

完整需求、科学边界和实施阶段见[对抗式 MLP 重构设计](../neural_adversarial_mlp_refactor_design.md)。

> 当前状态：Sprint M1-02 MC-only 预处理已实现；权威 r3-ARM64 full-data gate 尚未在本机运行。

## 1. Conda 环境配置

### 1.1 固定约束

- Conda 环境名称：`pytorch`
- 权威平台：`osx-arm64`
- 开发与测试平台：`win-64`
- 神经网络框架：PyTorch 2.7.1 CPU
- 直接依赖声明：`environment.yml`
- macOS 完整依赖锁：`osx.yml`
- Windows 完整依赖锁：`win.yml`
- 权威运行禁止使用 MPS 和 CUDA；跨平台环境只用于开发验证，不能声明与权威 ARM64 运行精确等价。

所有命令均从本目录 `neural/` 执行。

### 1.2 安装 Conda Lock

如果 base 环境尚未安装 `conda-lock`：

```bash
conda install --name base --channel conda-forge conda-lock
conda-lock --version
```

### 1.3 按锁文件创建权威环境

macOS Apple Silicon 权威环境使用：

```bash
conda-lock install --name pytorch osx.yml
```

Windows x86-64 开发与测试环境使用：

```powershell
conda-lock install --name pytorch win.yml
```

两个锁文件使用相同的直接依赖版本，但包含各自平台的二进制构建、传递依赖、下载地址和哈希。不要在环境中手工追加或升级依赖。

激活环境：

```bash
conda activate pytorch
```

也可以不激活环境，统一通过 `conda run` 执行命令：

```bash
conda run -n pytorch python --version
```

### 1.4 验证环境

检查依赖一致性：

```bash
conda run -n pytorch python -m pip check
```

安装本项目的两个 console entry point（依赖已经由 lock 安装）：

```bash
conda run -n pytorch python -m pip install --no-deps -e .
```

检查 PyTorch 版本、平台和可用设备：

```bash
conda run -n pytorch python -c "import platform, torch; print('platform:', platform.platform()); print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('mps:', torch.backends.mps.is_available())"
```

权威训练即使检测到 MPS 可用，也必须由程序固定使用 CPU。运行配置和 manifest 必须记录 PyTorch build、CPU 架构、线程数和 deterministic 标志。

运行测试：

```bash
conda run -n pytorch python -m pytest -q
```

基础 CLI smoke：

```bash
conda run -n pytorch higgsml-preprocess --help
conda run -n pytorch higgsml-train --help
```

### 1.5 生成或更新锁文件

只有在 `environment.yml` 的直接依赖经过审核后，才允许重新生成锁文件：

```bash
conda-lock lock \
  --file environment.yml \
  --platform osx-arm64 \
  --lockfile osx.yml
```

```powershell
conda-lock lock `
  --file environment.yml `
  --platform win-64 `
  --lockfile win.yml
```

生成后应使用新锁创建独立验证环境，完成 `pip check` 和完整测试，再决定是否替代现有权威环境。不能在旧环境中通过临时 `pip install` 获得新的权威结果。

## 2. 按配置运行

### 2.1 MC 预处理

```bash
conda run -n pytorch higgsml-preprocess \
  --protocol config/preprocess_protocol_v1.yaml \
  --run-config config/preprocess_run.local.yaml \
  --run-dir runs/preprocess-<unique-id>
```

先复制 `config/preprocess_run.example.yaml` 为不提交的本地配置，只填写 Higgs 345060、
ZZ 363490 的只读 ROOT 路径和 `chunk_size_events`。输出路径只由 `--run-dir` 指定。
Selection、DSID、输入哈希、特征定义、权重和 split 算法由版本化 protocol 固定。

成功 run 发布 `processed/mc_events.csv.gz`、`artifacts/cutflow.json`、
`artifacts/mc_summary.json` 和最后写入的 `artifacts/manifest.json`。完整字段、canonical CSV
与 ARM64 golden 规则见 [`Preprocess Protocol V1`](docs/preprocess-protocol-v1.md)。

### 2.2 Development 训练

```bash
conda run -n pytorch higgsml-train develop \
  --input-run runs/preprocess-<id> \
  --protocol config/adversarial_mlp_protocol_v1.yaml \
  --run-dir runs/mlp-development-<unique-id>
```

该命令只能访问 development 数据，用于五折 OOF、候选去相关强度比较、资格判断和工作点冻结，不得读取或评价 held-out test。

### 2.3 显式开启 Held-out Test

只有 development run 合格、已经封存且另有明确授权时，才可执行：

```bash
conda run -n pytorch higgsml-train open-test \
  --development-run runs/mlp-development-<id> \
  --run-dir runs/mlp-test-<unique-id>
```

Test 只评价已经冻结的模型和工作点，不得触发重新训练、重新选阈值或放宽资格门槛。

## 3. 稳定退出码

| 退出码 | 含义 |
|---:|---|
| `0` | 成功或声明的正常科学终态 |
| `2` | CLI usage 错误 |
| `3` | 输入、schema、哈希或 protocol 绑定失败 |
| `4` | run path 或事务失败 |
| `5` | 资格或 test-opening 拒绝 |
| `70` | 未预期内部错误 |

完整科学安全与开发约束见 [`AGENTS.md`](AGENTS.md)。
