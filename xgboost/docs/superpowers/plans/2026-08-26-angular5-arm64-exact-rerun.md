# DropTop4 + Angular5 ARM64 Exact Rerun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在原生 Apple Silicon ARM64 环境中，以不放宽任何数值比较、科学门槛或数据封存规则的方式，从已审查的 source-identity 实现继续完成 Angular5 enrichment 和一次性 MC-only 训练。

**Architecture:** 保留 R2 的稳定 `(source_sample, source_entry)` 身份设计和逐字节旧 CSV 列权威性，只为 ARM64 重跑增加一组严格、不可覆盖的 R3-ARM64 配置与 run path。生产链按 identity baseline → Angular5 enrichment → 15-feature mass-bin reweighting 顺序推进，每一级成功 manifest/table 的实际 SHA-256 都冻结到下一级配置；任何失败路径永久保留且不复用。

**Tech Stack:** macOS arm64、Python 3.12.13、NumPy 2.5.1、pandas 3.0.5、uproot 5.7.5、PyYAML 6.0.3、scikit-learn 1.9.0、XGBoost 3.3.0、pytest。

**Spec:** `docs/superpowers/specs/2026-08-26-drop-top4-angular5-source-identity-r2-design.md`，并继续受 `docs/superpowers/specs/2026-08-26-drop-top4-angular5-reweighting-design.md` 约束。本计划只改变执行架构和新鲜输出命名，不改变物理、特征、训练或验收政策。

## Global Constraints

- 当前工作分支是 `codex/angular5`；已审查实现基线提交为 `fd0639b`，ARM 设备的 HEAD 必须包含该提交。
- 已失败的 `runs/angular5-identity-mc-363490-2026-08-26-r2` 是不可修改证据，不得删除、修复、补全或复用。
- R3-ARM64 不采用浮点容差。旧列（包括派生运动学量）继续要求解析后精确相等；权威 CSV 的旧 lexical tokens 继续逐字节保留。
- 只有确认 Python 进程自身是原生 `arm64` 且未由 Rosetta 转译后，才允许执行生产命令。
- 当前研究严格 MC-only：不得读取、复制、hash、解析、评分、绘图或 inventory `data16_periodA.root` 或其他真实数据。
- `source_sample` 只能是 `higgs_345060` 或 `zz_363490`；`source_entry` 是 selection 前零起始的原始 TTree entry。
- `(source_sample, source_entry)` 是唯一 enrichment join identity；重复 legacy event key 必须保留并报告。
- `source_sample`、`source_entry`、`m4l`、标识、provenance、split、label、weights 和四个 DropTop4 移除变量不得进入模型。
- AUC 门槛保持 `>= 0.80`；loose/medium/tight 三个 ZZ mass KS 均保持 `<= 0.10`；每个工作点 signal efficiency 必须严格大于 achieved ZZ efficiency。
- held-out MC test 只能在第一个合格 development-OOF iteration 出现后开启一次；若没有合格 iteration，则 `test_opened: false`，且不得生成模型或 test artifact。
- 每个生产路径只能 claim 一次。失败后必须创建下一版设计、配置和新 path，不能在原路径重跑。
- 所有生产发布都继续使用 descriptor-bound input、no-follow/no-clobber、failure terminal、source freshness check 和 manifest-last。

---

## 1. 当前断点和已知结论

### 1.1 已完成代码

以下提交已完成并审查：

```text
9a6cf5c  R2 source-identity design
41ff9ea  R2 implementation plan
b34c5e0  stable opt-in ROOT source_entry
24e723a  identity bootstrap transformation
ba7ed57  multiline/quoted CSV preservation
a084ba4  sealed identity run, publication, and CLI
fd0639b  duplicate evidence and post-claim failure hardening
```

已验证基线：

```text
843 passed
56 focused identity tests passed
5 known unrelated sklearn/hep_ml warnings
```

当前仓库尚未包含以下两个 R2 配置，也尚未实现/执行后续 R2 enrichment 和 15-feature training wiring：

```text
config/angular5_mc_dsid363490_r2.yaml
config/mass_bin_reweighting_drop_top4_angular5_r2.yaml
```

因此 ARM 设备不能从 identity 命令直接跳到训练；identity 成功后必须继续完成本计划 Task 5–8。

