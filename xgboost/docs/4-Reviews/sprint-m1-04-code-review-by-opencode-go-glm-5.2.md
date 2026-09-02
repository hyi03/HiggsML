# Sprint M1-04 代码评审报告（独立）

- 评审对象：Sprint M1-04 实现（`higgsml-xgboost open-test` 绑定、原子、一次性 test-opening）
- 评审类型：代码评审（code review）
- 评审人模型：opencode-go / glm-5.2
- 日期：2026-09-02
- 状态：完成，无阻塞型缺陷；发现 0 Critical / 0 High / 5 Medium / 5 Low / 4 Info

## 1. 独立性与执行约束声明

- 本评审未读取、未搜索、未依赖 `docs/4-Reviews/` 下任何既有 document review、code review 或
  review-confirm 文档；全部 finding 由源码、测试、FR、Sprint、设计与 protocol 文件独立形成。
- 本评审未读取 `sprint-m1-05.md` 与 `sprint-m1-06.md`；对 M1-05/M1-06 的引用仅来自
  FR-001 R8 与批准设计 §12 的删除授权描述。
- 本评审为只读评审，除本报告文件外未写入、未修改任何文件。
- 未运行测试、包管理器、venv 命令、安装器、格式化工具或任何 git 变更命令；测试执行结果
  按任务声明视为已由外部验证，本报告只做测试存在性与断言强度的静态分析。

## 2. 评审输入

权威文件：

- `AGENTS.md`（项目根与 xgboost/ 两级）
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`（R1–R8、验收要点）
- `docs/3-Plan/sprint-m1-04.md`（§3 范围、§5 任务与测试要求、§6–§9）
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`（§6.3、§10、§11、§13）
- `config/preprocessing_protocol_v1.yaml`、`config/xgboost_protocol_v1.yaml`

实现与测试文件：

- `src/training/test_opening.py`（592 行）
- `src/cli/xgboost.py`（53 行）
- `src/training/trainer.py`（500 行，M1-04 复用其 code/software 身份与 manifest 构造）
- `tests/refactor_training_support.py`、`tests/unit/test_refactor_test_opening.py`、
  `tests/integration/test_refactor_open_test_cli.py`

为核实绑定与等价性，额外只读查阅了：
`src/artifacts/transaction.py`、`src/artifacts/manifest.py`、`src/training/dataset.py`、
`src/training/evaluation.py`、`src/training/qualification.py`、`src/training/model.py`、
`src/training/folds.py`、`src/config.py`、`src/preprocessing/pipeline.py`、
`src/experiment_runner.py`（legacy `_test_metrics`/`_save_test_plots`/`_validate_test_frame`
等价对照）、`src/full_training_policy.py`（fixture 依赖对照）、`pyproject.toml`、
`tests/integration/test_refactor_develop_cli.py`、`tests/golden/` 目录清单。

## 3. 已验证正确的关键行为

以下为本次评审逐项确认、与 Sprint/FR/设计要求一致的核心机制（含证据位置）：

1. **固定顺序与 claim 前不读 test bytes**（Sprint §5.1/§9）：`run_open_test` 的顺序为
   reserve test run（`RunTransaction` enter，test_opening.py:500，在任何输入读取前
   mkdir 占用）→ 无 test-content 的上游/资格/哈希校验
   （`_validate_development`，165-367）→ atomic claim（`_claim`，370-391）→
   test read/hash/decompress/parse/score（506-527）→ manifest 发布（591）。
   claim 前对 `test.csv.gz` 的唯一触碰是 `_resolve_test_path`（110-133）中的
   receipt 元数据校验与 `_file_fingerprint` 的 `lstat`（98-107），无任何字节读取，
   恰好等于 Sprint §9 允许的"test identity metadata + lstat/path containment"。
   单元测试 `test_open_test_claims_before_read_and_publishes_exact_contract`
   （unit 53-93）用 spy 断言 test 路径上 `read_regular_bytes` 恰好被调用一次且当时
   claim 文件已存在（`observations == [True]`）。
