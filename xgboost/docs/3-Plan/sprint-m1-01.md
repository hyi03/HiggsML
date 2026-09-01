# Sprint M1-01

## 1. Sprint 目标

覆盖 [FR-001](../1-Requirement/FR-001-angular19-xgboost-refactor.md)，建立可验证的旧行为
基线、新 package 骨架、冻结 protocol 和统一 artifact 事务，为后续迁移提供安全边界。

核心目标：

- 在不改变生产科学行为的前提下，先锁定关键 characterization/golden 契约。
- 建立 `pyproject.toml`、目标目录、两个 CLI 骨架和 protocol schema。
- 建立统一 run transaction、manifest 与哈希基础设施。

## 2. 前置依赖

- [批准设计](../superpowers/specs/2026-09-01-xgboost-refactor-design.md)
- 当前测试与现有通用 XGBoost CLI 行为

协同说明：本 Sprint 不迁移完整预处理或训练，只建立可供后续 Sprint 复用的骨架。

## 3. 纳入范围

- `pyproject.toml`
- `config/preprocessing_protocol_v1.yaml`
- `config/preprocessing_run.example.yaml`
- `config/xgboost_protocol_v1.yaml`
- `src/cli/`、`src/config.py`、`src/artifacts/`
- `tests/unit/`、`tests/integration/`、`tests/golden/`、`tests/fixtures/`
- characterization、protocol、artifact、CLI 基础测试
- `docs/1-Requirement`、`docs/3-Plan`、`docs/4-Reviews`

## 4. 暂不纳入范围

- 完整 ROOT 预处理、XGBoost develop、open-test、历史删除。

原因：先建立行为和产物边界，再迁移功能。

## 5. 工作范围

### 5.0 环境与旧实现基线

目标：在写新实现前记录可复核的执行边界。

实现任务清单：

- [x] 记录 worktree、分支、HEAD、Git 状态、Python/依赖版本和操作系统/CPU。
- [x] 记录本 worktree 不包含权威 ROOT、冻结 run；在 worktree 新建隔离 `.venv`。
- [x] 使用 worktree `.venv` 运行并保存迁移前完整 `pytest` 基线。

测试要求：

- [x] 基线命令、退出码、通过/失败/跳过数和缺失验证门写入本 Sprint 交付结论。
- [x] 明确记录没有读取真实数据，也没有修改冻结 run。

### 5.1 行为基线

目标：在迁移前锁定设计 §13.1 的现有科学行为，并预注册数值政策。

实现任务清单：

- [x] 增加不改变生产代码的 characterization/golden tests，覆盖 selection/cutflow、
  SFOS/Z1/Z2/四动量、Base14/Angular5、权重、identity/split/fold、工作点、指标、
  qualification、模型保存/加载/预测和最终树数。
- [x] 固定数值精度政策：整数、identity、split、fold、schema、列序和终态精确相等；
  同一 Windows/Python/依赖环境中直接迁移的 domain 值要求精确相等；XGBoost OOF、指标、
  序列化 round-trip 与预测预注册为 `rtol=1e-12, atol=1e-12`。
- [x] 声明 Windows old/new 比较只证明同平台等价，不能替代现有 ARM64 exact 权威证据。
- [x] 固定禁止字段契约。

测试要求：

- [x] 基线测试在旧实现上通过；若某类只能在后续 Sprint 构造，必须在写对应新实现前先
  捕获旧实现输出和政策。

### 5.2 工程与 protocol 骨架

目标：建立直接位于 `src/` 的分层结构和严格 protocol loader。

实现任务清单：

- [x] 添加 package metadata 与两个 console scripts。
- [x] 添加三个配置样例和严格 schema/dataclass。
- [x] CLI 只暴露批准参数，业务入口暂以明确的未实现错误结束。
- [x] 显式配置 `src`/`src.*` package discovery，并为两个 CLI 增加 `__main__` guard。

测试要求：

- [x] `--help` 通过；unknown schema/field、YAML duplicate key、错误类型、非有限值和
  非法覆盖全部拒绝。
- [x] Protocol V1 与现有权威逐项对应：19 特征顺序、单候选/公共参数、fold、工作点和
  AUC/KS/效率门槛。

### 5.3 Artifact 基础设施

目标：统一 no-clobber run、哈希、canonical JSON 和失败收据。

实现任务清单：

- [x] 实现路径约束、原子 claim、成功 manifest 与失败 receipt。
- [x] 覆盖 symlink、路径逃逸和已有目录；输入替换检测由读取实际输入的 M1-02/M1-03
  source-binding 测试承接。Windows 无 symlink 权限时跳过原生
  集成项，但通过可注入 path resolver 单测覆盖拒绝分支并记录限制。

测试要求：

- [x] 事务成功/失败/并发占用测试通过。

## 6. 验收标准

