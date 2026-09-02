# Sprint M1-02 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-02-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-02-code-review-by-opencode-go-glm-5.2.md`
- `docs/4-Reviews/sprint-m1-02-review-confirm.md`
- `docs/3-Plan/sprint-m1-02.md`
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `AGENTS.md`
- M1-02 implementation and targeted tests

**Review Date**

- 2026-09-02

## Overall Conclusion

两份代码评审均未发现 Critical/High 科学正确性问题，并以专项测试、旧 domain 回归和
完整失败集合逐项对比证明当前迁移没有改变 selection、权重、split 或 Angular19 数学。
实现可以在应用下表 Accept/Partial 动作并重跑验证后接受；当前还不能直接提交。

即时修正集中在 import graph、代码/软件/输入身份、manifest 自描述性、schema/DSID
负例和 M1-05 删除准备。不会修改冻结 protocol V1，不增加 CLI 科学配置面，也不会把
Angular5 异常静默转成新的事件 selection。读取前后输入复验满足批准设计；per-chunk
复验只作为威胁模型限制记录，不在本 Sprint 扩大实现。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | Medium | Correctness | Kimi M1 | `run_dir.parent` 被同时当成 `runs_root`，允许任意父目录 | Partial | 设计 §11 要求 run 位于允许的 `runs/` 根下；Sprint §7 的微型测试使用临时目录，不能绑定仓库唯一绝对路径 | 要求 `run_dir` 的直接父目录名精确为 `runs`，并继续由 `RunTransaction` 校验 direct-child、containment 与 symlink；测试改用 `<tmp>/runs/<id>`。不采用只能指向仓库 `runs/` 的更窄方案，以保留隔离测试。 |
| 2 | Medium | Risk | Kimi M2 | Git dirty 状态忽略 untracked 源码 | Accept | FR R7 和 Sprint §6 要求 manifest 绑定实际代码身份；当前 M1-02 新源码均未跟踪，`--untracked-files=no` 会给出误导状态 | dirty 检测包含 untracked 文件，并把 manifest 字段改为语义准确的 `worktree_dirty`；增加/更新 manifest 断言。 |
| 3 | Medium | Test | Kimi M3 | Golden 未覆盖 ZZ `official_metadata` normalization | Accept | DSID 363490 的生产路径使用 protocol 官方 normalization；现有 golden 只覆盖 Higgs event-derived 路径 | 增加 ZZ/MeV/open-data golden，比较 legacy `normalization_override` 与新 protocol normalization 的 cutflow、`physical_weight`、`train_weight` 和共享列。 |
| 4 | Medium | Correctness | Kimi M4 | `build_angular5` 异常策略未显式测试 | Accept | 迁移权威的 enrichment 链对 Angular5 异常为 fail-closed 整 run 失败；把异常事件静默丢弃会新增 selection 并改变 cutflow | 保持异常传播，增加选中事件 Angular5 失败导致整个 sample/run 失败的明确测试；不新增隐式事件过滤。 |
| 5 | Low | Reproducibility | Kimi L1 | software manifest 缺 `awkward`、`vector` | Accept | ROOT reader/event 构造直接依赖这两个 distribution，FR R7 要求绑定软件环境 | 将 `awkward`、`vector` 加入 `_software_versions` 并在集成 manifest 测试中断言。 |
| 6 | Low | Risk | Kimi L2 | ROOT 只在整个读取前后复验，未逐 chunk 复验 | Reject | 批准设计 §8.1 明确要求读取前后验证，当前实现会在发布任何成功产物前检测替换并留下 failure receipt；逐 chunk 复验是更强威胁模型而非已批准等价门 | 不改变 reader/chunk 语义；在 Sprint 风险边界记录“读取期间的临时替换可能先影响内存中解析，但最终复验会阻止成功发布”。未来高保障协议可另行设计。 |
| 7 | Low | Clarity | Kimi L3 | preprocess manifest 的 `test_opened: false` 混淆 development 生命周期语义 | Accept | 设计 §10 将 test-opening 状态归属 development run；预处理只发布物理分离的 test 文件，不执行开启 claim | 从 preprocessing manifest 删除 `test_opened`，不改名为另一个可能暗示生命周期状态的字段。 |
| 8 | Low | Reproducibility | Kimi L4 | code hash 漏掉 package `__init__.py` | Accept | package 初始化文件可影响 import 行为；当前 code identity 应覆盖完整新主链 | 将 `src/__init__.py`、`src/cli/__init__.py`、`src/artifacts/__init__.py` 与全部新链直接依赖纳入 hash，并测试改变初始化文件会改变哈希。 |
| 9 | Low | Consistency | Kimi L5 | domain 与 protocol forbidden-feature 集合不同 | Partial | `src/domain/features.py` 是 legacy/raw feature leakage guard；protocol V1 的列表是新 32 列 artifact 到模型的权威禁用集合，二者处于不同层且都未泄漏 | 保留 legacy domain 集合以维持等价，在代码注释中说明层次；新增 protocol forbidden 与 19 项 allowlist disjoint 的精确测试，不强行合并两套集合。 |
| 10 | Low | Maintainability | Kimi L6 | compat alias 不利于 M1-05 删除跟踪 | Accept | M1-02 需兼容历史测试，M1-05 又必须完全删除旧执行面；显式迁移注释可防止别名被误认为永久 API | 在每个 alias stub 注明 authoritative replacement 和 M1-05 删除义务，并在 M1-05 plan 删除清单中列出这些 stub。 |
| 11 | Low | Maintainability | Kimi L7 | protocol loader 硬编码 V1 contract，未来版本脆弱 | Accept | 当前 exact hard-code 是 V1 fail-closed 要求，不应被泛化；未来 protocol 变更必须升版评审 | 在 loader 上补充注释，明确它是 sealed V1 loader，schema/version 变化必须新增或更新校验器。 |
| 12 | Low | Test | Kimi L8 | CLI 未覆盖关闭 enhanced selection 的路径 | Reject | protocol V1 byte-for-byte 固定 `lepton_quality.enabled: true`，普通 CLI 不允许覆盖 selection；非 enhanced legacy 路径已有 domain/selection 单测 | 不增加 CLI 或 run-config 覆盖面，也不制造非 V1 protocol；在交付证据注明该路径由历史/domain 测试保护而非 M1-02 CLI。 |
| 13 | Info | Verification | Kimi I1 | 专项通过且完整失败集合未扩大 | Accept | 评审实测 `15 passed, 1 skipped`；完整套件为 `791 passed, 211 failed, 3 skipped`，与 M1-01 的 211 个失败逐项相同 | 在 Sprint §10.3 记录最终重跑结果和失败集合逐项 identity；提交前重新验证，不能仅引用评审时输出。 |
| 14 | Info | Correctness | Kimi I2 | 19+13 schema 已满足设计 | Accept | `OUTPUT_COLUMNS` 当前顺序与 Sprint §5.2 一致 | 保留现有实现，并用 No.20 的长度、唯一性和 disjoint 精确断言增强回归门。 |
| 15 | Info | Correctness | Kimi I3 | ROOT stat/SHA-256 与替换拒绝已实现 | Accept | `inspect_mc_input`/`verify_mc_input` 和相应单测满足设计 §8.1 | 保持实现；最终专项重跑后记录为已验证，不扩展到 per-chunk。 |
| 16 | Info | Boundary | Kimi I4 | MC-only protocol/reader 边界已实现 | Accept | loader exact keys 和 pipeline 固定 Higgs/ZZ，未知 data sample 在 ROOT I/O 前失败 | 保留实现，并增加 No.23 的 CLI swapped-root DSID 绑定负例。 |
| 17 | Medium | Test | GLM M1 | import 边界测试用 substring，漏相对导入和 `src/config.py` | Accept | Sprint §5.2 要求验证 import graph；评审探针证明 `from ..pipeline`、`mplhep` 等可逃逸 | 改为 AST 解析、相对导入解析感知的测试，覆盖 `src/cli/preprocess.py`、`src/preprocessing`、`src/config.py`、`src/artifacts`，精确禁止旧 pipeline/preparation/provenance/io/plots、真实数据、generic predict、plotting/XGBoost 越层依赖。 |
| 18 | Medium | Maintainability | GLM M2 | 新 `src/config.py` 仍经 compat stubs 导入 feature constants | Accept | M1-05 删除 stubs 会破坏新链；manifest 当前又未 hash stubs | 立即改为从 `src.domain.angular5`/`src.domain.features` 直接导入；与 No.8 一并补齐 code hash 闭包。 |
| 19 | Medium | Auditability | GLM M3 | 物理权重 luminosity 只硬编码在 code，manifest 不自描述 | Partial | 值 `10000.0` 与冻结配置/legacy default 等价；Sprint §9 禁止改 protocol V1，但 FR R7 要求 run 自描述 | 本 Sprint 在 manifest 明确记录 `luminosity_pb: 10000.0` 并测试；不修改 sealed protocol V1。把未来 protocol version 的显式字段记录为后续版本义务。 |
| 20 | Low | Test | GLM L1 | 缺 32 列唯一性及 model/metadata/protocol-forbidden disjoint 断言 | Accept | Sprint §5.1/§6 要求精确 19+13 schema 且 metadata 不进入模型 | 增加 `len==32`、唯一性、model/metadata disjoint 和 protocol forbidden disjoint 精确断言。 |
| 21 | Low | Consistency | GLM L2 | cutflow/summary 顶层短 sample key 与内部 DSID-suffixed `sample_name` 不一致 | Accept | legacy artifact 和内部 cutflow 使用 `higgs_345060`/`zz_363490`，M1-03 消费前应只有一个 authority | 将 cutflow 与 summary 的 sample keys 统一为 DSID-suffixed 名称并更新 golden/integration assertions。 |
| 22 | Low | Test | GLM L3 | live golden 已共享迁移后的 domain，且缺 ZZ 路径 | Accept | 直接 old/new domain 比较确实会共享 alias；评审已额外证明 HEAD old source 与新 domain 代码等价 | 增加 No.3 的 ZZ orchestration golden，并在 Sprint §10.3 记录 HEAD `409a728` 旧模块与新 domain 的逐文件内容/差异证据；不恢复一份永久重复旧 domain。 |
| 23 | Low | Test | GLM L4 | CLI 无 Higgs/ZZ ROOT 对调的 DSID 绑定负例 | Accept | 单元层虽验证 wrong channel，Sprint §5.3 还要求 CLI 层的 DSID fail-closed | 复用 micro-ROOT fixture，将两个 ROOT 路径对调，断言 exit 1、failure receipt 存在且 success manifest 不存在。 |
| 24 | Low | Clarity | GLM L5 | CLI stderr 丢失异常类型 | Accept | Sprint §5.3 要求规范失败消息；failure receipt 已有 `error_type` | stderr 至少输出 `{ExceptionType}: {message}`，保持 exit code 不变；不新增普通 CLI debug/traceback 参数。 |
| 25 | Low | Input binding | GLM L6 | protocol/run-config 未拒绝 symlink/非普通文件 | Accept | 设计 §11 对输入 symlink fail-closed，配置虽然有内容哈希，也应与 ROOT binding 一致 | 在读取前复用/增加 regular-file、no-symlink 校验，并添加 protocol 与 run-config 的负例；继续在结束前复验 bytes。 |
| 26 | Info | Verification | GLM I1 | 完整 suite failure set 与 M1-01 逐项相同 | Accept | 评审在隔离 HEAD worktree 重跑基线并完成双向集合比较 | 最终验证重新生成当前失败 inventory，并与保存的 M1-01 211 项基线逐项比较后写入 §10.3。 |
| 27 | Info | Correctness | GLM I2 | domain 搬迁字节等价且 155 个历史测试通过 | Accept | 评审比较 HEAD 源文件、新 domain 与 alias import 行为，无科学代码变化 | 最终重跑 155 项历史 domain 测试，并在交付记录 byte-identity 边界；compat stubs 仍按 No.10 留到 M1-05。 |
| 28 | Info | Artifact | GLM I3 | artifact no-clobber、manifest-last、双哈希等已满足 | Accept | M1-01 artifact 测试与 M1-02 micro-ROOT probe 均通过 | 保留事务语义；应用 No.2/5/7/8/19/25 后重跑 artifact、integration 测试并记录新 manifest contract。 |
| 29 | Info | Process | GLM I4 | §10 证据、stage 边界和 code-review-confirm 尚待完成 | Accept | Sprint workflow 要求 confirmation、实际重跑、只 stage 当前 Sprint 并独立提交 | 完成本文动作后填 §10；只 stage M1-02 plan/reviews/source/tests，保持 M1-03～M1-06 plan 未跟踪，最后使用规定提交消息。 |