2. **原子 claim 与并发唯一获胜**：claim 以 `open("xb")`（O_EXCL，test_opening.py:387）
   独占创建，永不改写；`state` 目录符号链接被显式拒绝（372-373）。
   `test_concurrent_distinct_test_runs_have_one_claim_winner`（unit 290-308）断言
   两个并发不同 run-dir 恰一胜一败、恰一份 manifest 与一份 failure receipt；失败者在
   claim 前/claim 处即退出，结构上不可能读取 test bytes。
3. **occupied 零读零写**：occupied target 在 `RunTransaction._validate_target`
   （transaction.py:102-110）于 `__enter__` 抛 `FileExistsError`；因 `__enter__` 未成功，
   `__exit__` 不会执行，故不写 receipt、不改写既有内容。
   `test_occupied_output_is_zero_read_and_zero_write`（unit 96-110）验证零输入读、
   marker 保留、文件集合不变。
4. **失败收据与 claim 消耗边界**（Sprint §5.1/§5.2、设计 §11）：claim 前验证失败
   （qualification 篡改、上游 artifact/preprocess manifest 篡改、未知布局、不合格 run）
   写 `failure.json` 且不创建 claim（unit 136-149、168-229）；claim 后失败（评分异常、
   同尺寸 test 损坏、非法 32 列 schema）保留 claim 并永久消耗开启权，重试拒绝
   （unit 113-133、232-287）。
5. **资格证据重算而非信任字符串**（Sprint §5.1）：`_validate_development` 从解压校验后的
   OOF、sealed protocol 重算 `build_working_points`/`weighted_oof_auc`/`background_mass_ks`
   并经 `qualify` 重建完整 qualification，逐字段比较 receipt JSON 与 manifest 双份记录，
   且强制 `rebuilt_qualification["eligible"] is True`（284-305）；四项门
   （AUC≥0.80、三 KS≤0.10、signal eff 严格大于 background eff、OOF 有限/唯一/全覆盖）
   全部由重算路径执行，与 `config/xgboost_protocol_v1.yaml` 的 qualification 值一致。
6. **阈值来源唯一**（Sprint §5.2）：`_test_metrics` 只使用
   `evidence["working_points"]`（冻结 `working_points.json`，已被三向一致性校验，
   284-299）中的 `threshold`；不从 protocol target 或 test 分数重算。
   `test_frozen_threshold_comes_only_from_development_working_points`
   （unit 152-165）与 `test_test_scores_cannot_change_frozen_thresholds`
   （unit 330-347，poison 分数）均通过。
7. **科学行为等价迁移**（FR R4、Sprint §5.2）：`test_opening._test_metrics`
   （410-433）与 legacy `experiment_runner._test_metrics`（574-601）逐行对照为
   同一实现（schema 1.0、status complete、test_rows、abs(physical_weight) 加权 AUC、
   非加权 AUC、`>=` 阈值选择、per-class efficiency 与 selected_rows）；无 test KS、
   无 qualification、无 reproduction gate、无任何 test-result 决策。三张 plot
   （roc/score_distribution/score_vs_m4l，436-477）与 legacy
   `_save_test_plots`/`_save_score_plots`（638-678）输入语义一致（同 figsize、dpi、
   bins、标签、散点参数）。
8. **冻结模型只评不训**（FR R6）：`_load_model`（136-146）仅 `load_model` 并校验
   feature names 严格等于 19 项 Angular19 且 `num_features()` 一致；模块内无任何
   `fit` 调用；评分经 `positive_scores` 使用 `MODEL_FEATURES` 固定顺序（523）。
9. **test 帧校验**（Sprint §5.2）：claim 后恰好读取一次，先 compressed SHA/size
   （508-509）、再 deterministic 解压与 canonical SHA（511-515）、再解析并校验
   32 列固定顺序、`split == {"test"}`、label {0,1}、全数值有限、
   `(channelNumber,eventNumber)` 唯一、每类绝对物理权重为正（394-407）、行数等于
   manifest 记录（521-522）。
