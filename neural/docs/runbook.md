# HiggsML Neural MC-only Runbook

## 1. 适用范围与停止原则

本手册只恢复和运行严格 MC-only 的 `higgsml-preprocess` 与 `higgsml-train`。Classifier 只消费
[`Adversarial MLP Protocol V1`](adversarial-mlp-protocol-v1.md) 固定的 15 项 features；`m4l`、identity、
provenance、split 和 weight 字段都不得作为 classifier features。

权威结果只能来自 `osx.yml` 恢复的原生 `osx-arm64` 环境。Windows/synthetic 运行只产生非权威开发
证据。任一 authority 前置缺失、hash/golden 不一致、pytest skip 或科学错误都会停止当前 run 和
M1-06 提交；不得改 protocol、门槛、候选或历史 artifact 来绕过失败。

所有命令从 `neural/` 执行。所有 run path 必须是 `runs/` 下执行前不存在的唯一新路径；失败 run
保留且不得复用。所有输出只能描述为 educational/technical demo。

## 2. 准备本地运行配置

复制示例，但不要提交实际 ROOT 绝对路径：

```bash
cp config/preprocess_run.example.yaml config/preprocess_run.local.yaml
git check-ignore config/preprocess_run.local.yaml
```

Windows PowerShell 可使用：

```powershell
Copy-Item -LiteralPath config/preprocess_run.example.yaml -Destination config/preprocess_run.local.yaml
git check-ignore config/preprocess_run.local.yaml
```

只允许填写已批准的 Higgs 345060 和 ZZ 363490 MC ROOT 路径以及 `chunk_size_events`。不得搜索、枚举、
探测或填入任何真实数据路径。程序会按 sealed preprocess protocol 核对两个 MC ROOT SHA-256。

## 3. 恢复环境

### 3.1 权威 osx-arm64

```bash
conda-lock install --name pytorch osx.yml
conda run -n pytorch python -m pip install --no-deps -e .
conda run -n pytorch python -m pip check
```

记录锁文件 hash、环境和 native 状态：

```bash
shasum -a 256 osx.yml
conda run -n pytorch python -c "import platform,sys,torch; print(platform.system()); print(platform.machine()); print(sys.version.split()[0]); print(torch.__version__); print(torch.get_num_threads()); print(torch.are_deterministic_algorithms_enabled())"
sysctl -n sysctl.proc_translated
```

必须得到 Darwin、arm64 且 translation probe 为 `0`；若 key 不存在或命令失败，原样记录并停止确认
native 状态。`run_authority_gate` 还会再次强制平台条件。

### 3.2 Windows 开发环境

```powershell
conda-lock install --name pytorch win.yml
conda run -n pytorch python -m pip install --no-deps -e .
conda run -n pytorch python -m pip check
```

Windows 结果的 `authority` 必须记录为 `false`。

## 4. Authority 执行前置

按顺序执行；首个失败即停止，后续 full-data 命令记为 `not_run`：

1. 确认 host 为原生 Darwin/arm64，并由 `osx.yml` 恢复 `pytorch`。
2. 记录 `git rev-parse HEAD`，并确认 reviewed M1-05 scientific bytes 未改变：

   ```bash
   git diff --exit-code 85b67d1 -- src config/preprocess_protocol_v1.yaml config/adversarial_mlp_protocol_v1.yaml
   git status --porcelain --untracked-files=all -- src config/preprocess_protocol_v1.yaml config/adversarial_mlp_protocol_v1.yaml
   ```

   两条命令都必须无输出且 exit 0；从 `neural/` 执行时 `src` 已包含两个 CLI module。Test 文件不属于
   runtime scientific byte freeze，但 authority comparator definition 位于被覆盖的 `src/`。

3. 只对 run config 明确列出的两个批准 MC ROOT 计算 SHA-256，并与
   [`Preprocess Protocol V1`](preprocess-protocol-v1.md) §2.1 exact 比较；禁止发现式扫描其他数据。
4. 按协议 §7.1 固定 locator/hash 确认五项：identity manifest、identity table、enrichment manifest、
   baseline manifest 和 r3-ARM64 golden table。不要接受替代 path 或未绑定 artifact。
5. 为 preprocess、authority evidence 和 development 选取三个执行前不存在的 `runs/` 子路径。将下列
   placeholders 替换为本轮同一组唯一 id，再执行 resolved containment/absence preflight：

   ```bash
   conda run -n pytorch python -c "import os; from pathlib import Path; root=(Path.cwd()/'runs').resolve(); targets=[Path('runs/preprocess-<unique-id>').resolve(),Path('runs/authority-evidence-<unique-id>/preprocess-authority.json').resolve(),Path('runs/mlp-development-<unique-id>').resolve()]; [item.relative_to(root) for item in targets]; assert all(not os.path.lexists(item) for item in targets)"
   git check-ignore runs/preprocess-<unique-id> runs/authority-evidence-<unique-id>/preprocess-authority.json runs/mlp-development-<unique-id>
   ```

   两条命令都必须 exit 0，且 Python preflight 无 traceback。现存、symlink/reparse escape、位于 root 外或
   未 ignored 的任一路径都停止执行。

