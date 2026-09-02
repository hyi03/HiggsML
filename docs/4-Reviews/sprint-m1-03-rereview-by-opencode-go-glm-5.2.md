# Sprint M1-03 Focused Re-Review (Amended Documents)

- `评审人`: opencode-go / glm-5.2
- `日期`: 2026-09-02
- `评审类型`: document review（review-confirm 修订后的聚焦复审）
- `主审对象`: `neural/docs/sprint-m1-03.md`（修订后工作树版本）
- `绑定协议`: `neural/docs/adversarial-mlp-protocol-v1.md`（新增工作树文件）
- `决策来源`: `docs/4-Reviews/sprint-m1-03-review-confirm.md`

## Reviewed Inputs

- `neural/docs/sprint-m1-03.md`（amended；git 状态 `M`，未提交）
- `neural/docs/adversarial-mlp-protocol-v1.md`（bound protocol；git 状态 untracked）
- `docs/4-Reviews/sprint-m1-03-review-confirm.md`（decision source）
- 交叉核对：根 `AGENTS.md`、`neural/AGENTS.md`、
  `neural/docs/FR-001-adversarial-mlp-refactor.md`、
  `neural/docs/preprocess-protocol-v1.md`、
  `neural_adversarial_mlp_refactor_design.md`、
  `neural/docs/sprint-m1-02.md`、`neural/docs/sprint-m1-04.md`
- 仓库状态证据：`git log`、`git diff`、`git diff --check`、`neural/src`、`neural/tests`、
  `neural/config` 目录现状

## Review Boundary and Method

- 独立工作：未读取 `sprint-m1-03-rereview-by-opencode-go-kimi-k2.7-code.md`，结论仅基于
  上述输入与仓库状态。
- 本复审只回答三个问题：(1) decision source 中每一条 Accept/Partial 动作是否被正确应用；
  (2) 修订后的 Sprint 与 Protocol 是否内部一致、可进入实现；(3) 修订是否引入新的
  Critical/High/Medium blocker。
- 评审过程为纯文档/代码库检查：未访问任何数据，未运行训练，未执行 `open-test`，
  严格保持 MC-only 与 held-out-test 边界。
- 数值断言（参数量、ramp、列契约）由评审人独立重算，不沿用前次评审结论。

## Decision-Source Application Verification

对 decision table 全部 29 项逐条核对（14、15、26–28 为 Accept-keep/无修改项，仅确认原文保留）：

