# Sprint M1-06 Document Review Confirm

**Reviewed Inputs**

- `neural/docs/sprint-m1-06.md`
- `docs/4-Reviews/sprint-m1-06-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-06-review-by-opencode-go-glm-5.2.md`
- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- `neural_adversarial_mlp_refactor_design.md`
- `neural/AGENTS.md` and M1-01 through M1-05 delivery records

**Review Date**

- 2026-09-02

## Overall Conclusion

两份评审共同确认 M1-06 的科学安全边界正确，但 authority full-data comparator 尚未在 Sprint 中给出可执行调用，且 evidence taxonomy、完整 count/cutflow 谓词、source/protocol freeze 与本地配置 ignore 仍不够明确。GLM 的 High finding 成立，但不需要新增第三个产品 CLI：已有 `run_authority_gate` 是完整 application function，可由 runbook 中固定的受控 Python 调用执行，并把 `xb` evidence 写到独立、ignored、全新 authority-evidence path。

文档在应用下表 Accept/Partial 项后可作为实施基线。当前 Windows/AMD64 主机不具备 authority closure 条件；这不阻止先完成文档与本地证据准备，但不能被记录为 M1-06 完成。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Requirement | Kimi Critical | 四份 M1-06 交付文档当前不存在 | Partial | 它们在 Sprint §3/§5.3 中是明确的“待创建实现产物”，在 plan review 时不存在不是 Critical 缺陷；但 Sprint closure 确实要求全部创建 | 在 §3 标注“新建”，实施阶段创建 runbook、artifact schema、evidence 与 final report；不增加 owner/due-date 流程。 |
| 2 | High | Consistency | Kimi High | README 状态停在 M1-04 且缺少 M1-06 文档链接 | Accept | README banner 未反映已提交的 M1-05，也未覆盖最终恢复/审计入口 | 实施阶段更新 banner、完整链路和四份文档链接；authority 未通过时明确 M1-06 blocked。 |
| 3 | Medium | Clarity | Kimi Medium 1 | Sprint 未内联 ROOT/golden hashes 和协议引用 | Accept | 执行人需要跨 FR/design 查找关键绑定值，增加误用风险 | 新增 bound references 表，固定两 ROOT hash、r3 table hash、五项 lineage hash 与协议路径。 |
| 4 | Medium | Risk | Kimi Medium 2 | closure 规则可能把 test-opening 误读为必需 authority gate | Accept | `test_opening` 与 authority classes 相邻，而授权边界要求默认 `not_run` | 明确 test-opening 不是 M1-06 closure 必需项，无授权时 `not_run` 是正确终态。 |
| 5 | Medium | Correctness | Kimi Medium 3 | Windows preflight 写进 plan 会随 authority host 变化而陈旧 | Accept | 当前检查真实为 Windows/AMD64，但 plan 应保持可复用 | 把事实标成 dated preflight，并把执行证据转录到 evidence 文档。 |
| 6 | Low | Consistency | Kimi Low 1 | Sprint 缺 metadata header | Reject | M1-01 至 M1-05 均采用相同无 metadata 的 Sprint 模板，状态由 checklist、§10、review artifacts 和 Git commit 管理 | 保持系列文档一致，不单独引入 owner/version 元数据。 |
| 7 | Low | Clarity | Kimi Low 2 | synthetic/authority CLI smoke 未给出 exact 定义 | Accept | 当前“两个 CLI smoke”与 FR 中两个 `--help` smoke 容易混淆 | 在 §7 分别列出两个 help、synthetic mechanism、authority preprocess/develop 命令与证据类别。 |
| 8 | Info | Documentation | Kimi Info | §10 空白缺少填写约束 | Accept | 计划期应保持空白，但不能预填期望结果 | 增加只可转录实际 authority evidence 或明确 blocked 的说明。 |
| 9 | High | Requirement | GLM F01 | `run_authority_gate` 无明确 executable invocation，pytest module 不会执行全表 gate | Partial | `run_authority_gate` 已完整实现 lineage、逐列 compare、counts、cutflow 和 `xb` evidence；缺陷是 invocation/evidence contract，而非必须新增产品 CLI | 在 Sprint/runbook 固定直接 Python 调用，明确 pytest 仅为 contract/comparator 测试且不足以 closure；evidence 写入独立新 ignored path，并把 gate pass 加入 §6。保持 pyproject 只有两个 console entry points。 |
| 10 | Medium | Consistency | GLM F02 | 平面 evidence label 混合 method/platform/data 且命名不一致 | Accept | `development_only`/`windows_development` 冲突，ARM64 automated test 无准确 label | 改为每条 evidence 的 `method`、`platform`、`data_scope`、`authority` 四字段，并给出允许值表。 |
| 11 | Medium | Requirement | GLM F03 | 只列 selected counts，遗漏 read/split/development/test/duplicates/cutflow | Accept | protocol §7.2 与 gate 固定完整 count 和 cutflow predicates | §5.2/§6 normatively 引用 protocol §7.1/§7.2，并显式列 totals、development/test、duplicates、cutflow。 |
| 12 | Medium | Test | GLM F04 | eligible/no-eligible 两分支被写成同时必过 | Accept | 单个 authority development 只会产生一个科学终态，另一分支已有 synthetic coverage | 改为按实际分支验证，另一分支记 `not_applicable` 并引用 M1-04 synthetic evidence；N/A 不阻塞 closure。 |
| 13 | Medium | Risk | GLM F05 | authority 执行期间未冻结 M1-05 reviewed src/protocol bytes | Accept | 中途科学代码/协议变化会断裂证据链；当前 HEAD `85b67d1` 是已评审实现基线 | authority 前验证 `neural/src` 与 sealed YAML 相对 `85b67d1` 无 diff，记录 HEAD；任何变化先停止、评审、重新规划，不在 run 中热修。 |
| 14 | Medium | Risk | GLM F06 | `preprocess_run.local.yaml` 声称私有但未被 ignore | Accept | `git check-ignore` 当前返回未忽略，绝对 MC ROOT path 可能误提交 | M1-06 增加精确 `.gitignore` 规则并以 `git check-ignore` 验证。 |
| 15 | Low | Consistency | GLM F07 | “两个 CLI smoke”歧义且丢失两个显式 `--help` 命令 | Accept | FR 最小验证的“两 CLI”指两个 console program 的 help；M1-06 又用它表示两类 data smoke | 重命名并在 §7 恢复两个 help 命令，同时单列 synthetic 和 authority commands。 |
| 16 | Low | Clarity | GLM F08 | “无真实数据路径”静态审计没有确定 pass/fail | Accept | protocol 合法包含五个 approved MC lineage path，不能简单禁止所有 `xgboost/runs` 字符串 | 固定 grep-able source/config audit：禁止 `xgboost/src` runtime import/call 与已知 real-data locator/DSID；只允许 protocol 中批准的 MC lineage 与私有两 ROOT 路径。 |
| 17 | Low | Clarity | GLM F09 | Rosetta/native 状态没有固定 probe | Accept | platform enforcement 不等于可复查 evidence | authority host 记录 `platform.system/machine` 和 `sysctl -n sysctl.proc_translated`（0/native；不存在也逐项记录），并由 gate 再次强制 Darwin/arm64。 |
| 18 | Low | Requirement | GLM F10 | 若获授权，test run 未纳入 new/unique/ignored path 规则 | Accept | Test run 同样不可覆盖且必须留 receipt | 补充条件规则；但没有单独明确授权时绝不创建该 path 或执行命令。 |
| 19 | Low | Documentation | GLM F11 | final report 只有措辞要求，没有最小内容结构 | Accept | FR R7 把最终报告列为一等交付物 | 固定 outline：scope/non-claims、sealed methods、evidence boundary、实际 artifact numbers、qualification、test status、blocked gates。 |
| 20 | Info | Consistency | GLM F12 | hashes/contracts/safety cross-check 一致 | Accept | 两份 reviewer 均未发现科学边界冲突 | 保持 MC-only、15 features、frozen predicates、eligibility != authorization。 |
| 21 | Info | Test | GLM F13 | authority host full pytest 应预期零 skip | Accept | M1-05 两个 skip 分别由缺 authority table 和 Windows symlink 能力导致；authority preconditions 满足时均应消失 | authority full suite 要求 zero skips；任一 skip 都诊断并阻塞，不作为通过。 |
| 22 | Info | Documentation | GLM F14 | §10 尚未填写符合 plan 阶段 | Accept | 当前没有 authority artifact，预填会制造证据 | 只在实际 gate 后转录；若外部前置缺失则写 stopped phase/reason 和未执行项。 |

## Needs Immediate Action

- 把 `run_authority_gate` 的直接调用、独立 evidence path 和逐列 golden closure 条件写入 Sprint/runbook。
- 统一多维 evidence taxonomy，补齐完整 counts、duplicates、cutflow 与 outcome-conditional 规则。
- 固定 M1-05 source/protocol freeze、native probe、local config ignore 和 exact smoke commands。
- 创建四份 M1-06 文档并更新 README；最终报告不得预填预期科学结果。

## Can Be Deferred

- 不新增第三个产品 CLI 或 console entry point；现有 application function 的受控直接调用足够。
- 不为 M1-06 单独引入与前五个 Sprint 不一致的 metadata/owner 流程。
- 未获另行明确授权时，`test_opening` 保持 `not_run`，不属于 closure blocker。

## Final Status

**Accepted.** 上述 Sprint 文档阶段的 Accept/Partial 动作均已应用，可进入实现；authority phase 仍必须等待 locked native `osx-arm64`、两个 MC ROOT 与 r3-ARM64 golden table。当前 Windows/AMD64 只能生成非权威本地证据。
