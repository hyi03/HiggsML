# HiggsML H4l

本仓库只维护 `H -> ZZ* -> 4l` 的 MC-only 教育与技术研究流程。核心研究问题是比较不同运动学表示、质量条件化与样本效率对信号强度 `mu` 推断精度的影响。仓库输出不构成 ATLAS 结果、Higgs discovery 或物理测量。

## 目录

```text
src/higgsml/       H4l Python 包
config/            数据集契约、研究协议、schema 与配置示例
scripts/           数据下载和可复现实验编排
tests/             软件与合成数据测试
docs/              方法、复现和验证文档
paper/             论文稿件
data/raw/          本地 MC 输入（忽略，不提交）
runs/              本地不可变运行产物（忽略，不提交）
```

历史 legacy15 预处理、训练、qualification、final-fit、test-opening 和旧版 XGBoost 实现均不属于当前项目，相关运行入口与源码已经移除。

## 安装

项目要求 Python 3.12。环境定义位于仓库根目录：

```bash
conda env create -f environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip check
```

研究扩展依赖按需安装：

```bash
python -m pip install -r requirements-research.txt
```

macOS ARM64 和 Windows 的锁定环境分别见 `osx.yml` 与 `win.yml`。

## 准备受控 MC 数据

```bash
python scripts/init_data.py --dataset atlas2020_4lep
```

数据写入 `data/raw/<dataset>/`，只有文件大小和 SHA-256 与数据集契约一致后才会发布。正式 H4l 协议当前使用 `atlas2020_4lep`；不得读取或处理真实数据。

## 运行 H4l 工作流

主要命令入口为 `higgsml`，完整参数可用 `higgsml --help` 查看。推荐通过跨平台编排脚本运行：

```bash
python scripts/h4l_prepare.py --run-name 001
python scripts/h4l_g1.py --run-name 001
python scripts/h4l_run.py --run-name 001
```

默认协议位于 `config/protocols/h4l_v2.json`。每次运行必须使用 `runs/` 下的新目录；已完成、失败或诊断运行均不可覆盖。样本效率子流程使用同一个入口：

```bash
higgsml sample-efficiency --help
higgsml sample-efficiency-report --help
higgsml sample-efficiency-controls --help
```

## 文档与论文

- [文档索引](docs/README.md)
- [研究方案](docs/methods/research-project.md)
- [复现实验手册](docs/reproducibility/runbook.md)
- [当前证据状态](docs/validation/current-status.md)
- [论文稿件](paper/manuscript.md)

## 软件验证

```bash
python -m compileall -q src scripts tests
python -m pytest -q
```

软件测试、合成数据验证、完整 MC 科学验证与原生 ARM64 权威验证是不同证据层级，报告时不得互相替代。