| No. | Decision | Applied | Evidence（修订后位置） |
|---:|---|---|---|
| 1 | Accept | Yes | Sprint §3 L41–44；Protocol §1 L16–18、§2.1 L55–56。loader/trainer 边界已显式化（残留输入表语义歧义见 R1） |
| 2 | Partial | Yes | Sprint §5.3 L119–121；Protocol §8 L222–226。checkpoint 最小字段、deep CPU copy、protocol hash、内存 validator 均已写入；持久化/反序列化按 Partial 范围留给后续 Sprint，未扩 scope |
| 3 | Accept | Yes | Sprint §5.3 L121；Protocol §8 L216–218（双类、有限非负权重、正总和、关闭式失败） |
| 4 | Partial | Yes | Sprint §5.1 L79（poison accessor）；Protocol §2.1 L51–52（步骤顺序 + 不误称已物化 DataFrame）。但"立即拒绝/立即失败"与行级排除两种语义未钉死，见 R1 |
| 5 | Accept | Yes | Sprint §5.3 L124–126（白名单 `0.00/0.05/0.10/0.20/0.50`、拒绝 schedule override）；Protocol §4.3 L128 |
| 6 | Accept | Yes | Sprint §3 L45、§5.3 L119–121；Protocol §8 L225–226（load time YAML bytes SHA-256、validator hash mismatch 拒绝） |
| 7 | Accept | Yes | Sprint §5.2 L96 实现项 + L105 测试项；Protocol §5.3 L165–167 |
| 8 | Accept | Yes | Sprint §5.2 L96、§5.3 L131（`drop_last=False`）；Protocol §6 L192–193 |
| 9 | Accept | Yes | Sprint §5.2 L106–107；Protocol §5.3 L176–179 + §6 L190–191 |
| 10 | Accept | Yes | Sprint §3 L43–44；Protocol §2.1 L55–56（fitting 不新增 split 枚举值） |
| 11 | Accept | Yes | Sprint §5.1 L82–83、§5.3 L122–123；Protocol §9 L247 |
| 12 | Partial | Yes | Protocol §9 L248–249（`InputBindingError`→3、unexpected→70、不制造 4/5 虚假路径）；Sprint §5.1 L83；与 `neural/src/config.py` 既有 `ExitCode`/`InputBindingError` 一致 |
| 13 | Accept | Yes | Sprint §10 L185–187（收尾证据清单） |
| 14 | Accept (keep) | Yes | Sprint §6 L148–159 Windows/synthetic 权威边界保留并强化 |
| 15 | Accept (keep) | Yes | Sprint §5.2 L97、§6 L143；参数量独立重算通过（见下节） |
| 16 | Accept | Yes | Sprint §7 L155–166（`pip check`、两个 CLI `--help`、`git diff --check`、边界收尾声明） |
| 17 | Accept | Yes | Sprint §5.1 L68–70、§3 协议内容门 L35–45、§7 L160（`test_training_config.py`）、§8 步骤 1 L170 |
| 18 | Accept | Yes | Sprint §5.3 L136–139 完整测试绑定 Protocol §10 且声明摘要 checklist 不得跳过协议条目；主要 edge cases 已分布于 §5.1–5.3 |
| 19 | Accept | Yes | 同第 9 项机制 + 参数 bytes 不变断言（Sprint §5.2 L106–107） |
| 20 | Accept | Yes | Protocol §9 L242–245（warm-up/λ=0 记录 adv=0、total=cls；epoch 级分子/分母聚合、单次除法）；Sprint §5.3 L131–132 |
| 21 | Accept | Yes | Protocol §4 L92–94（两网络统一 bias、affine LayerNorm、`eps=1e-5`）；写入 YAML 由 §1"全部冻结字段"转录规则 + Sprint §3 内容门覆盖 |
| 22 | Accept | Yes | Protocol §2.1 L53（全行 `105 <= m4l <= 160`、仅背景进 binning）；Sprint §5.2 L104（兼容性核清见 R5） |
| 23 | Accept | Yes | Sprint §5.3 L122–123 绑定 Protocol §9 result object |
| 24 | Accept | Yes | Sprint §5.1 L82–83（与第 11 项独立成测试证据） |
| 25 | Accept | Yes | Protocol header L3–8（协议 ID/状态/日期/Sprint/需求来源/权威平台；状态为"文档评审确认通过，等待实现验证"） |
| 26 | Info (keep) | Yes | 无修改，复核一致 |
| 27 | Info (keep) | Yes | M1-02 已提交（`aebf0ce`）；`neural/src/training/` 仅 `__init__.py` 骨架，与依赖声明一致 |
| 28 | Info (keep) | Yes | MC-only/test/feature 边界在修订文本中闭合 |
| 29 | Accept | Yes | Sprint §3 L37–44 normative 句采用 protocol 原文（mutation 五类、test-first 顺序）；§5.3 L133–134 增加 exact `1e-4` 边界（相等/不超过 `1e-4` 改善/阈值）测试 |

**结论：29 项动作全部按 decision source 落实，无遗漏、无 scope 越界（第 2、12 项的 Partial
边界被正确尊重）。**

## Findings