### 1.2 R2 失败证据

失败路径：

```text
runs/angular5-identity-mc-363490-2026-08-26-r2
```

终态：

```text
ValueError: source identity old-column mismatch: mZ1
failure.json SHA-256:
16316f80a3ede0b493e2f5be7fc382fa1522b18b25ef638f2c86c003544609df
```

该 run 没有发布 identity table、complete manifest、enrichment、模型，也没有打开 test 或访问真实数据。

### 1.3 已确认根因

身份映射正确，权威表总行数为 `199104`。legacy key 只有两个重复组、四行：

| eventNumber | `source_sample` | raw `source_entry` |
|---:|---|---:|
| 102001 | `higgs_345060` | 173348 |
| 102001 | `higgs_345060` | 345900 |
| 1136001 | `higgs_345060` | 340911 |
| 1136001 | `higgs_345060` | 342358 |

x86_64/Rosetta 重算值与 ARM 冻结表的最大绝对差异为：

| 字段 | 最大绝对差异 |
|---|---:|
| `mZ1` | `9.66e-13` |
| `mZ2` | `8.19e-13` |
| `m4l` | `1.83e-12` |
| `pt4l` | `1.14e-13` |
| angular/distance derived quantities | 约 `1e-15`–`1e-14` |

同版本依赖的 x86_64 隔离环境仍产生 x86_64 数值，因此根因是 CPU/运行架构，而不是 source identity、CSV parser、selection 或 ROOT 数据损坏。本计划选择原生 ARM64 精确重放，不采用曾讨论的 `5e-12` R3 容差方案。

## 2. 固定的新路径和命名

ARM64 生产运行必须使用以下三个新路径：

```text
runs/angular5-identity-mc-363490-2026-08-26-r3-arm64
runs/angular5-mc-363490-2026-08-26-r3-arm64
runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26-r3-arm64
```

对应配置固定为：

```text
config/angular5_identity_mc_dsid363490_r3_arm64.yaml
config/angular5_mc_dsid363490_r3_arm64.yaml
config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml
```

不要在 ARM 设备上直接执行 R2 命令。即使 R2 目录没有随 Git 传输，R2 路径已经代表一次真实失败，仍不得重新使用。

## 3. 跨设备必须传输的文件

Git 不传输 `data/`、`runs/` 或虚拟环境。不要复制旧 `.venv`。必须按原相对路径复制以下 MC-only 文件或冻结运行目录：

```text
data/raw/higgs.root
data/raw/zz_363490.root
runs/full-baseline-363490-2026-08-11-r2/
runs/full-training-363490-2026-08-11-r2/
runs/mass-ablation-363490-2026-08-11/
runs/mass-reweighting-363490-2026-08-11/
```

至少要存在并保持原字节的生产输入是：

| 路径 | SHA-256 |
|---|---|
| `config/dsid363490.yaml` | `0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320` |
| `runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json` | `10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` |
| `runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz` | `1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e` |
| `data/raw/higgs.root` | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `data/raw/zz_363490.root` | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |
| `config/mass_bin_reweighting_drop_top4.yaml` | `950c4e700ba2a82c7638e0fdebbe60c60c80fc984e815a0e2bd1f664f6e00791` |
| `runs/full-training-363490-2026-08-11-r2/artifacts/training_manifest.json` | `da015d0a00bb002e69dc98eb9631c1b561af65f8da44b78a641d4e013558bf65` |
| `runs/mass-ablation-363490-2026-08-11/artifacts/study_manifest.json` | `5120e6080e82b14f66917ba731c98715fa5d6190c25c396d8c675200e9ca52df` |
| `runs/mass-reweighting-363490-2026-08-11/artifacts/study_manifest.json` | `145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38` |

不要复制 `data/raw/data16_periodA.root`。如果整目录传输，R2 failure directory 可以原样保留，但绝不能修改；R3-ARM64 使用完全不同的路径。

---

### Task 1: 在 ARM 设备恢复源码与冻结输入

**Files:**
- Verify: `AGENTS.md`
- Verify: `docs/superpowers/specs/2026-08-26-drop-top4-angular5-source-identity-r2-design.md`
- Verify: `docs/superpowers/plans/2026-08-26-drop-top4-angular5-source-identity-r2.md`
- Verify: 本文件