10. **产物 allowlist**（Sprint §5.2）：成功 test run 精确为六文件
    （`artifacts/{test_metrics.json,manifest.json}`、`predictions/test_scores.csv.gz`、
    `plots/{roc_curve,score_distribution,score_vs_m4l}.png`），无 `config.yaml`、
    `model/`、`state/`；`RunTransaction.write_bytes` 的 "xb" no-clobber
    （transaction.py:40-48）+ 单元断言（unit 73-80）落实。prediction 固定
    `OUTPUT_COLUMNS + ("xgb_score")` 33 列（35、524），deterministic gzip
    `compresslevel=9, mtime=0`（530），并按预处理惯例记录双哈希（544-548）。
    development 侧九文件 allowlist（318-331）与 Sprint §5.1 的九文件清单一致。
11. **上游不可变与唯一新状态**（FR R7、Sprint §6）：manifest 发布前重读全部
    development/preprocess/protocol/model/claim bytes 比对（`_verify_preclaim_sources`
    + `verify_development_input`，484-491、538），development manifest 的
    `test_opened: false` 冻结不回写（unit 91-93），唯一新上游状态是
    append-only `state/test_opening.json`
    （`test_success_does_not_write_back_any_development_artifact`，unit 311-327）。
12. **manifest 绑定面**（Sprint §5.2）：test manifest（551-590）绑定 claim
    （path/sha/size）、development run（resolved path + manifest SHA-256）、
    upstream preprocess run（path/manifest SHA/protocol identity）、sealed protocol
    （schema/SHA）、code（git identity + 代码哈希）、software、model bytes、
    test 输入身份（含 resolved_path）、19 特征、working points、counts、schema 与
    全部 output receipts；claim 内容恰为 Sprint §5.1 固定的六字段
    （schema/status/created time/development manifest SHA/resolved test-run path/
    预期 test artifact identity，377-384）。
13. **CLI 最小参数面**（FR R3、Sprint §5.3）：`open-test` parser 只接受
    `--development-run/--run-dir`（cli/xgboost.py:21-23）；集成测试对
    `--overwrite/--protocol/--model/--features/--seed/--folds/--candidate/--threshold/
    --qualification` 全部拒绝（integration 15-27）；普通 `Exception` 归一化为
    `higgsml-xgboost failed: Type: message` 且 exit 1，不捕获 `BaseException`
    （42-47）；成功仅输出 `succeeded`（48）；所有面向用户的失败消息为固定文案，
    test 解析失败统一包装为不含内容的 ValueError（510-519）。
14. **上游身份链**（Sprint §5.1）：sealed `config.yaml` bytes SHA 与 manifest protocol
    identity 相等并用 sealed V1 loader 解析（251-257）；upstream preprocess
    manifest SHA、protocol/run_config identity、development 双哈希身份逐一比对
    （259-274）；外部 preprocessing protocol path/schema/SHA 校验且不依赖外部
    XGBoost protocol 原路径（276-282）。`_upstream_payload`（trainer.py:360-376）与
    该校验的字段集精确互逆。

