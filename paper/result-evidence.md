# h4l-off-test01 论文结果证据索引

核对日期：2026-09-21。本文索引仅记录已发布受控 MC 产物，不包含原始事件。

当前代码：`e066bae9a12e5bd2d02cd199bbd09a99151ea6d7`。Asimov/freeze 代码：`3819547357354aa04fa2dd85e1da3afeeaeb8ffb`。最新恢复报告代码与当前代码相同。当前源码核对不构成对旧产物重新运行，也不证明跨版本数值恒等。

选定报告：`runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e`。artifact ID：`9c2413c8e5582e967b54f5a046883d5510143873941d6a53f320813297d47d68`。原 evaluation/report 是早期不完整快照，不作为本稿最终汇总。

冻结 ID：`aa8767f7f31688e8f6d501158a2e20d1ea0993abd83ae7f3f416f425045fe2ed`；protocol SHA-256：`e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e`；prepared artifact：`fb23c098d5279533609f52ee41e7fa9ff0ea99071ea948f26c14bfa9721fa611`。

## 数值提取规则

W68/AUC 按组合分别取五种子中位数；直接比较先配对再取中位数。Shapley/交互区间来自种子枚举，不能标成事件 MC 区间。覆盖取 five_seed_descriptive_diagnostics.csv 的 conditional_coverage；T2 的单位是外层 calibration 副本。bootstrap 的失败来源取 evaluation.json 的 candidate_states，不将非完整副本补齐。

## 五种子原始 W68

| 组合 | 42 | 43 | 44 | 45 | 46 |
|---|---:|---:|---:|---:|---:|
| BC | 1.51960396877934 | 1.51161685213344 | 1.5105965295417 | 1.51597864926882 | 1.51145040192357 |
| AC | 1.50893048527358 | 1.5152443015333 | 1.51605457849435 | 1.51785444797728 | 1.49719669168701 |
| ABC | 1.51826817757978 | 1.51530574476585 | 1.53042492691506 | 1.52304627860221 | 1.52115682688763 |
| BCD | 1.52591285353842 | 1.5244590238933 | 1.52837905089679 | 1.51019914627426 | 1.52078080478481 |
| ABCD | 1.53544151230838 | 1.52946504667538 | 1.53796772738576 | 1.53592965961348 | 1.54804721455072 |
| B | 1.55765038438651 | 1.56503799292023 | 1.56717805252157 | 1.55510237970175 | 1.56018736539633 |
| BD | 1.55559297573123 | 1.5570149293342 | 1.56183195932591 | 1.57418724295757 | 1.56135681102588 |
| ABD | 1.56435478718173 | 1.5959624831269 | 1.5736834003749 | 1.56857929268128 | 1.58874260867139 |
| AB | 1.56869242944756 | 1.56764488659016 | 1.57773992292546 | 1.57596703891602 | 1.58393663551321 |
| ACD | 1.5782756580223 | 1.58872490016283 | 1.52953818097632 | 1.52236475679 | 1.58812642518875 |
| C | 1.59192032394869 | 1.59156820889558 | 1.59270258098424 | 1.59288481529267 | 1.59186740081006 |
| CD | 1.60735541635802 | 1.59236226921819 | 1.5862078537808 | 1.60008583225044 | 1.60403707528464 |
| A | 1.6312609218253 | 1.62289134666304 | 1.61516618377473 | 1.63115131728033 | 1.62210525664141 |
| AD | 1.63054001364387 | 1.62260178357744 | 1.63507855945457 | 1.6260705651314 | 1.62897198811098 |
| D | 1.66296879298478 | 1.66068116788856 | 1.65531235613924 | 1.65387303948034 | 1.65907550213894 |
| M0off | 1.66372283629151 | 1.66372283629151 | 1.66372283629151 | 1.66372283629151 | 1.66372283629151 |

## 源码对应