**Interfaces:**
- Consumes: `codex/angular5` Git branch 和手动传输的 MC-only artifacts。
- Produces: clean tracked tree、包含 `fd0639b` 的 HEAD、通过 SHA-256 的冻结输入。

- [ ] **Step 1: 在项目根目录确认源码基线**

  ```bash
  git switch codex/angular5
  git status --short --branch
  git merge-base --is-ancestor fd0639b HEAD
  ```

  Expected: 当前分支为 `codex/angular5`，第三条命令退出码为 `0`，没有意外 tracked changes。

- [ ] **Step 2: 阅读冻结约束**

  依次完整阅读：

  ```text
  AGENTS.md
  README.md
  docs/project/overview.md
  docs/roadmap/next-stage.md
  docs/superpowers/specs/2026-08-26-drop-top4-angular5-reweighting-design.md
  docs/superpowers/specs/2026-08-26-drop-top4-angular5-source-identity-r2-design.md
  docs/superpowers/plans/2026-08-26-drop-top4-angular5-source-identity-r2.md
  docs/superpowers/plans/2026-08-26-angular5-arm64-exact-rerun.md
  ```

- [ ] **Step 3: 复制第 3 节列出的文件和运行目录**

  保持相对路径和文件字节不变。不要复制 `.venv`，不要复制任何真实数据 ROOT。

- [ ] **Step 4: 校验所有当前生产必需输入**

  ```bash
  shasum -a 256 \
    config/dsid363490.yaml \
    runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json \
    runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz \
    data/raw/higgs.root \
    data/raw/zz_363490.root \
    config/mass_bin_reweighting_drop_top4.yaml \
    runs/full-training-363490-2026-08-11-r2/artifacts/training_manifest.json \
    runs/mass-ablation-363490-2026-08-11/artifacts/study_manifest.json \
    runs/mass-reweighting-363490-2026-08-11/artifacts/study_manifest.json
  ```

  Expected: 九个结果逐项等于第 3 节表格。任何一个不同都停止，不运行测试或生产命令。

- [ ] **Step 5: 确认真实数据不在本次工作面**

  ```bash
  test ! -e data/raw/data16_periodA.root
  ```

  Expected: 退出码 `0`。如果真实数据因整目录复制而存在，不要读取或 hash；先把本研究放在不含该文件的独立 MC-only 工作副本中。

### Task 2: 建立并验证原生 ARM64 环境

**Files:**
- Create locally, never commit: `.venv-arm64/`
- Verify: `requirements.txt`

**Interfaces:**
- Consumes: 原生 Apple Silicon Python 3.12.13 和 Homebrew ARM64 `libomp`。
- Produces: `.venv-arm64/bin/python`，其架构和关键版本与冻结 baseline 一致。

- [ ] **Step 1: 验证操作系统进程未运行在 Rosetta 下**

  ```bash
  uname -m
  arch
  sysctl -in sysctl.proc_translated 2>/dev/null || true
  ```

  Expected: 前两项均为 `arm64`；`sysctl.proc_translated` 为 `0` 或该键不存在，绝不能为 `1`。

- [ ] **Step 2: 安装原生 OpenMP 并创建独立虚拟环境**

  ```bash
  brew install libomp
  /usr/bin/arch -arm64 python3.12 -m venv .venv-arm64
  .venv-arm64/bin/python -m pip install --upgrade pip
  ```

  创建环境前先确认 `python3.12 --version` 精确为 `Python 3.12.13`。若不是，先安装原生 3.12.13；不要用 3.13 或 x86_64 Python 代替。

- [ ] **Step 3: 安装冻结参考版本**

  ```bash
  .venv-arm64/bin/python -m pip install \
    "awkward==2.12.0" \
    "hep_ml==0.8.0" \
    "matplotlib==3.11.1" \
    "mplhep==1.3.2" \
    "numpy==2.5.1" \
    "pandas==3.0.5" \
    "PyYAML==6.0.3" \
    "scikit-learn==1.9.0" \
    "tqdm==4.70.0" \
    "uproot==5.7.5" \
    "vector==1.8.1" \
    "xgboost==3.3.0" \
    pytest
  ```

