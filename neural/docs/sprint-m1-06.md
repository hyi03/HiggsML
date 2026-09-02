# Sprint M1-06

## 1. Sprint 目标

完成 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的全链复现、验证证据与用户文档收尾：在锁定 ARM64 环境中验证从 ROOT 到 development 资格结论的完整主线，并明确记录 test-opening 的授权边界与最终技术结论。

核心目标：

- 用完整 pytest、CLI smoke、全量预处理 golden、development OOF 和 manifest 审计证明交付边界。
- 让新环境可凭 README、Conda lock、两个 MC ROOT 和配置从零恢复。

## 2. 前置依赖

- Sprint M1-01 至 M1-05 均已完成评审确认和代码验证。
- 权威 `osx-arm64` 主机、锁定 Conda 环境和两个只读 MC ROOT 可用。
- [`FR-001`](FR-001-adversarial-mlp-refactor.md) 全部需求。

协同说明：

- Development OOF 是本 Sprint 的验证范围；`open-test` 仍只在 eligible 且用户另行明确授权时执行。
- Preflight note（2026-09-02）：当前执行主机确认为 Windows/AMD64，只能完成本地开发验证和文档准备；它不能
  执行或替代 locked native `osx-arm64` 权威 gate。若权威主机、两个 MC ROOT 或 r3-ARM64
  golden table 不可用，Sprint 必须停在对应 authority phase，不得把 M1-06 标记完成或提交。
- Owner acceptance override（2026-09-02）：用户在查看上述阻塞与本地证据后明确要求“不要求 test，
  完成 M1-06，并提交”。该决定豁免剩余 authority/full-data/test 项作为本 Sprint 的 closure/commit
  gate，但不把任何 `blocked`/`not_run` 变成 `passed`，也不授权 `open-test`。

绑定引用（唯一规范来源仍是 [`Preprocess Protocol V1`](preprocess-protocol-v1.md) §7.1/§7.2
与 `config/preprocess_protocol_v1.yaml`）：

| 项目 | SHA-256 |
|---|---|
| Higgs 345060 MC ROOT | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| ZZ 363490 MC ROOT | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |
| identity manifest | `74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0` |
| identity table | `a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94` |
| enrichment manifest | `ab5e283f4b6a2038a100a2a9d4e6745cccc3ee7f400ef056bcd05d3c22f28ad5` |
| baseline manifest | `10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` |
| r3-ARM64 golden table | `bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09` |

训练规则由 `config/adversarial_mlp_protocol_v1.yaml` 与
[`Development Protocol V1`](development-protocol-v1.md) 冻结。`osx.yml` SHA-256 必须在 authority
执行时从实际 reviewed file 计算并转录，不在计划中手工预填。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：全链恢复、权威 MC 验证、审计、文档与最终技术报告

涉及包和目录：

- `neural/README.md`、`neural/docs/`
- 新建 `neural/docs/runbook.md`
- 新建 `neural/docs/artifact-schema.md`
- 新建 `neural/docs/m1-06-verification-evidence.md`
- 新建 `neural/docs/final-technical-report.md`
- `neural/config/`、`neural/tests/`
- 新建且唯一的权威 preprocess/development run paths（保持 ignored，不提交产物）
- 全部源码与 artifact schema 的最终一致性检查

## 4. 暂不纳入范围

- 在无另行授权时执行权威 `open-test`。
- 真实数据、系统误差、控制区、sideband 或 likelihood。
- 因 development 不合格而改变模型、lambda、门槛或 protocol。
- 将 run、ROOT、模型、图、cache 或环境提交到 Git。

原因：

- 这些边界由 FR 的科学安全与仓库变更纪律明确禁止或延期。

## 5. 工作范围

### 5.1 工作包：环境与自动化回归

目标：

- 证明锁定环境可恢复、源码测试与 CLI 主线一致。

实现任务清单：

- [ ] 从权威 `osx.yml` 创建/验证 `pytorch`；Windows 开发验证使用 `win.yml`。
- [ ] 运行 `pip check`、完整 pytest、两个 console program 的 help smoke、synthetic mechanism
  smoke 和 authority preprocess/develop 主线。