| 契约 | 当前源码 |
|---|---|
| 特征输入顺序 | [representations.py](../src/higgsml/modeling/representations.py) |
| 80 个身份、种子枚举、归因和排序 | [attribution.py](../src/higgsml/inference/attribution.py) |
| bootstrap 失败和误差范围 | [bootstrap.py](../src/higgsml/inference/bootstrap.py) |
| 人工 CRN 及 primary_claim_eligible=false | [marginal_coupling.py](../src/higgsml/inference/marginal_coupling.py) |
| 36 单元、T2 外层汇总、报告字段 | [marginal_workflow.py](../src/higgsml/inference/marginal_workflow.py) |
| 默认自审编排 | [h4l_all.py](../scripts/h4l_all.py) |

知识图对当前 marginal 模块检索不充分，因此直接核对以上当前文件。`support=[]` 和空 marginal_support.csv 不表示 J0/J1 未运行；已另查两份 passed 产物。报告的 assessment_source_status=pending_access_review 是当前报告生成逻辑的粗粒度状态，独立性以实际 receipt 的 independent=false 为依据。

## 校验范围

对以下 31 个已发布文件核对 manifest 中的字节数与 SHA-256，均一致；核对 Asimov 80 条记录与最新 CSV 完全对应，重新计算全文组合中位数、配对量和覆盖表。此校验不包括原始 ROOT、全部训练 checkpoint 或全部历史 upstream 的递归验证，不构成独立物理审计。没有执行软件测试套件或重新运行科学实验。