## 4. Findings 总表

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Auditability / 上游绑定 | `src/training/trainer.py:301-322`（经 `src/training/test_opening.py:31,574` 进入 test manifest） | `_code_sha256` 的代码身份哈希未覆盖 5 个现行维护链源文件，test/development manifest 的 `code` 绑定不完整 | 源列表（303-314）只含 `src/cli/__init__.py`、`src/cli/xgboost.py`、`src/preprocessing/{__init__,pipeline}.py` 等；实际存在且被主链使用的 `src/cli/preprocess.py`、`src/preprocessing/reader.py`、`src/preprocessing/profiles.py`、`src/preprocessing/application.py`、`src/progress.py`（`pipeline.py:20`、`application.py:20-21`、`trainer.py:221` 的传递依赖）均未入哈希 | 将代码哈希源改为对 `src/{cli,preprocessing,domain,training,artifacts}/*.py` 整包 glob，并显式加入根级维护文件 `src/{__init__,config,validation,progress}.py`；配套更新单元断言 |
| Medium | Compliance / 校验完整性 | `src/training/test_opening.py:165-184,316-317,333-334` | development manifest 的 `final_parameters` 仅做键存在性检查，未做语义校验：未从 `fold_metrics.csv` 的 best_iteration 重算最终树数，也未校验已加载模型的真实树数与 `n_estimators` 一致 | `_exact_keys` 只要求键存在；`manifest.get("candidate") != dict(protocol.candidate)` 校验了 candidate（316），但无任何对 `final_parameters` 取值的比较；`_load_model`（136-146）只校验特征名与 `num_features()`，不检查 `num_boosted_rounds()`；Sprint §5.1 明确要求 exact-validate "candidate/final parameters" | 解析 fold_metrics.csv，按 `final_tree_count` 语义重算中位数树数并与 `manifest["final_parameters"]["n_estimators"]` 及 `booster.num_boosted_rounds()` 三方比对，不一致即 pre-claim 拒绝 |
| Medium | Test coverage / 等价证据 | `tests/golden/`、`tests/unit/test_refactor_test_opening.py` | Sprint §5.2 要求的 "Golden 对照 legacy score/metrics/三张 plot 的输入语义" 测试缺失；golden 目录只覆盖训练链（`train_experiment`），无任何 open-test 指标/绘图对 legacy 的对照 | `tests/golden/test_refactor_training_golden.py:9`、`test_refactor_characterization.py:15` 仅 import `train_experiment`；全测试树 grep 无 `_test_metrics`/`run_test_evaluation` 的 legacy 对照 | 增加 golden 测试：同一合成 test 帧上分别调用 legacy `experiment_runner._test_metrics` 与 `test_opening._test_metrics`，断言输出相等；plot 至少断言输入参数/列语义一致（figsize、bins、score 列、权重列） |
| Medium | Test coverage / CLI 契约 | `tests/integration/test_refactor_open_test_cli.py` | Sprint §5.3 要求的 "同一 development run、不同新 test run-dir 第二次调用 exit 1，且没有第二次 test read" CLI 级测试缺失；现有集成测试只有 parser 拒绝、错误归一化与成功 smoke | 该文件仅含 3 个测试（15-27、30-47、50-87）；二次调用仅在单元层覆盖（unit 113-133）且无 read spy，CLI 层 exit 1 与"无第二次读取"均未断言 | 在集成层追加第二次 `open-test` 调用：断言 returncode 1、stderr 为归一化消息、第二 run 内有 `failure.json` 无 manifest；"无第二次 test read"可用模块级 wrapper/spy 或对 preprocess manifest 做读取时间戳侧证 |
| Medium | Maintainability / 前向兼容 | `tests/refactor_training_support.py:13` | 测试支撑模块 import legacy `src.full_training_policy.development_fold`，而语义相同的新实现已存在于 `src.training.folds.development_fold`；FR-001 R8 与设计 §12 授权在后续 Sprint 删除旧执行面，届时该 fixture 将断裂或迫使保留 legacy 模块 | `from src.full_training_policy import development_fold`（13 行）；对照 `src/full_training_policy.py:201-206` 与 `src/training/folds.py:13-18`，payload/digest/modulo 逐字节相同 | 将 import 改为 `from src.training.folds import development_fold`（行为等价，fixture 无需其他改动） |
| Low | Fail-closed 阶段正确性 | `src/training/test_opening.py:129-132` | test receipt 的 `sha256_compressed`/`sha256_canonical_csv` 只校验"64 字符字符串"，未校验十六进制；非 hex 的畸形身份可通过 pre-claim 校验，直到 claim 后哈希比对才失败并永久消耗开启权 | `isinstance(value, str) or len(value) != 64` 判定；对照 `dataset._sha256_identity`（dataset.py:66-69）有完整 `[0-9a-fA-F]{64}` 正则 | 在 `_resolve_test_path` 复用与 `dataset._sha256_identity` 相同的 hex 校验，使畸形 manifest 身份在 pre-claim 阶段被拒绝 |
| Low | Compliance / 发布前复核 | `src/training/test_opening.py:538-540` | Sprint §5.2 要求 manifest 发布前"再次验证……test bytes 均未改变"；实现对其余全部输入做了字节级重读，唯独 test 文件只做 stat 指纹（size/mtime_ns/ctime_ns/ino），同尺寸且还原 mtime 的替换或 ctime/ino 不可靠的文件系统可绕过 | `_verify_preclaim_sources`（484-491）重读 bytes，但 test 路径仅走 `_file_fingerprint` 比较（539-540） | 发布 manifest 前对已读入内存的 compressed bytes 重新做一次 SHA-256 比对（文件已在内存，成本可忽略），或在文档中明确声明 stat 指纹为接受的复核机制并记录于 manifest |
| Low | Compliance / receipt 校验 | `src/training/test_opening.py:80-95,207-227` | development 侧 candidate/fold/OOF receipts 的 `rows`/`columns` 只要求键存在，取值从不与解析后的 artifact 比对（如 OOF receipt rows vs `len(oof)`、columns vs `OOF_COLUMNS`）；与 `_resolve_test_path` 对 test receipt 的逐字段取值校验不对称，Sprint §5.1 要求 exact-validate "全部 output receipts" | `_receipt_bytes` 仅验证 path/sha/size；OOF 帧的列与行数校验存在于 `_validate_oof`（155）但未回指 receipt 字段 | 在 receipt 校验中加入 `rows`/`columns` 取值断言（OOF、candidate、fold 三处），与 test receipt 的校验强度对齐 |
| Low | Robustness / 布局与路径边界 | `src/training/test_opening.py:318-331,494-497` | 九文件 allowlist 只枚举文件（`path.is_file()`），空目录不可见；且 `--run-dir` 只要求父目录名为 `runs`，未禁止 test run 落在 development/preprocess run 内部。若上游 run 内预存空 `runs/` 目录（对 allowlist 不可见），`--run-dir <development>/runs/x` 会在上游 run 树内写入新文件，超出"唯一允许的新上游状态是 `state/test_opening.json`"的验收边界 | `actual` 集合仅收集 `is_file()` 条目（324-327）；`destination.parent.name != "runs"` 是唯一位置约束（495-497）；`RunTransaction` 不检查与上游 run 的包含关系 | allowlist 同时枚举目录（`rglob` 全条目而非仅文件）；并在占用前断言 `destination` 不位于 `development_run` 或 `binding.input_run` 之内（反之亦然） |
| Low | Test coverage / 负例矩阵 | `tests/unit/test_refactor_test_opening.py` | Sprint 测试清单中的以下负例路径无直接测试：缺文件（development artifact 被删除）、test 帧 `split != "test"`、test 身份重复、单类/零权重 test、manifest rows 与解析行数不一致（哈希自洽时）、canonical CSV 哈希不匹配、发布前 output 被替换、protocol working-point target poison（§5.2 poison 清单只覆盖了 test 分数 poison） | 对应校验代码存在（test_opening.py:394-407、514-522）但测试树中无触发这些分支的用例；`test_invalid_test_schema_fails_only_after_claim`（249-287）仅覆盖列数不匹配一种 | 按上述清单补充参数化负例，断言失败阶段（pre-claim 不耗权 / post-claim 耗权）与 receipt 存在性 |
| Info | Style / 命名 | `src/training/test_opening.py:484` | `_verify_preclaim_sources` 实际执行的是 claim 之后、manifest 发布之前的复核，函数名易误导为"claim 前校验" | 调用点在 538 行（所有输出写入之后） | 改名如 `_verify_sources_before_manifest` 或加 docstring 说明语义 |
| Info | Maintainability / 模块边界 | `src/training/test_opening.py:31,42-52,480-481`；`src/training/dataset.py:53-63` | 跨模块导入 trainer 的下划线私有工具 `_code_sha256/_git_identity/_software_versions`；`_mapping/_exact_keys` 在 dataset 与 test_opening 重复实现；`_receipt` 在 trainer 与 test_opening 重复 | import 行与两处相同形状的辅助函数 | 将 code/software 身份与 JSON 校验辅助收敛到共享模块（如 `src/artifacts/provenance.py`），消除私有跨模块依赖与重复 |
| Info | Auditability / 软件绑定 | `src/training/trainer.py:325-336` | `_software_versions` 未记录 matplotlib 版本，而 test run 的三张 PNG 由 matplotlib 生成，plot 可复现性无法从 manifest 审计 | 版本字典仅含 python/numpy/pandas/pyyaml/scikit-learn/xgboost | 将 matplotlib（以及后续涉及绘图时的依赖）加入版本绑定 |
| Info | Style / 生产断言 | `src/training/test_opening.py:486,505,526` | 以 `assert isinstance(...)` 承担生产不变量，`python -O` 下失效 | 三处 `assert isinstance` | 改为显式类型检查异常或删除（值来源受控） |