- [x] 以固定 source/config audit 证明运行时代码没有导入/调用 `xgboost/src`，也没有已知真实数据
  locator/DSID；合法引用仅限 protocol 中五个批准的 MC lineage path，以及私有 run config 提供且
  由两个批准 SHA-256 绑定的 MC ROOT。
- [ ] 在 authority evidence 中记录 `osx.yml` SHA-256、Darwin/arm64/native translation 状态、
  Python/PyTorch/CPU threads/deterministic flags 和命令 exit code。

测试要求：

- [x] Windows full suite 的 skip 逐项记录；authority host 在所有前置满足时预期 zero skip，任一
  skip 都是 diagnosis trigger 和 closure blocker。
- [x] 环境、平台和 deterministic 设置写入证据；当前仅有 Windows/AMD64 非权威记录，authority
  environment 项明确为 `blocked`。
- [x] Synthetic mechanism smoke 与 authority full-data preprocess/develop 分开记录；前者不得充当
  后者，两个 `--help` smoke 也不得替代任一 data-path gate。

### 5.2 工作包：权威全量预处理与 development

目标：

- 在新唯一 run path 上生成可审计的全量 MC 证据和资格结论。

实现任务清单：

- [ ] 验证 ROOT SHA-256 后运行全量 preprocess。
- [ ] 通过 `run_authority_gate` 核验协议 §7.2 的完整预注册集合：read
  `419,943/554,279/974,222`、selected `187,128/11,976/199,104`、split totals
  `119,676/39,719/39,709`、development `159,395`、legacy duplicate groups/rows `2/4`、
  全部 29 个 canonical columns（其中 19 个 model-candidate features）的 schema/order/provenance、逐列
  r3 golden 与 baseline-manifest-bound cutflow。
- [ ] 独立审计新 preprocess run 的 manifest-last 布局、output size/SHA-256 和 canonical-content binding；
  `run_authority_gate` 不读取新 run manifest，不能替代该项。
- [ ] 运行完整五候选五折 development OOF。
- [ ] 审计 OOF 完整性、指标、资格、模型有无和 test 未读状态。
- [ ] 权威运行只使用新建且不存在的 ignored run paths；记录 run path、manifest SHA-256、
  protocol/config SHA-256、开始/结束时间和 exit code。失败 run 不删除、不复用。

测试要求：

- [ ] 按 authority development 实际终态验证对应分支：`no_eligible_candidate` 必须无模型/无 test
  artifact；`eligible` 必须有封存模型但 test 仍未读且未自动 claim。未发生分支记录
  `not_applicable`，并引用 M1-04 synthetic 双分支覆盖，不阻塞 closure。
- [ ] `tests/golden/test_preprocess_authority.py` 只证明 contract/comparator；它通过仍不足以 closure。
  必须在 locked native host 显式调用 `run_authority_gate`，成功发布独立 immutable evidence；
  `authoritative_gate_not_run` 在 authority closure 中是阻塞而非通过。

### 5.3 工作包：文档与最终报告

目标：

- 提供从零恢复、运行、审计和解释终态所需的自包含文档。

实现任务清单：

- [x] 完成 README、配置说明、运行手册和 artifact schema。
- [x] 记录验证命令、结果、环境、run 标识、哈希和未完成边界。
- [x] 生成最终技术报告，使用教育/技术演示措辞。
- [x] 若 development eligible，仅记录可申请 test-opening，不把资格等同于授权；本轮 authority
  development 未运行，因此该条件分支为 `not_applicable`。
- [x] `m1-06-verification-evidence.md` 只转录实际命令和 artifact；未执行项标记
  `not_run`/`blocked`/`not_applicable`，不得写预期数字冒充结果。
- [x] 最终技术报告至少包含：scope 与 educational/technical-demo 定位、sealed protocol 方法引用、
  authority 对 Windows/synthetic 的证据边界、仅来自实际 artifact 的数字、qualification 终态、
  eligibility 不等于授权、test-opening 状态、blocked gates，以及“不构成 ATLAS 结果、Higgs
  discovery 或 physics measurement”的明确 non-claims。

