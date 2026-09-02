# Sprint M1-04 Review Confirm

**Reviewed Inputs**

- `neural/docs/sprint-m1-04.md`
- `neural/docs/development-protocol-v1.md`
- `docs/4-Reviews/sprint-m1-04-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-04-review-by-opencode-go-glm-5.2.md`
- `AGENTS.md`、`neural/AGENTS.md`、FR-001、已确认设计与当前 M1-03 实现

**Review Date**

- 2026-09-02

## Overall Conclusion

两位 reviewer 均确认文档的科学规则、安全边界和 FR 映射正确。Kimi 报告把大量明确列在
Sprint checklist 中的“待实现项”提高为当前 Critical/High 缺陷；这些事实成立，但不是
pre-implementation 文档缺陷。GLM 的两项 High 指出真正需要在实现前补清的 contract：two-stage
reader 必须是唯一持久输入入口，以及 M1-04 JSON 必须使用与旧 helper 分离的确定性编码。

文档可在下表 Accept/Partial 的澄清全部应用后作为实现基线；任何 implementation gap 都不得以
“文档已通过”为理由跳过。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Security | `Kimi K1` | 现有 DataFrame validator 不能证明 test token 未被解码 | Partial | M1-04 尚无持久 reader，故不存在已上线的泄漏路径；但绕过风险真实 | 明定 `development_reader.py` 为唯一入口，禁止外部直接构造 `ValidatedDevelopment`，实现 malformed test-token poison test。 |
| 2 | Info | Requirement | `Kimi K2` | folds/qualification/development/plots 等模块不存在 | Reject | Sprint §5 正是创建这些模块，且 checklist 未勾选 | 不是文档缺陷；实现阶段逐项创建并测试，完成前不得关闭 Sprint。 |
| 3 | Medium | Consistency | `Kimi K3` | YAML 尚无五个 M1-04 sealed blocks | Partial | Protocol §3 已把添加 blocks 列为实现任务 | 在文档补充 `_EXPECTED` 同步要求；实现时同时修改 YAML、loader 与 mutation tests。 |
| 4 | Info | Requirement | `Kimi K4/K9` | 尚无 stable fold assignment | Reject | 两条为同 reviewer 的 exact duplicate，Sprint §5.1 已明确待实现 | 保留为实现门，不把 pre-implementation 状态误判为文档 blocker。 |
| 5 | Info | Requirement | `Kimi K5` | qualification/working-point 尚未实现 | Reject | Sprint §5.2 与 Protocol §6–7 已给出待实现规则 | 实现阶段完成；文档无需因代码尚未开始而返工。 |
| 6 | Info | Requirement | `Kimi K6` | final fit 尚未实现 | Reject | Sprint §5.3 与 Protocol §8 明确待实现 | 实现阶段新增 fixed-epoch final fit。 |
| 7 | Info | Requirement | `Kimi K7` | CLI develop 尚未实现 | Reject | Sprint §3/§7 明确此交付，当前 placeholder 符合顺序门 | 实现阶段添加子命令与 exit-code tests。 |
| 8 | Info | Test | `Kimi K8` | M1-04 test modules 不存在 | Reject | Sprint §7 把它们列为将创建的专项 tests | 不构成文档缺陷；代码评审前必须存在并通过。 |
| 9 | Medium | Clarity | `Kimi K10` | reader 与 orchestrator 模块边界不明确 | Accept | Sprint 只写“development.py 与 reader” | 固定 `development_reader.py` 负责 input binding/route/decode，`development.py` 只负责编排与发布。 |
| 10 | Info | Requirement | `Kimi K11` | 尚无 OOF canonical writer | Reject | Protocol §5 已精确定义待实现 schema/order/hash | 实现门保留，不需要把未实现状态写成文档错误。 |
| 11 | Info | Requirement | `Kimi K12` | 尚无 development artifact writers | Reject | Protocol §9 和 Sprint §5.3 已明确待实现 | 实现时创建并由 manifest/hash tests 验证。 |
| 12 | Info | Requirement | `Kimi K13` | 当前 dataset API 未绑定 preprocess run | Reject | dataset 是 M1-03 in-memory primitive，不是 M1-04 持久 reader | 新 input binder 负责 run binding；不把路径职责塞入 dataset。 |
| 13 | Medium | Test | `Kimi K14` | 现有 poison DataFrame 不能证明 CSV test token 未解析 | Accept | M1-03 test 只覆盖 validator access order | M1-04 增加 gzip streaming poison row，并覆盖 decoder→validator→trainer→metric→plot。 |
| 14 | Low | Clarity | `Kimi K15` | 应明确 train+validation 合并 | Reject | Protocol §2 已原文写明合并且不保留决策区别 | 已满足，无重复修改。 |
| 15 | Info | Documentation | `Kimi K16` | Sprint 结论仍是 placeholder | Reject | 实现前 placeholder 是真实状态 | 只在代码评审修订和最终验证后填写。 |
| 16 | Info | Security | `Kimi K17` | MC-only/test boundary 正确 | Accept | 与两级 AGENTS 及 FR 一致 | 保留原文并在 manifest/最终记录中提供证据。 |
| 17 | Info | Consistency | `Kimi K18` | fold/threshold/tie 规则与 FR 一致 | Accept | FR-001 R4 与设计 §9 支持 | 保持 exact 值，不运行时扩展或放宽。 |
| 18 | High | Security | `GLM F1` | two-stage reader 未明确为 sole entry point | Accept | 直接 pandas load 可在 validator 前物化 test feature | 明定唯一入口与构造权限；persistent flow 禁止调用公开 DataFrame loader 绕过。 |
| 19 | High | Consistency | `GLM F2` | compact/sorted JSON 与现有 `json_bytes` 冲突 | Accept | 旧 helper 是 indented/unsorted，修改会扰动 M1-02 bytes | 新增 M1-04-only `canonical_json_bytes`；qualification、working points、development manifest 均用 sorted compact UTF-8 + LF，旧 helper 不变。 |
| 20 | Medium | Clarity | `GLM F3` | 未显式说明同步 `_EXPECTED` | Accept | 当前 loader exact 比较会拒绝新增 YAML keys | Sprint/Protocol 点名更新 `_EXPECTED` 及其 mutation tests。 |
| 21 | Medium | Clarity | `GLM F4` | fold_metrics 每 epoch 与 fold summary 放置含糊 | Accept | 当前未给 exact 列序和重复规则 | 写出 exact 列序；fold summary fields 在该 fold 每个 epoch row 重复。 |
| 22 | Medium | Requirement | `GLM F5` | input symlink/reparse 检查的 owner 不清 | Accept | `RunTransaction` 只负责 output，不应混入 input binding | 由 `DevelopmentInputBinder` 逐 component 拒绝 symlink/junction，RunTransaction 保持 output 职责。 |
| 23 | Medium | Consistency | `GLM F6` | design tree 未列 development module | Accept | 新模块是 M1-04 的必要 orchestration seam | 在已确认设计的工程树中补 `development_reader.py` 与 `development.py`，不改变科学架构。 |
| 24 | Medium | Clarity | `GLM F7` | trainer.py 的 M1-04 变化未说明 | Accept | final fit 与 early-stopped train_fold 不同 | 明定新增 `train_fixed_epochs`，无 validation/checkpoint/early stop；scaler 仍由 dataset/development 层拟合。 |
| 25 | Low | Clarity | `GLM F8` | source_entry=0 编码可误读 | Accept | 单独 `0` 不是 redundant leading zero | 增加文字和 known vector 测试要求。 |
| 26 | Low | Documentation | `GLM F9` | threshold 缺手算例 | Accept | full score tie 会使 achieved efficiency 超过 target | 加入 4-row、target 0.20、threshold 0.8、achieved 0.40 的例子。 |
| 27 | Low | Clarity | `GLM F10` | preprocess protocol/config hash 算法隐含 | Accept | §2 只写“以 hash 引用” | 明定对文件 payload bytes 计算 SHA-256。 |
| 28 | Low | Consistency | `GLM F11` | final fit seed 42 未回写设计 | Accept | 是 base seed 的合理、无搜索 narrowing | 在设计 §8.5/§9.4 明记 final fit seed 42。 |
| 29 | Low | Clarity | `GLM F12` | OOF 不单列 absolute weight | Accept | §6 已要求由 signed physical_weight 取 abs | 明定运行时派生、不得持久化冗余列或误用 signed/train weight。 |
| 30 | Low | Clarity | `GLM F13` | 流式 hash 与 test token 数值解码边界易误读 | Accept | 字节传输不可避免，但 typed parse 禁止 | 明定 hash 仅消费 bytes，不定位、解码或物化 test feature tokens。 |
| 31 | Info | Documentation | `GLM F14` | Sprint 结论 placeholder | Reject | 与 Kimi K16 相同且符合 pre-implementation 状态 | 收尾时再填写。 |
| 32 | Info | Consistency | `GLM F15` | M1-04 不创建 test_opening.json 是正确 scope | Accept | M1-05 才拥有 claim/receipt | 保持不创建任何 state placeholder。 |
| 33 | Info | Consistency | `GLM F16` | 禁止 runtime 使用 xgboost 是合规 narrowing | Accept | neural/AGENTS 要求 runtime independence | 保持，仅允许文档期只读行为核对。 |
| 34 | Info | Clarity | `GLM F17` | fold SHA-256 与 preprocess blake2b 可混淆 | Partial | 两者职责不同且无冲突，但一行区分可防误实现 | Protocol §3 加明确区分说明。 |
| 35 | Info | Documentation | `GLM F18` | Sprint 依赖未链接 preprocess protocol | Accept | M1-04 input binder 直接依赖 M1-02 manifest/schema | Sprint §2 增加链接。 |
| 36 | Info | Test | `GLM F19` | poison test 应覆盖五个组件 | Accept | Protocol §10 已列出，但需落实 | 实现时使用 spy/poison 证明各组件只收到 development rows。 |
| 37 | Info | Consistency | `GLM F20` | best-AUC-relative tie 是正确 narrowing | Accept | 避免 pairwise chain 非传递且不放宽 `1e-6` | 保持，无修改。 |

## Needs Immediate Action

- 在实现前应用 rows 1/3/9/13/18–30/34–35 的文档澄清。
- 实现阶段完成所有仍未实现的 M1-04 checklist；文档通过不等于代码通过。

## Can Be Deferred

- Sprint §10 的结论只在最终验证后填写。
- `state/test_opening.json` 及任何一次性 claim 继续留给 M1-05，M1-04 不创建占位物。

## Final Status

**Accepted after confirmed document revisions.** 上述澄清已应用，可进入实现；所有
implementation gaps 仍是本 Sprint 的强制门。不得读取真实数据、不得打开 held-out test、不得
执行 `open-test`。