## 5. Finding 详述与裁决建议

### F1（Medium）代码身份哈希未覆盖全部维护链源文件

`_code_sha256`（trainer.py:301-322）是 development 与 test manifest 共用的 `code`
绑定来源。其源列表遗漏了现行主链的 5 个文件：`src/cli/preprocess.py`（维护链 CLI）、
`src/preprocessing/reader.py`（ROOT 读取器，`pipeline.py:20` 直接依赖）、
`src/preprocessing/profiles.py`（输入 profile）、`src/preprocessing/application.py`
（预处理 application service）与 `src/progress.py`（trainer 进度回调依赖）。这些文件的
任何改动都不会改变 manifest 中的代码哈希，使 FR R7 的"Manifest 绑定……代码"在
open-test 审计链上不完整。修复不影响行为与既有测试断言的具体哈希值来源（除哈希值本身
会变化外），建议随 M1-04 review-confirm 一并应用。

### F2（Medium）`final_parameters` 只查存在、不查一致性

`_validate_development` 对 manifest 的 17 键做精确键集校验，其中 `candidate` 与
`selected_candidate` 有取值校验（test_opening.py:316-317），`final_parameters` 没有：
既没有从 `fold_metrics.csv` 的 `best_iteration` 重算
`max(1, round(median(best_iteration+1)))`（model.py:53-57 的冻结语义），也没有校验
`_load_model` 加载的 booster 实际树数。Sprint §5.1 将 "candidate/final parameters"
列入 exact-validate 清单。后果是 training 证据与被封存模型之间的审计绑定弱于规格：
若 model.json 被连同 manifest receipt 一致地替换，或 `final_parameters` 记录与
fold 证据不一致，open-test 无法发现。该缺口不破坏一次性/不窥视保证（资格门由 OOF
重算独立把守），故定级 Medium 而非 High。