任何 scientific source/protocol 差异都必须回到文档与代码评审门；不得在 authority run 中热修后继续。

## 5. 自动化与 CLI smoke

```bash
conda run -n pytorch python -m pytest -q
conda run -n pytorch higgsml-preprocess --help
conda run -n pytorch higgsml-train --help
```

Authority host 在全部外部前置可用时预期 zero skip；任一 skip 都要诊断并阻塞 closure。Focused
synthetic mechanism smoke 使用测试 fixture，不是 full-data 替代物：

```bash
conda run -n pytorch python -m pytest -q tests/integration/test_preprocess_micro_root.py tests/integration/test_development_run.py tests/integration/test_open_test_cli.py
```

## 6. Authority full-data preprocess 与 golden

为本次执行替换唯一 id；目标 path 必须尚不存在：

```bash
conda run -n pytorch higgsml-preprocess --protocol config/preprocess_protocol_v1.yaml --run-config config/preprocess_run.local.yaml --run-dir runs/preprocess-<unique-id>
```

仅在 preprocess exit 0 且单独审计其 manifest-last 布局、output size/SHA-256/canonical-content binding
后调用 application-level comparator；普通 pytest comparator/orchestration 测试不等于该 gate。
Comparator 固定从 reviewed `repository/neural/config/preprocess_protocol_v1.yaml` 读取 sealed protocol，
不接受 runtime protocol-path 注入：

```bash
conda run -n pytorch python -c "from src.preprocessing.authority import run_authority_gate; run_authority_gate(repository_root='..', new_run_dir='runs/preprocess-<unique-id>', evidence_path='runs/authority-evidence-<unique-id>/preprocess-authority.json')"
```

Comparator 必须 exit 0 并以 exclusive create 发布独立 evidence。它验证批准 lineage SHA-256、全量
read/selected/split/development/test/duplicate counts、全部 29 个 canonical columns 的 schema/order 与
逐列 r3 golden，以及 baseline-manifest-bound cutflow；精确规则以 preprocess protocol §7 为准。它不读取
新 preprocess run 的 `artifacts/manifest.json`，所以前一段的 manifest audit 是独立 gate，不能被
comparator 替代。

任何 traceback、partial evidence 或非零 exit 都是 closure blocker，必须保留 run 和已有 evidence path
并人工审计。`FileExistsError` 表示违反 fresh evidence-path preflight；不得覆盖或删除旧 evidence，也不得
把该调用记录为 pass。只有在审计确认未发生科学变更后，才可选择另一个执行前不存在的 evidence path
重跑 comparator。

## 7. 完整 development OOF

只在 authority preprocess/golden 通过后运行：

```bash
conda run -n pytorch higgsml-train develop --input-run runs/preprocess-<unique-id> --protocol config/adversarial_mlp_protocol_v1.yaml --run-dir runs/mlp-development-<unique-id>
```

审计 `artifacts/manifest.json`、`qualification.json`、两个 metric CSV 和完整 OOF：

- `no_eligible_candidate`：不得存在 `model/` 或 test artifact；
- `eligible`：必须存在封存 model/scaler，但 held-out test 仍未读取且没有自动 claim；
- 实际未发生的另一分支在 M1-06 evidence 中记为 `not_applicable`，引用 M1-04 synthetic 分支覆盖。

两种 qualification 都是合法科学终态，且都不能自动授权 `open-test`。

## 8. Test-opening 授权边界

`open-test` 不是 M1-06 closure 必需项。没有针对具体 eligible frozen development run 的另行明确用户
授权时，记录 `not_run`，不得创建 test path 或 claim。

获得单独授权后才可使用执行前不存在且 ignored 的新 path：

```bash
conda run -n pytorch higgsml-train open-test --development-run runs/mlp-development-<id> --run-dir runs/mlp-test-<unique-id> --authorization-reference <external-approval-reference>
```

Eligibility 不等于授权。Test 结论只允许 `test_reproduced` 或 `test_nonreproduction`，且不得反馈到训练、
候选、阈值或 protocol。

## 9. 证据与失败处理

把实际命令、exit code、时间、run/manifest/protocol/config SHA-256 和四字段分类转录到
[`m1-06-verification-evidence.md`](m1-06-verification-evidence.md)。未执行项使用 `not_run`，外部前置
缺失使用 `blocked`，未发生的条件分支使用 `not_applicable`；不得预填预期科学数字。

失败 run、failure receipt、claim 和 terminal receipt 都不可删除或覆盖。若 test output 已发布但
terminal receipt 失败，按 exit 4 和 manual audit 处理，绝不能报告完整成功。