## Needs Immediate Action

- 完成 AST import graph、`src/config.py` 直接 domain 导入、code/software/Git/config identity
  加固。
- 增加 ZZ official-metadata golden、Angular5 hard-failure、schema disjoint、DSID swapped-root
  和配置 symlink/regular-file 测试。
- 统一 sample keys，删除 preprocessing `test_opened`，在 manifest 记录 luminosity。
- 把 run 目录限制为名为 `runs` 的直接父目录，并同步所有 micro-ROOT/CLI 测试路径。
- 在 M1-05 plan 明确 compat stubs 删除义务，然后执行专项、完整 failure-set、安装和 CLI
  验证。

## Can Be Deferred

- Per-chunk ROOT identity 复验属于比批准设计更强的威胁模型；当前保留读取前后复验并记录
  限制。
- Luminosity 在下一 protocol 版本成为显式字段；M1-02 不修改 sealed V1，只在 manifest
  自描述。
- 非 enhanced-selection CLI 路径不属于 V1；继续由 legacy/domain 测试保护。
- 权威 345060/363490 ROOT count/cutflow 仍未执行；不得读取冻结 run 或真实数据补证。

## Final Status

**暂不接受 M1-02 实现。** 完成上述 Accept/Partial 动作，重新证明专项测试通过、完整
211 个失败集合不变，并填入 Sprint §10 实际证据后，方可提交并进入 M1-03。