### F3（Medium）§5.2 golden 对照测试缺失

Sprint §5.2 测试要求第一条是 "Golden 对照 legacy score/metrics/三张 plot 的输入语义"。
现有 golden 测试（`tests/golden/test_refactor_training_golden.py`、
`test_refactor_characterization.py`）只覆盖训练链。本评审通过逐行对照确认
`test_opening._test_metrics`（410-433）与 legacy `experiment_runner._test_metrics`
（574-601）是同一实现、三张 plot 输入语义一致（§3 第 7 条），但按 Sprint 的证据标准，
这一等价性目前只有评审旁证、没有可回归的测试证据。建议补充 golden 测试以闭环。

### F4（Medium）§5.3 CLI 二次调用负例缺失

Sprint §5.3 测试要求 "Eligible module/console CLI 全链成功；以同一 development run、
不同新 test run-dir 第二次调用 exit 1，且没有第二次 test read"。前半句已由
`test_module_and_console_open_test_smoke` 覆盖；后半句在 CLI 层完全缺失，单元层的
二次调用测试（unit 113-133）也没有读取 spy。结构上第二次调用在
`_validate_development` 的首个 claim 检查（168-170）即抛出，先于任何读取，因此行为
正确但证据缺失。建议按 §5.3 原文补测试。

### F5（Medium）fixture 依赖 legacy 模块

`tests/refactor_training_support.py:13` 从 `src.full_training_policy` 导入
`development_fold` 用于构造跨 fold 均衡的合成帧。新实现
`src.training.folds.development_fold` 与其逐字节等价（payload
`task4b-fold:{channel}:{event}`、blake2b digest_size=8、大端取模）。FR-001 R8 与设计
§12 授权删除旧 full-training 执行面；保留该 import 要么在 M1-05/M1-06 造成
fixture 断裂，要么迫使保留本应删除的 legacy 模块。属于一行修复。

### F6–F10（Low）见总表

均为 fail-closed 阶段归属、发布前复核强度、receipt 取值校验、目录级布局/路径边界、
负例矩阵覆盖的收紧项，不影响核心保证，可随 review-confirm 裁决批量应用或明确保留。
其中 F9 建议同时做目录枚举与 run-dir 与上游 run 的不相交断言，二者共同封住
"在上游 run 内开 test run"的边缘写入侵。

