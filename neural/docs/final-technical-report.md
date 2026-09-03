# HiggsML Neural Final Technical Report

## 1. 报告状态与范围

状态：**M1-06 已按用户明确验证豁免完成；authority/full-data 科学全链未验证。**

本项目实现严格 MC-only 的行为等价预处理、固定 15-feature 对抗式 MLP development OOF，以及需另行
明确授权的单次 held-out MC test-opening。当前报告只转录已实际取得的 source/static 与
Windows/synthetic 自动化证据；没有把预注册 expected numbers 写成实际 full-data 结果。

## 2. Sealed 方法

- Preprocess：[`Preprocess Protocol V1`](preprocess-protocol-v1.md) 与
  `config/preprocess_protocol_v1.yaml`；
- Model/training：[`Adversarial MLP Normal Protocol`](adversarial-mlp-protocol-normal.md)、
  [`Development Protocol V1`](development-protocol-v1.md) 与
  `config/adversarial_mlp_protocol_normal.yaml`；
- Test-opening：[`Test-opening Protocol V1`](test-opening-protocol-v1.md)。

Classifier 只允许固定 15 features。`m4l`、identity、provenance、split、physical/train weight 均不是
classifier inputs。Eligibility 由冻结 development OOF 规则决定，但永远不等于 test-opening 授权。

## 3. 已取得的证据

命令、平台、data scope、authority 属性和 exit code 的唯一转录见
[`M1-06 Verification Evidence`](m1-06-verification-evidence.md)。本地 Windows/AMD64 实际结果为：

- scientific `src/` 与两个 sealed protocol YAML 相对 M1-05 commit `85b67d1` byte-identical；禁止的
  `xgboost/src` runtime reference 和两个已知真实数据 locator/DSID 静态审计无命中；
- 精确 local run config ignore 与两个 console entry point 通过；
- `pip check` 与两个 CLI help 均 exit 0；
- focused synthetic mechanism suite：`23 passed`；test-only authority orchestration contract：
  `4 passed, 1 skipped`；
- final full local suite：`228 passed, 2 skipped`；skip 分别为外部 r3-ARM64 table 缺失和 Windows directory
  symlink 不可用。

这些结果的 `authority=false`，不提供 full-data preprocess 或 development scientific outcome。两份实现
review 均确认安全边界，Accept/Partial 修订只增加测试与文档精度，没有改变 frozen runtime source 或
sealed protocol。

## 4. Authority 阻塞与未运行项

当前执行主机为 Windows/AMD64，不满足 locked native `osx-arm64` authority host gate。因此以下 required
closure gates 均未运行：

- 由 `osx.yml` 恢复并验证的原生 authority environment 与 zero-skip full pytest；
- 两个批准 MC ROOT 的 full-data preprocess；
- 对批准 r3-ARM64 golden table 的 application-level `run_authority_gate`；
- 五候选五折完整 development OOF 和其实际 qualification 终态。

这些项不能由 Windows、synthetic fixture、pytest comparator contract 或 CLI help 替代。用户于
2026-09-02 明确要求“不要求 test，完成 M1-06，并提交”，因此接受上述验证保持 `blocked`/`not_run`
并豁免其 Sprint closure/commit gate。该验收例外不改变证据等级，也不表示上述 authority gates 通过。

## 5. Qualification 与 test-opening

Authority qualification：`not_run`。没有实际 full-data development artifact，因此没有 selected lambda、
模型、工作点或实际 OOF 指标可报告。

Authority test-opening：`not_run`。用户未对任何具体 eligible frozen development run 给出另行明确授权，
也未创建 test run 或 claim。`open-test` 不是 M1-06 closure 必需 gate；即使未来 development eligible，
也只能记录“可申请授权”，不能自动开启。

## 6. 恢复路径

在可用的原生 `osx-arm64` host 上按 [`runbook.md`](runbook.md) 从 environment preflight 重新开始，使用
全新 ignored run paths，并把实际 artifact/hash/exit code 转录到 evidence。本地 scientific source 与
两个 sealed protocol YAML 必须先相对 reviewed M1-05 commit `85b67d1` 保持 byte-identical。

## 7. Non-claims

本实现和全部输出仅为 educational/technical demo。它们不构成 ATLAS 结果，不构成 Higgs discovery，
也不构成 physics measurement。当前没有权威 full-data 科学结论；Sprint 完成只表示用户接受本次
交付和未验证边界。