- [ ] **Step 4: 用 Python 自检架构与关键版本**

  ```bash
  .venv-arm64/bin/python - <<'PY'
  import platform
  import sys
  import numpy
  import pandas
  import sklearn
  import uproot
  import xgboost
  import yaml

  expected = {
      "numpy": "2.5.1",
      "pandas": "3.0.5",
      "sklearn": "1.9.0",
      "uproot": "5.7.5",
      "xgboost": "3.3.0",
      "yaml": "6.0.3",
  }
  actual = {
      "numpy": numpy.__version__,
      "pandas": pandas.__version__,
      "sklearn": sklearn.__version__,
      "uproot": uproot.__version__,
      "xgboost": xgboost.__version__,
      "yaml": yaml.__version__,
  }
  assert platform.machine() == "arm64", platform.machine()
  assert platform.python_version() == "3.12.13", platform.python_version()
  assert actual == expected, actual
  print(sys.executable)
  print(platform.platform())
  print(actual)
  PY
  ```

  Expected: assertions 全部通过，Python executable 位于 `.venv-arm64`。

- [ ] **Step 5: 运行源码基线测试并记录环境**

  ```bash
  .venv-arm64/bin/python -m pip freeze > /tmp/angular5-arm64-pip-freeze.txt
  .venv-arm64/bin/python -m pytest -q
  ```

  Expected: `843 passed`；只允许已知的 5 个 sklearn/hep_ml warnings。测试数因后续新增 R3-ARM64 tests 增加时，要求所有 tests pass。

### Task 3: 增加严格的 R3-ARM64 identity 配置和执行门

**Files:**
- Create: `config/angular5_identity_mc_dsid363490_r3_arm64.yaml`
- Modify: `src/angular5_identity_run.py`
- Modify: `scripts/build_angular5_identity_mc.py`
- Modify: `tests/test_angular5_identity_run.py`
- Modify: `tests/test_build_angular5_identity_mc_script.py`

**Interfaces:**
- Consumes: 已审查的 R2 identity implementation 和第 2 节固定 R3-ARM64 path。
- Produces: 只接受 exact R3-ARM64 config/path、只在 native arm64 上生产、仍保持 exact old-column comparison 的 identity command。

- [ ] **Step 1: 写失败测试**

  测试必须逐项证明：

  ```text
  config path = config/angular5_identity_mc_dsid363490_r3_arm64.yaml
  output_run = runs/angular5-identity-mc-363490-2026-08-26-r3-arm64
  platform.machine() = arm64
  sysctl.proc_translated != 1
  old-column comparison remains exact
  no tolerance field exists in config or evidence
  R2 failed path is rejected as an output
  CLI still exposes only --config and --run-dir
  ```

- [ ] **Step 2: 运行测试确认 RED**

  ```bash
  .venv-arm64/bin/python -m pytest \
    tests/test_angular5_identity_run.py \
    tests/test_build_angular5_identity_mc_script.py -q
  ```

  Expected: 新 R3-ARM64 cases 因配置/平台 gate 尚不存在而失败。

- [ ] **Step 3: 最小实现 sealed variant**

  从 R2 YAML 复制全部物理、source 和 artifact policy，只把配置名与 output run 改为第 2 节精确值。实现必须选择有限的 sealed profile，不能把 output path 或 architecture 变成任意运行参数；R2 行为保留为历史兼容，但生产入口不得把 R2 failure path 当成新鲜路径。

  native ARM gate 必须在 claim output 前执行。`platform.machine() != "arm64"` 或 Rosetta 标志为 `1` 时立即失败，且不能创建 R3-ARM64 run directory。

- [ ] **Step 4: 验证 GREEN 和完整测试**

  ```bash
  .venv-arm64/bin/python -m pytest \
    tests/test_io.py \
    tests/test_angular5_identity.py \
    tests/test_angular5_identity_run.py \
    tests/test_build_angular5_identity_mc_script.py -q
  .venv-arm64/bin/python -m pytest -q
  git diff --check
  ```

  Expected: 全部通过；没有生产 run 被创建。