| 已核对文件 | SHA-256 |
|---|---|
| [evaluation/report-resume-6f5909a8b7f58d5e/candidate_fit_status.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/candidate_fit_status.csv) | `e82b3e10958c097c3d42e5db20610c3667c57581fba45db19decd3ea5de48f2c` |
| [evaluation/report-resume-6f5909a8b7f58d5e/data_dictionary.json](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/data_dictionary.json) | `74289a8b65905bdef95a77511a93e8c32dfd34fe3e864de881e6e6bf4d709d60` |
| [evaluation/report-resume-6f5909a8b7f58d5e/evaluation_completeness.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/evaluation_completeness.csv) | `7c0de7713d9a23d058fe22b42be1ddd048f4978c443f8b16917c63c02f3bf6b0` |
| [evaluation/report-resume-6f5909a8b7f58d5e/five_seed_descriptive_diagnostics.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/five_seed_descriptive_diagnostics.csv) | `a25b2427093870ec4427f214a3827956a1bb79a73ed66e5bd541ecc56c79b926` |
| [evaluation/report-resume-6f5909a8b7f58d5e/marginal_support.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/marginal_support.csv) | `7703741f562b3f2c276fc35a9aba6f2de114df21e80f56ebf257cdb5ea03115c` |
| [evaluation/report-resume-6f5909a8b7f58d5e/mass_off_feature_attribution.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/mass_off_feature_attribution.csv) | `8874c673fd1f5f7a48e03abd6887ba799ce9a5933a369d2d1fa69f7e028b8a52` |
| [evaluation/report-resume-6f5909a8b7f58d5e/mass_off_feature_interactions.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/mass_off_feature_interactions.csv) | `aa9ee26f98795768364ae6a4eb5ccf98cf6d3f77138f979023ba6ffc2808e24c` |
| [evaluation/report-resume-6f5909a8b7f58d5e/mass_off_feature_metrics.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/mass_off_feature_metrics.csv) | `b23739c6bacae918ac465c160796b60f3cf0ee241cda47544d5af8965877c743` |
| [evaluation/report-resume-6f5909a8b7f58d5e/mass_off_pairwise_comparisons.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/mass_off_pairwise_comparisons.csv) | `359b64dd90b083494f1a1d5a12f88dac29cac530b428662cabffde397da86172` |
| [evaluation/report-resume-6f5909a8b7f58d5e/mc_bootstrap_uncertainty.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/mc_bootstrap_uncertainty.csv) | `06dae030de94a11b50de0771cf7f8d3f92dd1f76e337f5cb2b83e448fdec9695` |
| [evaluation/report-resume-6f5909a8b7f58d5e/protocol.json](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| [evaluation/report-resume-6f5909a8b7f58d5e/provenance.json](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/provenance.json) | `9388e20874491d2952523d126c22afef9ca8127dab892417c863fdc5955e4abd` |
| [evaluation/report-resume-6f5909a8b7f58d5e/report.json](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/report.json) | `25d69f33a393c06c0a533883df43959d95dfb964b208f3568c4f3f63bce26029` |
| [evaluation/report-resume-6f5909a8b7f58d5e/report.md](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/report.md) | `03f5895d3c15f15f3c5b0ee808def5066e9d546ef7e40fb69df99b0890972e33` |
| [evaluation/report-resume-6f5909a8b7f58d5e/seed_block_status.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/seed_block_status.csv) | `7c0de7713d9a23d058fe22b42be1ddd048f4978c443f8b16917c63c02f3bf6b0` |
| [evaluation/report-resume-6f5909a8b7f58d5e/seed_descriptive_diagnostics.csv](../runs/h4l-off-test01/evaluation/report-resume-6f5909a8b7f58d5e/seed_descriptive_diagnostics.csv) | `63cb0b66dc1e51f2a8adbfc0bf00d5c226cb4662e90c45db60e2d9c84999839b` |
| [asimov/binding.json](../runs/h4l-off-test01/asimov/binding.json) | `202a0f570dc295c1cbebf2530b8bb758ab3d5fd897bdfe5106b2051427d41f0c` |
| [asimov/inference.json](../runs/h4l-off-test01/asimov/inference.json) | `dea098d8caab0f3186a2501b987456d8df34cb8f6f94bb5f917eb991dbb2d71b` |
| [asimov/protocol.json](../runs/h4l-off-test01/asimov/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| [asimov/summary.json](../runs/h4l-off-test01/asimov/summary.json) | `23d5e9648a37a7849f2c86bf814f9998f4b794a9ee3fa690aa6644f05c04be25` |
| [freeze/freeze.json](../runs/h4l-off-test01/freeze/freeze.json) | `38daf2d1bf970b0589a1d42120b26e9c0ed024920e9d81a0ca3178bb3014133b` |
| [freeze/protocol.json](../runs/h4l-off-test01/freeze/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| [access-review/protocol.json](../runs/h4l-off-test01/access-review/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| [access-review/validated-off-assessment-access.json](../runs/h4l-off-test01/access-review/validated-off-assessment-access.json) | `b15afe67039ff9b67a2d317288edde92623d1e48ca1463fe838e44b3cce3b166` |
| [support-j0/marginal-rates.jsonl](../runs/h4l-off-test01/support-j0/marginal-rates.jsonl) | `92ea40b5327ec33f96716955606c5e48488423310612946c9233112ef3d65c34` |
| [support-j0/marginal-support-summary.json](../runs/h4l-off-test01/support-j0/marginal-support-summary.json) | `0ec50737ff12109a9a2a6b8029c36c69a90b8c71c139ebb7cd4105f8e8f716ae` |
| [support-j0/protocol.json](../runs/h4l-off-test01/support-j0/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| [support-j1/marginal-support-summary.json](../runs/h4l-off-test01/support-j1/marginal-support-summary.json) | `8cf76799f82e07c3ee788ed937fc859735c284a9b878367155f0014de07336d7` |
| [support-j1/protocol.json](../runs/h4l-off-test01/support-j1/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |
| [evaluation/mc-bootstrap-mu1/evaluation.json](../runs/h4l-off-test01/evaluation/mc-bootstrap-mu1/evaluation.json) | `faeed79408025ba080f89b01d238d270a4bbfee64079ce078137afe345783406` |
| [evaluation/mc-bootstrap-mu1/protocol.json](../runs/h4l-off-test01/evaluation/mc-bootstrap-mu1/protocol.json) | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |

## 当前代码汇总复核

以当前 attribution.summarize 读取已有 80 条 Asimov 记录重新计算 4 个 Shapley、24 个交互和 105 个配对比较，与原冻结 summary 在 rtol=atol=1e-12 下相符。最大逐种子效率残差为 0.0。这只复核汇总代数，不重拟合似然，也不补足有限 MC 或独立验证。正文 15 个非空子集 W68/AUC 的显示舍入和 paper 全部本地链接均已检查。