- 目标骨架可安装，两个 CLI `--help` 可运行。
- Protocol V1 精确包含 Angular19 和冻结 XGBoost 参数。
- Artifact 事务不覆盖、不逃逸，失败不产生成功 manifest。
- 新增 characterization tests 证明旧行为基线。
- 已记录环境、迁移前完整测试基线、未读取真实数据且未修改冻结 run。

## 7. 验证要求

项目声明的验证命令：

- `python -m pytest -q`

专项验证：

- `python -m pytest -q tests/golden/test_refactor_characterization.py tests/unit/test_refactor_config.py tests/unit/test_refactor_artifacts.py tests/integration/test_refactor_cli.py`
- `python -m pip install -e .`
- `higgsml-preprocess --help`
- `higgsml-xgboost --help`
- `python -m src.cli.preprocess --help`
- `python -m src.cli.xgboost --help`

## 8. 实施顺序

1. 写 characterization tests。
2. 添加结构和 protocol loader。
3. 添加 CLI 骨架。
4. 添加 artifact transaction。
5. 运行专项和完整验证。

## 9. 风险控制

- 不移动现有科学函数，避免本 Sprint 混入行为改变。
- 新模块使用独立命名空间，后续 Sprint 再切换入口。
- 不读取任何真实数据或冻结 run。

## 10. 交付结论

### 10.1 评审证据

- 文档评审：
  - `docs/4-Reviews/sprint-m1-01-review-by-opencode-go-kimi-k2.7-code.md`
  - `docs/4-Reviews/sprint-m1-01-review-by-opencode-go-glm-5.2.md`
  - `docs/4-Reviews/sprint-m1-01-review-confirm.md`
- 代码评审：
  - `docs/4-Reviews/sprint-m1-01-code-review-by-opencode-go-kimi-k2.7-code.md`
  - `docs/4-Reviews/sprint-m1-01-code-review-by-opencode-go-glm-5.2.md`
  - `docs/4-Reviews/sprint-m1-01-code-review-confirm.md`
- 确认结果：35 条代码评审意见均逐条裁决；所有 Accept/Partial 的 M1-01 即时动作已应用，
  迁移期依赖/package surface 和 golden authority 切换明确由 M1-06 收口。

### 10.2 环境与基线

- worktree：`D:\code\HiggsML-worktrees\xgboost-refactor`
- branch：`codex/xgboost-refactor`
- base HEAD：`7f7f19f10a61de04cfcfc9888658e9f8ac107820`
- Python：3.12.13，Windows 10.0.19045 AMD64，Intel64 Family 6 Model 165。
- 关键版本：numpy 2.5.2、pandas 3.0.5、xgboost 3.4.1、scikit-learn 1.9.0、
  uproot 5.7.6、PyYAML 6.0.3、pytest 9.1.1。
- 迁移前完整基线：`721 passed, 211 failed, 1 skipped`；M1-01 首轮骨架为
  `737 passed, 211 failed, 1 skipped`。
- 本 worktree 不含权威 ROOT 或冻结 run；本 Sprint 未读取任何真实数据、未执行真实规模
  训练、未开启 held-out test，也未修改/复用任何冻结 run。

### 10.3 最终验证

- 专项：
  `.venv\Scripts\python.exe -m pytest -q tests/golden/test_refactor_characterization.py tests/unit/test_refactor_config.py tests/unit/test_refactor_artifacts.py tests/integration/test_refactor_cli.py`
  → exit 0，`55 passed, 1 skipped`。
- 完整：`.venv\Scripts\python.exe -m pytest -q`
  → exit 1，`776 passed, 211 failed, 2 skipped, 5 warnings`；失败数和失败集合未扩大。
- 历史 211 failures 的主要边界：POSIX-only `os.O_DIRECTORY`、Windows symlink 权限
  `WinError 1314`、以及 worktree 不携带冻结 run。它们不涉及新 M1-01 文件。
- Editable install：`.venv\Scripts\python.exe -m pip install -e .` → exit 0。
- 依赖检查：`.venv\Scripts\python.exe -m pip check` → `No broken requirements found`。
- Console/module `--help` 四项均 exit 0；CLI 错误路径已由集成测试覆盖。
- `git diff --check` → exit 0。

### 10.4 缺失门与剩余风险

- 原生 Windows symlink 创建因权限不足跳过 1 项；fake-path 分支测试已证明拒绝逻辑。
- WSL 缺少 `python3-venv`/pip，未执行 POSIX 原生回归；Windows old/new 证据不能替代
  ARM64 exact 权威证据。
- `requirements.txt` 仍是迁移期完整历史测试环境；新 `pyproject.toml` 不扩张 legacy-only
  `hep_ml` 依赖，M1-06 删除相应旧模块。
- Sprint commit 使用精确消息
  `feat: complete sprint-m1-01 code and change base on reviews`；实际 hash 由 Git 历史、
  M1-02 前置依赖记录和最终交付汇总给出，避免在同一 commit 内容中自引用不可固定 hash。

**交付结论：接受 M1-01。** 多 Sprint 共用 FR 在 M1-06 完成前保持 active；本 Sprint
commit 创建后可启动 M1-02。