测试要求：

- [x] 逐条执行或静态核对本机可安全执行的文档命令和路径；authority/full-data 命令因 host gate
  阻塞而保持 `not_run`。
- [x] 文档数字只能引用实际 run artifact，不手工臆测更新。
- [x] README/runbook 中的 authority 命令使用本机私有、禁止提交的
  `config/preprocess_run.local.yaml`；该路径由 `.gitignore` 精确排除并以 `git check-ignore` 验证，
  示例文件不得包含实际 ROOT 绝对路径。

## 6. 验收标准

- 锁定 ARM64 环境恢复、`pip check`、完整 pytest 与 CLI smoke 有可追踪证据。
- `run_authority_gate` 对批准 lineage、完整 counts/duplicates、baseline-bound cutflow 和全部 29 个
  canonical columns（其中 19 个 model-candidate features）的逐列 r3-ARM64 golden 全部通过，独立 gate
  evidence 已发布并转录。
- 新 preprocess run 的 manifest-last 布局、output size/SHA-256 和 canonical-content binding 已独立审计；
  不把 comparator 描述成该 manifest audit 的替代物。
- 五候选五折 OOF 完整发布，资格结论严格来自冻结规则。
- Authority 实际发生的 qualification 分支符合冻结规则；另一分支有 M1-04 synthetic coverage，
  两种合法结论均不会自动访问 test。
- README 足以在具备两个 ROOT 时从零恢复主线。
- `xgboost/`、冻结 runs 和用户既有修改均未被覆盖。
- `m1-06-verification-evidence.md` 的每条记录包含下表四个正交字段；required authority environment、
  automated、preprocess/golden 和 development 项全部通过后才能关闭 Sprint。`test_opening` 不是
  M1-06 必需 closure gate，未授权时必须保持 `not_run`。

| 字段 | 允许值 |
|---|---|
| `method` | `static`、`automated`、`preprocess`、`development`、`test_opening` |
| `platform` | `windows-amd64`、`osx-arm64`、`not_applicable` |
| `data_scope` | `source_only`、`synthetic_mc`、`full_mc`、`held_out_mc` |
| `authority` | `true`、`false` |

## 7. 验证要求

项目声明的验证命令：

- 权威平台：`conda-lock install --name pytorch osx.yml`
- Windows 开发平台：`conda-lock install --name pytorch win.yml`
- `conda run -n pytorch python -m pip check`
- `conda run -n pytorch python -m pytest -q`
- `conda run -n pytorch higgsml-preprocess --help`
- `conda run -n pytorch higgsml-train --help`

专项验证：

- `conda run -n pytorch higgsml-preprocess --protocol config/preprocess_protocol_v1.yaml --run-config config/preprocess_run.local.yaml --run-dir runs/preprocess-<unique-id>`
- `conda run -n pytorch higgsml-train develop --input-run runs/preprocess-<id> --protocol config/adversarial_mlp_protocol_v1.yaml --run-dir runs/mlp-development-<unique-id>`
- 在全量 preprocess 完成后，从 `neural/` 显式执行 authority comparator（pytest module 本身不足）：

```bash
conda run -n pytorch python -c "from src.preprocessing.authority import run_authority_gate; run_authority_gate(repository_root='..', new_run_dir='runs/preprocess-<id>', evidence_path='runs/authority-evidence-<unique-id>/preprocess-authority.json')"
```

- `open-test` 命令只有在 eligible 且用户另行明确授权后才加入本 Sprint 的实际验证记录。

权威执行前置与证据门：

- host 必须实际为 Darwin/arm64，记录 Python `platform.system()`/`platform.machine()` 与
  `sysctl -n sysctl.proc_translated`（`0` 表示 native；probe 不存在或失败也原样记录），且 gate 再次
  强制 authority platform；
- `osx.yml` 创建的 `pytorch` 环境、两个 MC ROOT 和批准的 r3-ARM64 golden table 均可用；
- ROOT SHA-256 只能与 protocol 中两个 MC hash 比较，不得发现或探测真实数据路径；
- authority preprocess/development 均使用全新唯一 run path，且路径在 `neural/runs/` 下并被 Git
  ignore；
