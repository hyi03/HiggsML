# Sprint M1-01 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-01-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-01-code-review-by-opencode-go-glm-5.2.md`
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/3-Plan/sprint-m1-01.md`
- M1-01 implementation and targeted tests

**Review Date**

- 2026-09-01

## Overall Conclusion

两份评审对 package/CLI 骨架、当前 protocol 转录值和基本 no-clobber 行为给出了正面证据，
但也共同证明当前实现尚不能通过 M1-01 验收。阻塞项集中在 protocol 的嵌套 fail-closed、
characterization 覆盖、protocol 内容完整性和 Windows drive-relative 路径逃逸；这些都属于
本 Sprint 已批准范围，必须在启动 M1-02 前完成。

评审中关于 `mkdir()` 本身“不原子”和 `_validate_target()` 会因 runs-root 祖先 symlink
直接逃逸的判断不成立；实际需要补的是并发证明，以及每个 artifact 目标的完整祖先链
containment/symlink 校验。低优先级的历史依赖和 package 范围问题由 M1-06 删除旧运行面解决，
本 Sprint 只记录，不扩大临时兼容层。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Correctness | Kimi H1 | 预处理 protocol 未拒绝未知嵌套字段 | Accept | FR R3、Sprint §5.2 明确要求 unknown field fail-closed；当前只校验 top-level 与 `features`。 | 为全部嵌套 mapping 定义 exact key/type/invariant 校验，并增加变异 YAML 测试。 |
| 2 | High | Correctness | Kimi H2 | XGBoost protocol 未拒绝未知/缺失嵌套字段和错误类型 | Accept | GLM 临时探针证明字符串 seed、bool 浮点、缺键和额外键均被接受。 | 校验 candidate/common/working_points/qualification 的 exact keys、类型、有限性和范围。 |
| 3 | High | Correctness | Kimi H3 | 预处理 DSID、split fraction 和 forbidden contract 未验证 | Accept | 当前 loader 除 Angular19 外不检查科学结构；当前设计固定 345060/363490 和稳定 0.6/0.2/0.2 split。 | 校验 MC-only DSID/label/profile、fraction、selection、feature lists 与 forbidden contract。 |
| 4 | High | Test | Kimi H4 | characterization 未覆盖 Sprint §5.1 的行为类别 | Accept | Sprint §5.1 明列 selection、重建、特征值、identity/split/fold、工作点、指标、资格和 round-trip。 | 在旧实现上补齐 synthetic characterization；若某项确需后置，必须在对应新代码前记录并捕获旧值。 |
| 5 | Medium | Test | Kimi M5 | protocol loader 缺少 fail-closed 变异测试 | Accept | 现有参数化只覆盖 run config。 | 为两类 protocol 增加 unknown/missing/type/non-finite/range 变异测试。 |
| 6 | Medium | Test | Kimi M6 | CLI 只测试 `--help` | Accept | FR 最小验证和 Sprint §7 同时要求错误路径 smoke。 | 增加缺参、未知参数、缺 subcommand、skeleton 业务调用和已安装 entry-point 元数据/命令测试。 |
| 7 | Medium | Test | Kimi M7 | artifact 缺并发、symlink、发布后写入和失败 no-clobber 测试 | Accept | Sprint §5.3 明确要求成功/失败/并发占用与 symlink 拒绝。 | 增加并发唯一赢家、发布后拒写、post-publish 异常、fake/native symlink 分支测试。 |
| 8 | Medium | Correctness | Kimi M8 | `mkdir()` 不是原子 claim | Reject | 单目录 `os.mkdir`/`Path.mkdir(exist_ok=False)` 是 OS 原子创建；竞态只有一个成功，另一方 `FileExistsError`。GLM 也独立否定该缺陷判断。 | 不引入额外 lock；用并发测试证明现有原语的一胜一败语义。 |
| 9 | Medium | Security | Kimi M9 | runs-root 祖先 symlink 经 `resolve()` 可使 claim 逃逸 | Reject | `runs_root` 和 `run_dir.parent` 同时 resolve 后要求相等，祖先 symlink 不会让 target 离开 resolved root；runs_root 自身 symlink 已拒绝。 | 不改 claim 判定；另行采纳 GLM M5，对 artifact 的中间祖先 symlink 做完整 containment 校验。 |
| 10 | Medium | Correctness | Kimi M10 | 工作点顺序和资格范围未校验 | Accept | legacy `experiment_config.py` 已执行该约束，等价 loader 不能更宽松。 | 强制 loose > medium > tight、效率/门槛处于合法范围并增加边界测试。 |
| 11 | Low | Clarity | Kimi L11 | skeleton `main() -> int` 实际总是 `SystemExit` | Accept | 标注与当前控制流不符。 | M1-01 改为 `NoReturn`；M1-02/M1-03 落地真实入口时恢复 `int` 返回。 |
| 12 | Low | Maintainability | Kimi L12 | `include = ["src*"]` 过宽 | Accept | 当前模式可能匹配未来无关顶层包。 | 改为显式 `include = ["src", "src.*"]`，仍保留当前历史模块直至 M1-06。 |
| 13 | Low | Maintainability | Kimi L13 | golden tests 引用 M1-06 将删除的历史模块 | Accept | characterization 当前必须以旧实现为 authority，但删除前必须迁移契约。 | M1-06 删除旧模块前，把这些契约切到新 domain/训练实现并保留冻结期望值。 |
| 14 | Low | Test | Kimi L14 | 未断言完整 common/working-points | Accept | Sprint §5.2 要求逐项对应，当前只断言 folds。 | 增加完整 mapping 和预处理 authority 对应断言。 |
| 15 | Low | Consistency | Kimi L15 | example 的 ZZ 路径与 AGENTS 通用说明不同 | Reject | `config/dsid363490.yaml` 的实际权威路径就是 `zz_363490.root`；example 已与当前 DSID-specific authority 一致。 | 不加入会暗示双重 authority 的注释；M1-05 统一用户文档时只保留新 CLI 示例。 |
| 16 | Info | Risk | Kimi I16 | Windows 完整测试有 211 个历史失败 | Accept | 两次评审均复现 211 failures；原因包含 POSIX-only API/symlink 权限和 worktree 不含冻结 run。 | 在 Sprint 交付结论记录 baseline、failure boundary 与未验证 POSIX gate，不把它描述为全绿。 |
| 17 | High | Correctness | GLM H1 | 13 种 malformed protocol 均被实测接受 | Accept | 这是 No.1-3/10 的更强运行证据，且证明 bool/string 会绕过有限性检查。 | 以 exact schema helpers 修复，并将 13 类失败条件转成参数化测试。 |
| 18 | High | Test | GLM H2 | fold 只比较实现自身，且大量 baseline 未分配 | Accept | 当前测试计算了独立 hash 值却没有直接断言，无法检测确定但错误的 fold 算法。 | 直接断言 blake2b fold 值；补 event split/identity、selection/reconstruction/feature、metrics/qualification/round-trip baseline。 |
| 19 | High | Test | GLM H3 | protocol-vs-authority 断言不完整 | Accept | 当前 checked-in 值正确，但缺少持续检测门。 | 对 full common、working points、selection、normalization、split 和 gate 做 exact assertions。 |
| 20 | High | Requirement | GLM H4 | 预处理 protocol 缺 units/tree/weights/identity/split algorithm，且错误标注 split seed | Accept | 设计 §7.1 要求这些内容；`src/split.py` 的 blake2b split 无 seed。 | 在 protocol v1 首次被消费前补齐契约，删除 `splitting.random_seed`，明确 hash payload/digest/endianness/buckets。 |
| 21 | High | Security | GLM H5 | Windows `C:evil` drive-relative 路径可逃逸 run | Accept | 临时探针证明 `PurePath("C:evil")` 非 absolute，跨 drive join 会替换 base。 | 拒绝非空 `drive`，并在所有 artifact open 前做 resolved containment/ancestor-symlink 检查；增加 Windows path tests。 |
| 22 | Medium | Test | GLM M1 | Windows symlink 拒绝策略未覆盖 | Partial | 风险和缺测成立；为测试专门扩展生产构造参数不是最小修复。 | 使用 monkeypatch/fake Path branch 覆盖拒绝逻辑，能创建 symlink 时运行 native test，否则显式 skip 并记录 WinError 1314。 |
| 23 | Medium | Correctness | GLM M2 | manifest 后仍可写；异常会同时产生 success/failure terminal | Accept | 违反 design §11 的 manifest 终态与失败 run 无 success manifest 契约。 | `_published` 后拒绝任何写入；已发布后异常只传播、不再创建 failure receipt；测试 manifest-last 与互斥终态。 |
| 24 | Medium | Test | GLM M3 | CLI 错误路径未自动化 | Accept | 与 No.6 一致，但补充了已实测 exit 2/1 证据。 | 合并到 CLI smoke 扩展。 |
| 25 | Medium | Test | GLM M4 | 缺 concurrent claim 测试 | Accept | Sprint §5.3 明确要求，且此测试也能关闭 Kimi M8 的争议。 | 两线程同时 claim，同步起跑，断言仅一个成功且 loser 不写 receipt。 |
| 26 | Medium | Security | GLM M5 | 中间祖先 symlink 与 manifest path 未完整防御 | Accept | 当前只检查 destination 和 immediate parent，`publish_manifest` 没有同等检查。 | 抽取统一安全目标解析，在 write/manifest/failure 路径复用；要求 resolved target 位于 resolved run_dir。 |
| 27 | Medium | Documentation | GLM M6 | 缺环境与迁移前 baseline 记录 | Accept | Sprint §5.0/§6 是明确验收项。 | 在 Sprint 交付结论写入 worktree/branch/base/Python/OS、16 focused pass、721/211 baseline 与当前增量结果。 |
| 28 | Low | Maintainability | GLM L1 | `pyproject.toml` 未含 legacy-only `hep_ml` | Partial | 当前新 CLI 不消费 `hep_ml`；用户已批准 M1-06 完全删除历史运行面，但 `src*` 暂时仍会打包旧模块。 | 不为短生命周期旧入口扩大新 package 依赖；记录安装/测试仍以 `requirements.txt` 为完整迁移环境，M1-06 删除 legacy import。 |
| 29 | Low | Test | GLM L2 | run config 失败覆盖不全且 example 未加载 | Accept | shipped example 和 required-field/type/bool 边界属于严格 loader 的基本契约。 | 增加 missing/empty/bool/non-positive/non-integer 案例及 example happy path。 |
| 30 | Low | Clarity | GLM L3 | CLI 返回标注错误 | Accept | 与 No.11 相同。 | 合并到 No.11。 |
| 31 | Low | Consistency | GLM L4 | 空 `tests/fixtures/` 不会被 Git 保存 | Accept | 目录在批准结构和 Sprint scope 中。 | 添加 `tests/fixtures/.gitkeep`。 |
| 32 | Low | Consistency | GLM L5 | 新 protocol forbidden list 与 legacy set 无映射 | Partial | 新 protocol 列的是新 artifact schema 中的 identity/provenance/weight 禁止列；legacy raw normalization 字段不应无说明地混入新输出契约。 | 校验新 forbidden list 的 exact frozen 值，并在 protocol 注释/文档说明它是新 schema 契约；legacy set 继续由 characterization 锁定。 |
| 33 | Info | Maintainability | GLM I1 | 当前 distribution 仍包含历史 flat modules | Accept | M1-01 为读取旧 authority 暂时保留，M1-06 才执行完全删除。 | 在 Sprint 记录 staging decision，M1-06 缩减 package surface。 |
| 34 | Info | Risk | GLM I2 | venv 无 setuptools，`--no-build-isolation` 重装失败 | Accept | 实测现有 editable install 可用，但无隔离重装缺 backend。 | 记录环境限制；正式验证使用正常 `pip install -e .`，不把 `--no-build-isolation` 作为验收命令。 |
| 35 | Info | Documentation | GLM I3 | 治理更新正确保存冻结边界 | Accept | `AGENTS.md` 与 roadmap 明确本次只做科学行为等价工程重构。 | M1-01 无额外动作；M1-05 按已确认范围清理旧命令与用户文档。 |

## Needs Immediate Action

- 完成 protocol 全层 exact schema/type/invariant 校验和变异测试。
- 补齐 preprocessing protocol 的 units、ROOT profile、weight、identity 与 seedless split 契约。
- 扩展 characterization 至 Sprint §5.1 行为类别，至少先锁定所有 M1-02 将迁移的行为。
- 修复 Windows drive-relative/中间 symlink 逃逸、manifest-last 和终态互斥。
- 增加 CLI error、artifact concurrency/symlink/post-publish、protocol authority 和 example 测试。
- 写入 Windows baseline、环境、无真实数据/冻结 run 访问和 POSIX 未验证门。

## Can Be Deferred

- Golden imports 从历史模块迁到新实现：最迟 M1-06 删除旧模块前完成。
- `hep_ml` 和当前 `src*` 历史打包面：维持迁移期记录，M1-06 随历史运行面一并删除。
- WSL/POSIX 原生验证：当前环境缺 Python venv/pip，作为平台验证缺口保留，不以 Windows
  静态或 synthetic 结果替代 ARM64 exact authority。

## Final Status

**暂不接受 M1-01 实现。** 完成上述 immediate actions、重新运行专项验证并证明完整测试
失败集合不扩大后，方可接受、填写交付结论、提交并启动 M1-02。
