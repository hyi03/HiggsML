# Sprint M2-01

## 1. Sprint 目标

交付 [FR-SE-02](../../1-Requirement/Done/FR-SE-02-deterministic-training-subsets.md)，完成开发计划M2的软件范围。

## 2. 前置依赖

M1 commit `7f21ad4`、prepared `research-run-v1`、identity-first events格式及FR-SE-01算法契约。

## 3. 纳入范围

`src/research/training_subsets.py`、`tests/research/test_training_subsets.py`、`docs/sw-dev/artifact-schema.md`（文件/schema/status/receipt/reader职责）。

## 4. 暂不纳入范围

M3—M7；正式ROOT数据和科学结论。

## 5. 工作范围

### 5.1 Identity-first计划与发布

- [x] 两阶段读取：严格验证全部identity，仅解码train payload的weight/m4l；永不解码assessment/其他角色payload。
- [x] 实现分层哈希、嵌套前缀、full规范化、稳定ID和摘要。
- [x] 以ResearchRun发布三个payload及完整upstream绑定。

### 5.2 Reader与失败语义

- [x] reader重算membership、summary、ledger、嵌套和协议绑定。
- [x] 覆盖低统计终态、篡改、角色/label冲突、行序变化和assessment poison。

## 6. 验收标准

满足FR全部验收点；三表示可共享一个subset ID；不访问assessment payload。

## 7. 验证要求

在neural/pytorch运行focused test、pip check、完整pytest。Windows synthetic不代替ARM64/ROOT。

## 8. 实施顺序

文档双评审/确认→实现→代码双评审/确认→修复→验证→单独提交。

## 9. 风险控制

不把identity envelope当科学特征输入；manifest receipt负责文件字节信任，reader负责内容语义重算。保留根AGENTS.md用户修改并排除提交。

## 10. 交付结论

当前阶段：完成。文档双评审与 `../../4-Reviews/sprint-m2-01-review-confirm.md`、代码双评审与 `../../4-Reviews/sprint-m2-01-code-review-confirm.md` 均已完成，接受项已落实。验证结果：扩展 focused 113 passed；`python -m pip check` 无依赖冲突；全量 661 passed、60 warnings。结果来自 Windows synthetic 软件验证，不替代 ARM64 authority、完整 ROOT 或科学数值验证。提交消息固定为 `feat: complete sprint-m2-01 code and change base on reviews`。