| ID | Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|---|
| R1 | Medium | Consistency / Specification | Protocol §1 L16–18、§2.1 L30 与 L45；Sprint §3 L41–44；decision item 4 | loader 对 `split=test` 行的处置语义存在两种互斥读法：(a) 行级排除——loader 只读 split 列即在读取 identity/feature values 前把 test 行排除出 validated development 对象；(b) 整体关闭——输入中出现任何 test 行即 `InputBindingError` 立即失败。两种读法对混合表产生相反的可观测行为和相反的测试。 | §2.1 L30 写"入口接收已由 M1-02 产出的 29 列 MC 表"，而 M1-02 的唯一产物 `processed/mc_events.csv.gz` 固定含 39,709 行 test（preprocess protocol §7.2）——若按读法 (b)，loader 永远无法接受其声明的输入，且没有任何文档规定上游子集化步骤；若按读法 (a)，§2.1 L45"出现 test 或其他值立即拒绝"与 decision item 4 的"split 检查后立即失败"措辞又会误导实现者写成整体失败。M1-04 §9"数据加载层必须物理隔离 test 行读取，而不只是在指标层过滤"支持读法 (a)。两种读法均保持"test 特征值不被读取"的安全不变量，无安全退化。 | 在 Protocol §2.1 第 2 步加一句钉死语义，并在 Sprint §3 镜像。建议采用读法 (a)：loader 仅读取 split 列即排除 test 行（不读取其 identity/feature values）；`split` 出现 `train/validation/test` 之外的枚举值则整个输入 fail closed。相应把 poison 测试明确为两类证据：全 test 行惰性表 + 毒化 identity/feature accessor → loader 在 split 检查后失败且 accessor 未被调用；混合表用访问顺序探针证明 split 先于 identity/feature 读取。若所有者选择读法 (b)，则 §2.1 L30 必须改写为"M1-02 schema 的 development 子集表"，且 M1-04 须显式规定只读 split 列的上游子集化步骤。同时统一输入表称谓（避免把含 test 行的全表称作"development table"）。 |
| R2 | Low | Correctness（edge case） | Protocol §5.3 L169–174 | `L_adv = sum(adv_weight·CE)/sum(adv_weight)` 没有与 `L_cls` 对称的 batch 级分母保护：§5.2 明确要求 L_cls 的 batch 权重和大于零，但 L_adv 未规定。 | 单行 `physical_weight == 0` 是可能的（如 `mcWeight == 0`；preprocess protocol §5.1 甚至为 mean=0 设了特例），此时该行 `adv_weight = 0`。若某 batch 的背景行全部为零对抗权重，则 `0/0`；只会被 §8 的 NaN/Inf 后备检查以未定义的错误类别捕获，而非干净的 input binding 失败。概率极低（batch 1024、背景占比约 6%），非科学风险。 | 在 §5.3 补一句对称保护：batch 含背景行时其 `adv_weight` 和必须大于零，否则按 data contract 失败；或将该情形显式定义为 differentiable-zero 路径（同无背景 batch）。可在实现时以测试固定，无需重开文档评审。 |
| R3 | Low | Clarity / Requirement | Protocol §2.1 L55、§3；Sprint §3 L42–43、§8 步骤 2 | "loader 构造的 validated fold 对象"缺少 M1-03 内的构造路径与最小字段定义：协议只说 loader 输出 validated development 对象、五折编排归 M1-04，而稳定五折规则被明确禁止在进入 M1-04 前冻结（preprocess protocol §5.3）。M1-03 自身测试需要一条确定性的 fold 构造 API，目前只能靠实现者推断。 | Sprint §8 步骤 2 要求实现"validated development/fold 对象"；Protocol §3 只约束 fold 的 identity 非空/唯一/不相交，未列 fold 对象内容（fitting features/labels/train weights、fitting 背景 mass-bin index 与 adv weights、validation features/labels/weights、fold index/seed）。 | 在 Protocol §2 或 §3 加一小段 fold 对象最小字段清单，并声明 M1-03 的 fitting/validation 划分由调用方（测试）在上述 identity 约束内提供、生产五折规则由 M1-04 冻结。亦可在实现+代码评审阶段以测试契约固化，不强求文档先行。 |
| R4 | Info | Documentation | Sprint §5.2 L96；Protocol §6 L192 | 组织性小瑕疵：11-bin 非空/正权重检查（数据/fold 层约束）与"保留最后一个不完整 batch"（训练循环约束）被合并进 §5.2 同一条实现项；Protocol §6 L192"最后一个不完整 batch保留"缺一个空格。 | 两项要求均已在文且可测，仅位置与排版问题。 | 可在下次文档触碰时拆分为 §5.1/§5.3 各自条目并修正空格；不阻塞实现。 |
| R5 | Info | Consistency（已核清） | Protocol §2.1 L53、§5.1 L141–142 vs preprocess protocol §3.2 规则 18 | 潜在疑问点主动核清：M1-03 要求全行 `105 <= m4l <= 160`（闭区间），M1-02 selection 窗口为 `105 <= m4l < 160`（半开）。 | M1-02 输出行域为 `[105,160)`，是 M1-03 校验域 `[105,160]` 的子集，闭区间是为 `[155,160]` 闭 bin 服务的防御性超集；真实管线无冲突，合成测试中 `m4l=160` 合法落入末 bin。与 decision item 22 的意图一致。 | 无需修改；实现时按协议原文执行即可。 |