- [ ] **Step 5: 提交 R3-ARM64 identity wiring**

  ```bash
  git add config/angular5_identity_mc_dsid363490_r3_arm64.yaml \
    src/angular5_identity_run.py scripts/build_angular5_identity_mc.py \
    tests/test_angular5_identity_run.py tests/test_build_angular5_identity_mc_script.py
  git commit -m "feat: add sealed ARM64 Angular5 identity rerun"
  ```

### Task 4: 一次性执行并审计 ARM64 identity baseline

**Files:**
- Produce once: `runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/`
- Create only after success: `config/angular5_mc_dsid363490_r3_arm64.yaml`

**Interfaces:**
- Consumes: Task 3 reviewed command 和五个 exact protected inputs。
- Produces: 199104-row identity table、validation evidence、complete manifest，以及下一级配置使用的实际 manifest/table hashes。

- [ ] **Step 1: 运行最终 preflight**

  ```bash
  git status --short
  test ! -e runs/angular5-identity-mc-363490-2026-08-26-r3-arm64
  .venv-arm64/bin/python -m pytest -q
  ```

  Expected: tracked tree clean、目标不存在、完整测试通过。再次执行 Task 1 的九文件 SHA-256 命令。

- [ ] **Step 2: 只执行一次 identity command**

  ```bash
  .venv-arm64/bin/python -m scripts.build_angular5_identity_mc \
    --config config/angular5_identity_mc_dsid363490_r3_arm64.yaml \
    --run-dir runs/angular5-identity-mc-363490-2026-08-26-r3-arm64
  ```

  Expected terminal line:

  ```text
  published 199104 MC source identities to runs/angular5-identity-mc-363490-2026-08-26-r3-arm64
  ```

- [ ] **Step 3: 审计 success allowlist 和身份内容**

  成功目录必须恰好包含：

  ```text
  config.yaml
  processed/mc_events_source_identity.csv.gz
  artifacts/identity_validation.json
  artifacts/run_manifest.json
  ```

  执行：

  ```bash
  .venv-arm64/bin/python - <<'PY'
  from pathlib import Path
  import pandas as pd

  root = Path("runs/angular5-identity-mc-363490-2026-08-26-r3-arm64")
  expected = {
      "config.yaml",
      "processed/mc_events_source_identity.csv.gz",
      "artifacts/identity_validation.json",
      "artifacts/run_manifest.json",
  }
  actual = {
      str(path.relative_to(root))
      for path in root.rglob("*")
      if path.is_file()
  }
  assert actual == expected, actual
  assert not (root / ".terminal.failed").exists()
  frame = pd.read_csv(root / "processed/mc_events_source_identity.csv.gz")
  assert len(frame) == 199104
  assert list(frame.columns[-2:]) == ["source_sample", "source_entry"]
  assert not frame[["source_sample", "source_entry"]].duplicated().any()
  duplicate = frame.duplicated(
      ["runNumber", "eventNumber", "channelNumber"], keep=False
  )
  groups = frame.loc[duplicate].groupby(
      ["runNumber", "eventNumber", "channelNumber"], sort=False
  ).ngroups
  assert duplicate.sum() == 4
  assert groups == 2
  print(frame.loc[duplicate, [
      "runNumber", "eventNumber", "channelNumber", "source_sample", "source_entry"
  ]].to_string(index=False))
  PY
  ```

- [ ] **Step 4: 处理失败分支**

  如果 command 失败，立即停止。保留该 R3-ARM64 目录及 `.terminal.failed`/`failure.json`，不要再次执行 command，不要更改比较规则。记录 native architecture、`pip freeze`、error 和最大差异后，另行设计 R4。

- [ ] **Step 5: 冻结实际 identity receipts**

  ```bash
  shasum -a 256 \
    runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/artifacts/run_manifest.json \
    runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/processed/mc_events_source_identity.csv.gz
  ```

  将这两个实际值写入新建的 `config/angular5_mc_dsid363490_r3_arm64.yaml`，不得预填、猜测或复制 R2 的不存在 receipt。

### Task 5: 实现 R3-ARM64 source-identity Angular5 enrichment

**Files:**
- Create: `config/angular5_mc_dsid363490_r3_arm64.yaml`
- Create: `src/angular5_enrichment_r3_arm64_run.py`
- Create: `src/angular5_enrichment_r3_arm64.py`
- Create: `scripts/enrich_angular5_mc_r3_arm64.py`
- Create: `tests/test_angular5_enrichment_r3_arm64_run.py`
- Create: `tests/test_angular5_enrichment_r3_arm64.py`
- Create: `tests/test_enrich_angular5_mc_r3_arm64_script.py`