### F11–F14（Info）见总表

命名、模块边界、软件绑定与生产断言的整洁性建议，不构成合规缺口。

## 6. Sprint 测试要求覆盖矩阵

| Sprint 要求（§5.1–§5.3 测试清单） | 状态 | 证据 |
|---|---|---|
| 不合格 run 拒绝 | 已覆盖 | unit 168-185 |
| 四门矛盾（重算资格不符） | 部分覆盖：仅 qualification.json 单门篡改负例（136-149）；"重算结果为不合格却声称 eligible"的直接构造负例缺失 | 见 F10 |
| 未知/多余布局 | 已覆盖（文件级） | unit 222-229；目录级见 F9 |
| 缺文件 | 未覆盖 | 见 F10 |
| protocol/model/OOF/working-point/preprocess manifest 哈希变化 | 已覆盖 | unit 188-219 |
| 预存 claim / 重复调用 / 不同 run-dir 二次调用 | 已覆盖（等价路径：第二次调用触发同一 claim 检查） | unit 113-133 |
| 并发调用 | 已覆盖 | unit 290-308 |
| claim 前不读 test bytes（spy） | 已覆盖 | unit 53-71 |
| claim 后 test 损坏 / scoring 异常 → receipt + 保留 claim + 重试拒绝 | 已覆盖 | unit 113-133、232-247 |
| occupied / pre-claim 拒绝不消耗 claim | 已覆盖 | unit 96-110、136-149、168-185、188-229 |
| Golden 对照 legacy score/metrics/plots | 未覆盖 | 见 F3 |
| poison protocol target | 未覆盖 | 见 F10 |
| poison test score distribution | 已覆盖（阈值不变性） | unit 330-347 |
| compressed/canonical 哈希、32 列、split、双类、identity、rows/counts | 部分覆盖：compressed 哈希与 32 列已覆盖（232-287）；split/双类/identity/rows/canonical 负例缺失 | 见 F10 |
| before-manifest input/output mutation 负例 | 未覆盖（输入侧由 `_verify_preclaim_sources`+指纹承担且无测试；输出侧仅靠 no-clobber） | 见 F7、F10 |
| parser 拒绝全部覆盖项 | 已覆盖 | integration 15-27 |
| Exception 归一化 / exit 1 / 不捕 BaseException | 已覆盖 | integration 30-47 |
| 成功仅输出 `succeeded` | 已覆盖 | integration 64-65、86-87 |
| 显式 `valid_test` fixture、默认 deny fixture 不变 | 已覆盖 | support 81-176（deny bytes 98-102） |
| module/console CLI 全链成功 | 已覆盖 | integration 50-87 |
| 同一 development run 第二次 CLI 调用 exit 1 + 无第二次读取 | 未覆盖 | 见 F4 |

## 7. 结论

M1-04 的核心机制——固定顺序（reserve → 无 test-content 校验 → atomic claim →
test 读取评价 → manifest）、O_EXCL 一次性 claim、并发唯一获胜、pre/post-claim 失败
收据边界、九文件/六文件 allowlist、33 列 deterministic prediction、冻结阈值来源、
`_test_metrics` 逐行等价迁移、CLI 最小参数面——均正确实现并有测试佐证，
满足 FR-001 R6/R7 与设计 §6.3/§10/§11 的验收语义。

未发现 Critical/High 缺陷。5 项 Medium 均为审计绑定完整性（F1、F2）与
Sprint 声明的测试证据缺口（F3、F4）及前向兼容（F5），不阻塞一次性生命周期与科学
安全边界；建议在 code-review-confirm 中裁决：F1、F2、F5、F6 直接应用，
F3、F4、F10 补测试后应用，F7–F9、F11–F14 可应用或明确保留并记录理由。

评审边界声明：本报告基于静态源码审阅形成；未执行任何测试、命令或真实数据/冻结 run
访问；测试通过情况以外部验证记录为准。未评审 sprint-m1-05 与 sprint-m1-06 的实现
或计划文件。