无新增 Critical/High 发现。

## Internal Consistency and Implementation-Readiness Verification

以下各项由评审人独立验证通过：

- **列契约**：Protocol §2.1 的 29 列输入与 preprocess protocol §6.1 逐列、逐序完全一致；
  §2.2 的 15 特征 tuple 与设计 §7.3 完全一致；禁止列 14 项，15+14=29 闭合，`m4l`、标识、
  provenance、权重列全部在禁止清单内。
- **网络与参数量**：层序、Dropout 仅前两层且 exact `0.10`、LayerNorm affine/`eps=1e-5`、
  全 Linear bias 与设计 §8.2/§8.3 一致；参数量独立重算：分类器
  1024+128+4160+128+2080+64+33 = `7,617`，对抗器 64+64+1056+64+363 = `1,611`，
  合计 `9,228`，与三处文档一致，且 Sprint §6 明确禁止以"约 9k"替代自动断言。
- **训练常数**：AdamW(lr=1e-3, wd=1e-4)、无 scheduler、batch 1024、max epochs 200、
  patience 20、AUC 改善阈值 `1e-4`、warm-up 5 epoch、ramp 6–15、base seed 42、
  fold seed `42+fold_index(0..4)`、CPU-only、`num_workers=0`、deterministic algorithms、
  拒绝 CUDA/MPS——Protocol §6/§7/§8 与设计 §8.5 及 Sprint 三方一致。
- **Ramp 算术**：epoch 6 = `0.1×target`、epoch 15 首次达到 target、epoch 16+ = target，
  "epoch 15 首次达到"表述正确；测试边界 epoch `1/5/6/14/15/16` 覆盖全部跳变点。
- **损失与权重**：weighted BCE 用 `train_weight`、signed `physical_weight` 不入优化器；
  对抗权重按 bin 内 `abs(physical_weight)` 归一化、每 bin 总和 exact 1（容差
  `rtol=1e-12, atol=1e-12`）；`L_cls` batch 分母保护已规定（R2 指出 `L_adv` 缺对称项）。
- **无背景 batch 机制**：`0.0 * classifier_logits.sum()` 保持 classifier graph 连接、
  不运行 adversary forward、`zero_grad(set_to_none=True)` 使 adversary 参数 `grad=None`；
  该机制对 PyTorch AdamW 成立（`grad=None` 的参数被跳过，不会发生 weight-decay 幽灵更新），
  Sprint 的"参数 bytes 不变"断言可执行。
- **Epoch 聚合**：跨全 epoch 累计加权分子/分母后单次除法、不做 batch 简单平均；
  warm-up/λ=0 记录 `adv=0`、`total=cls`；`total = cls + adv`（聚合后）——Protocol §9 与
  Sprint §5.3 测试一致。