**Interfaces:**
- Consumes: Task 4 actual identity manifest/table receipts、两个 protected MC ROOT files 和已审查的 `build_angular5` formulae。
- Produces: 对 `(source_sample, source_entry)` 的 unique/complete/one-to-one join，保留所有旧 token 并只追加五个 Angular5 columns。

- [ ] **Step 1: 写失败测试**

  覆盖 exact config/path/hash/schema、两个已知 duplicate legacy groups、canonical identity join、旧列与 identity lexical token 保留、五角顺序/range、missing/extra/duplicate identity、source mutation/swap、symlink/collision、`KeyboardInterrupt`、`SystemExit` 和 zero real-data surface。

- [ ] **Step 2: 验证 RED**

  ```bash
  .venv-arm64/bin/python -m pytest \
    tests/test_angular5_enrichment_r3_arm64_run.py \
    tests/test_angular5_enrichment_r3_arm64.py \
    tests/test_enrich_angular5_mc_r3_arm64_script.py -q
  ```

  Expected: modules/config 尚不存在导致 collection/config failure。

- [ ] **Step 3: 实现最小 enrichment**

  通过 descriptor snapshot 读取 identity CSV 和 ROOT，在 selection 前附加 canonical identity，计算冻结的五个 Angular5 observables，并只按 `("source_sample", "source_entry")` join。旧表的每个 lexical token 原样保留，只追加：

  ```text
  cos_theta_star
  cos_theta_1
  cos_theta_2
  phi_decay_planes
  phi_production_plane
  ```

  成功 artifact 必须恰好为：

  ```text
  config.yaml
  processed/mc_events_angular5.csv.gz
  artifacts/identity_validation.json
  artifacts/angular5_summary.json
  artifacts/run_manifest.json
  ```

- [ ] **Step 4: 验证 GREEN 和完整测试**

  ```bash
  .venv-arm64/bin/python -m pytest tests/test_angular5.py \
    tests/test_angular5_enrichment_r3_arm64_run.py \
    tests/test_angular5_enrichment_r3_arm64.py \
    tests/test_enrich_angular5_mc_r3_arm64_script.py -q
  .venv-arm64/bin/python -m pytest -q
  git diff --check
  ```

- [ ] **Step 5: 提交**

  ```bash
  git add config/angular5_mc_dsid363490_r3_arm64.yaml \
    src/angular5_enrichment_r3_arm64_run.py src/angular5_enrichment_r3_arm64.py \
    scripts/enrich_angular5_mc_r3_arm64.py \
    tests/test_angular5_enrichment_r3_arm64_run.py \
    tests/test_angular5_enrichment_r3_arm64.py \
    tests/test_enrich_angular5_mc_r3_arm64_script.py
  git commit -m "feat: enrich Angular5 on sealed ARM64 identities"
  ```

### Task 6: 一次性执行 enrichment 并冻结训练输入

**Files:**
- Produce once: `runs/angular5-mc-363490-2026-08-26-r3-arm64/`
- Create after success: `config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml`

**Interfaces:**
- Consumes: Task 5 reviewed command 和 Task 4 receipts。
- Produces: 199104-row Angular5 MC table 和 actual manifest/table hashes。

- [ ] **Step 1: preflight 后执行一次**

  ```bash
  git status --short
  test ! -e runs/angular5-mc-363490-2026-08-26-r3-arm64
  .venv-arm64/bin/python -m pytest -q
  .venv-arm64/bin/python -m scripts.enrich_angular5_mc_r3_arm64 \
    --config config/angular5_mc_dsid363490_r3_arm64.yaml \
    --run-dir runs/angular5-mc-363490-2026-08-26-r3-arm64
  ```

- [ ] **Step 2: 审计 enrichment**

  要求 exact five-file allowlist、`199104` rows、旧列/identity tokens 未变、canonical identity 全局唯一、两个 duplicate legacy groups/四行仍存在、五个 angle 全部 finite 且在冻结 range、complete manifest 存在、failure terminal 不存在。