- authority comparator evidence 使用独立、全新、尚不存在的
  `neural/runs/authority-evidence-<unique-id>/preprocess-authority.json`，不得写回已发布 preprocess
  run；
- authority 执行前记录 `git rev-parse HEAD`，并验证 `neural/src`、
  `config/preprocess_protocol_v1.yaml`、`config/adversarial_mlp_protocol_v1.yaml` 相对已评审 M1-05
  commit `85b67d1` byte-identical，同时以 scoped `git status --porcelain --untracked-files=all` 确认这些
  path 下没有 untracked 文件。`src` 已包含两个 CLI module；golden tests 不属于 runtime scientific
  byte freeze。任何差异或执行中发现的科学修改都停止并重新评审，不得热修后继续同一 run；
- 若 `open-test` 获得针对具体 eligible run 的另行授权，其 output 也必须是 `neural/runs/` 下
  ignored、全新、唯一、执行前不存在的 path，并记录 receipt 与 exit code；无授权时不创建；
- 任一前置缺失即在 `m1-06-verification-evidence.md` 记录 phase/reason，停止后续 authority
  命令和 Sprint 提交。

## 8. 实施顺序

1. 在权威平台重建环境并完成自动化回归。
2. 验证输入哈希并运行全量预处理。
3. 审计 preprocess artifact 后运行 development OOF。
4. 审计资格、模型有无和 test 未读状态。
5. 更新 README、schema、运行手册与最终报告。
6. 仅在另行授权时执行一次 `open-test`；否则以未开启边界收尾。

本地 Windows 可先完成静态审计、synthetic tests、文档和模板，但第 1 至 4 步的 authority
evidence 不得由本地结果勾选。若 authority gate 阻塞，M1-06 保持未提交，后续 Sprint 为空。

## 9. 风险控制

- 全量运行耗时或资源不足时保留失败收据和已完成证据，不以小样本结果替代权威结论。
- 任何 golden 差异、OOF 不完整或 deterministic 偏差都先诊断，禁止改门槛或重写历史 artifact。
- 每条证据使用 §6 的 `method × platform × data_scope × authority` 字段，不用单一混合标签替代。
- 固定静态审计命令至少覆盖：
  `rg -n "xgboost[.\\/]+src|(from|import)\\s+xgboost|full-baseline-2026-08-10|700600" src config`；
  任一命中先逐项判断，禁止 runtime import/call 或真实数据 locator，批准 MC lineage 只以 protocol
  exact 值为准。

## 10. 交付结论

M1-06 的文档交付、代码双模型评审/确认和本地 Windows/AMD64 非权威验证已完成。实际本地证据为
focused synthetic `23 passed`、authority orchestration contract `4 passed, 1 skipped`、最终完整 suite
`228 passed, 2 skipped`、`pip check`、两个 CLI help、scientific byte freeze、
静态禁止引用、两个 console entry point、local config ignore 与 `git diff --check` 均通过。两个 skip
逐项确认为外部 r3-ARM64 table 缺失与 Windows directory symlink 不可用。

技术执行停止于 `authority_environment_preflight`：当前 host 是 Windows/AMD64，不是 locked native
`osx-arm64`。因此 authority environment restore/zero-skip pytest、full-data preprocess、独立
`run_authority_gate` evidence、完整五候选五折 development OOF 和实际 qualification 均为
`blocked`/`not_run`。本轮未读取或 hash 两个 MC ROOT，未生成任何 full-data run。

用户未针对具体 eligible frozen development run 另行授权 `open-test`；权威 held-out test 保持
`not_run`，且未创建 test claim/path。未读取、哈希、探测、预处理、评分、绘图或发布真实数据。
Windows/synthetic 结果不替代 authority gate。用户于 2026-09-02 明确接受上述未验证边界，并豁免
remaining authority/full-data/test gates 后要求完成和提交；因此 M1-06 以“交付完成、authority 未验证”
关闭。所有结果仅为 educational/technical demo，不构成 ATLAS 结果、Higgs discovery 或 physics
measurement。