- **Checkpoint/result**：字段清单、deep CPU copy、内存 validator（缺/多字段、错误 feature
  tuple、hash mismatch）、load-time YAML SHA-256 密封、M1-03 仅内存对象；result object
  按 §9 绑定。持久化按 decision item 2 的 Partial 正确延后。
- **错误分类与退出码**：`InputBindingError`→3、unexpected→70、不制造 4/5 虚假路径；与
  `neural/AGENTS.md`、M1-01 固化退出码及已提交的 `src/config.py`（`ExitCode`、
  `InputBindingError`）一致；YAML bytes SHA-256 密封在 `pipeline.py` 已有先例。
- **验证命令可执行性**：`higgsml-preprocess`/`higgsml-train` CLI 骨架已存在（`--help` 可跑）；
  §7 专项模块命名遵循既有 `test_preprocess_config.py` 惯例；本复审执行 `git diff --check`
  通过（exit 0），满足 confirm 的"文档修订后运行 git diff --check"要求。
- **Sprint 间边界**：M1-03 不含五折 OOF、lambda 选择、资格、test-opening、artifact 发布；
  `folds.py`/`qualification.py`/`develop` 子命令归 M1-04；`trainer.py` 由 M1-03 提供原语、
  M1-04 做编排，无冲突。`adversarial_mlp_protocol_v1.yaml` 与 training 模块当前不存在，
  符合实现前状态。
- **科学安全边界**：严格 MC-only、仅 synthetic development 测试、禁止真实数据读取/哈希/
  探测/发布、禁止 full-data training、禁止 held-out test 与 `open-test`、
  Windows/synthetic 不替代 locked native `osx-arm64` 权威 gate、educational/technical demo
  措辞——在 Sprint §1/§3/§6/§7/§10 与 Protocol §1/§9/§10 全部闭合；未发现任何预注册
  AUC/KS/效率/epoch/结构/阈值被放宽。
- **状态/表头一致性**：Protocol 状态"文档评审确认通过，等待实现验证"与 Sprint §10
  "文档评审确认通过，等待实现与代码评审"一致；日期、需求来源（FR-001-R3/R7）、权威平台
  表头齐全。

## Overall Conclusion

1. Decision source 的全部 29 项 Accept/Partial/keep 动作均已正确应用于修订后的
   Sprint 与 Protocol，包括第 2、12 项 Partial 的范围约束（持久化延后、不制造虚假
   退出码路径）。
2. 两份文档与 FR-001、设计文档、preprocess protocol v1、M1-04 范围及仓库既有代码/
   测试/配置惯例在结构、数值、常量、边界上整体一致；核心数值断言（29/15 列、
   7,617/1,611/9,228、ramp、bins、常数）经独立重算全部通过。
3. 未引入新的 Critical 或 High blocker。新发现 1 项 Medium（R1：loader 对 test 行的
   处置语义存在互斥读法，且与 §2.1 自述输入相矛盾）、2 项 Low（R2、R3）、2 项 Info
   （R4、R5）。三者均不触碰任何科学安全不变量——无论按哪种读法，test 特征值都不可
   能被 development 读取。
4. **Final Status: PASS WITH REQUIRED MINOR AMENDMENT。** 实现可在应用 R1 的一句话
   澄清（Protocol §2.1 第 2 步 + Sprint §3 镜像，含 poison 测试的两种证据形态描述）后
   开始；R2/R3 建议随实现以测试契约固化（或在同一次微修中一并补入）；R4/R5 无需动作。
   该澄清属文本级钉死、不改变任何已确认规则，无需重开完整双模型评审，建议由所有者
   对修订句做一次 spot-check。
5. 本复审未授权真实数据、full-data training、held-out test 或 `open-test`；Windows/
   synthetic 仍不构成锁定原生 `osx-arm64` 权威证据。