- [ ] **Step 3: 冻结 actual receipts**

  ```bash
  shasum -a 256 \
    runs/angular5-mc-363490-2026-08-26-r3-arm64/artifacts/run_manifest.json \
    runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz
  ```

  将实际值写入 `config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml`。配置必须保留原 DropTop4 重加权的 11 个 mass bins、iterations `0..5`、damping/bounds、五折 OOF、seed、model candidates、AUC/KS/efficiency gates 和 conditional artifact allowlists。

- [ ] **Step 4: 提交实际 training config**

  ```bash
  git add config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml
  git commit -m "config: freeze ARM64 Angular5 training inputs"
  ```

### Task 7: 接通 exact 15-feature training profile

**Files:**
- Modify: `src/mass_bin_reweighting.py`
- Modify: `src/mass_bin_reweighting_run.py`
- Modify: `scripts/run_mass_bin_reweighting.py`
- Modify: `tests/test_mass_bin_reweighting.py`
- Modify: `tests/test_mass_bin_reweighting_run.py`
- Modify: `tests/test_run_mass_bin_reweighting_script.py`

**Interfaces:**
- Consumes: Task 6 actual config/receipts 和现有 sealed reweighting algorithm。
- Produces: profile `drop_top4_plus_angular5`，严格按以下顺序向模型提供 15 列。

  ```text
  lep1_pt
  lep2_pt
  lep1_eta
  lep2_eta
  lep3_eta
  lep4_eta
  pt4l
  deltaR_Z1
  deltaR_Z2
  deltaPhi_ZZ
  cos_theta_star
  cos_theta_1
  cos_theta_2
  phi_decay_planes
  phi_production_plane
  ```

- [ ] **Step 1: 写失败测试**

  Assert literal 15-feature tuple；明确拒绝 `m4l`、`lep3_pt`、`lep4_pt`、`mZ1`、`mZ2`、identity、labels、split 和 weights；保留历史 profiles；no-selection 分支不得访问 test，first-eligible 分支只允许一次 test evaluation。

- [ ] **Step 2: 验证 RED**

  ```bash
  .venv-arm64/bin/python -m pytest tests/test_mass_bin_reweighting.py \
    tests/test_mass_bin_reweighting_run.py \
    tests/test_run_mass_bin_reweighting_script.py -q
  ```

- [ ] **Step 3: 加入唯一的 sealed R3-ARM64 branch**

  只对 R3-ARM64 schema/path 读取 `processed/mc_events_angular5.csv.gz`。不得改变 folds、candidates、weights、bin corrections、eligibility gates、plot 内容或 legacy branches。

- [ ] **Step 4: 验证 GREEN、完整测试并提交**

  ```bash
  .venv-arm64/bin/python -m pytest tests/test_mass_bin_reweighting.py \
    tests/test_mass_bin_reweighting_run.py \
    tests/test_run_mass_bin_reweighting_script.py -q
  .venv-arm64/bin/python -m pytest -q
  git diff --check
  git add src/mass_bin_reweighting.py src/mass_bin_reweighting_run.py \
    scripts/run_mass_bin_reweighting.py tests/test_mass_bin_reweighting.py \
    tests/test_mass_bin_reweighting_run.py tests/test_run_mass_bin_reweighting_script.py
  git commit -m "feat: run sealed ARM64 Angular5 reweighting"
  ```

### Task 8: 一次性训练、终态审计与报告

**Files:**
- Produce once: `runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26-r3-arm64/`
- Create: `docs/superpowers/plans/2026-08-26-drop-top4-angular5-r3-arm64-report.md`
- Modify after actual result: `README.md`
- Modify after actual result: `docs/README.md`
- Modify after actual result: `docs/project/overview.md`
- Modify after actual result: `docs/roadmap/next-stage.md`

**Interfaces:**
- Consumes: reviewed R3-ARM64 enrichment、15-feature config 和 frozen Full14 reference run。
- Produces: immutable training terminal、完整 OOF trajectory、conditional test/model artifacts 和 evidence-backed report。

- [ ] **Step 1: final production gate**

  ```bash
  git status --short
  test ! -e runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26-r3-arm64
  .venv-arm64/bin/python -m pytest -q
  ```

  再次校验所有 historical source、identity manifest/table、enrichment manifest/table 和 training config hashes；要求 tracked tree clean。

- [ ] **Step 2: 只执行一次训练**

  ```bash
  .venv-arm64/bin/python -m scripts.run_mass_bin_reweighting \
    --input-run runs/angular5-mc-363490-2026-08-26-r3-arm64 \
    --reference-run runs/full-training-363490-2026-08-11-r2 \
    --config config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml \
    --run-dir runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26-r3-arm64
  ```

  不重跑、不增加 iteration、不换 feature、不改 bins、不降门槛，也不依据 test/data 结果修改选择。

- [ ] **Step 3: 审计终态**

  对 iterations `0..5` 逐项记录 full-precision weighted OOF AUC、loose/medium/tight KS、signal/ZZ efficiencies 和 eligibility。验证选择的是第一个合格 iteration。

  若无合格 iteration，必须满足：

  ```text
  selected_iteration: null
  test_opened: false
  no model artifact
  no test metrics/predictions
  ```

  若有合格 iteration，只允许一次 held-out MC test opening，并要求所有 conditional selected artifacts 完整。无论哪种终态，都不得读取真实数据。

- [ ] **Step 4: 写实际报告并更新导航**

  报告必须记录：ARM64/依赖环境、R2 CPU mismatch 根因、三个 production receipts、199104 rows、两个 duplicate groups/四行、所有测试结果、六轮 OOF 轨迹、test-opened 状态、与 frozen DropTop4 参考的比较、真实数据排除和方法局限。所有数字必须来自实际 artifacts，不能预估。

- [ ] **Step 5: 最终验证与提交**

  ```bash
  .venv-arm64/bin/python -m pytest -q
  git diff --check
  git add README.md docs/README.md docs/project/overview.md \
    docs/roadmap/next-stage.md \
    docs/superpowers/plans/2026-08-26-drop-top4-angular5-r3-arm64-report.md
  git commit -m "docs: report ARM64 Angular5 result"
  ```

## 4. 失败处理矩阵

| 失败位置 | 必须做 | 禁止做 |
|---|---|---|
| architecture/version preflight | 停止，重建 native ARM64 环境 | 用 Rosetta 或 3.13 继续 |
| protected input SHA mismatch | 停止，重新传输正确字节 | 更新 config hash 迁就错误文件 |
| test failure | 先按 systematic debugging 定位并修复代码 | 先跑生产命令 |
| identity production failure | 保留 R3-ARM64 failure terminal，另行设计 R4 | 删除目录、原路径重跑、自动加容差 |
| enrichment production failure | 保留失败目录，另行新 path | 修补已 claim 目录 |
| training production failure | 保留失败目录与 terminal | 重跑、加 iteration、改 gates |
| no eligible iteration | 作为正常科学终态发布 | 打开 test、真实数据或事后调参 |

## 5. 预计耗时

在数据已经传输到 ARM SSD 的前提下：

| 阶段 | 预计时间 |
|---|---:|
| 环境安装、hash 和基线测试 | 30–90 分钟 |
| R3-ARM64 identity wiring、测试与审查 | 1–2 小时 |
| identity production + audit | 10–30 分钟 |
| enrichment 实现、测试与审查 | 2–4 小时 |
| enrichment production + audit | 10–30 分钟 |
| 15-feature training wiring、测试与审查 | 1–3 小时 |
| 一次性六轮训练 + audit | 1–4 小时，取决于 Apple Silicon 型号 |
| 报告和最终完整测试 | 30–90 分钟 |

总计约一个完整工作日；数据复制时间另计。identity 成功只是恢复断点，不代表训练已经完成。

## 6. 新设备首次交接提示词

在 ARM 设备把项目根目录作为 Codex workspace 打开后，可直接发送：

```text
请先完整阅读 AGENTS.md、README.md、docs/project/overview.md、
docs/roadmap/next-stage.md，以及
docs/superpowers/plans/2026-08-26-angular5-arm64-exact-rerun.md。
确认当前进程是原生 arm64、受保护输入 SHA-256 正确、真实数据不在工作面，
然后从该计划第一个未勾选的 Task 继续。不得复用 R2 failure path，
不得引入浮点容差，不得放宽 AUC/KS 门槛或提前打开 held-out test。
```
