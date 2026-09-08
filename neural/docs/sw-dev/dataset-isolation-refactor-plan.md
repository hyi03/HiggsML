# Neural 按数据集严格配套的重构方案

状态：软件实现已落地，最终验证见 [dataset-v2-verification.md](dataset-v2-verification.md)。日期：2026-09-05。

本文保留实施前分析；第 2 节为重构前快照。A–D、F 已实现，E 的 Windows 全量预处理另记结果，ARM64 权威验证与正式 development/test 尚未完成。

适用范围：`D:\code\HiggsML\neural`，以及仓库共享下载入口 `scripts/init_data.py`。本文定义实现和验收边界。执行期间仅在新路径运行 MC 预处理及合成测试，不修改冻结或失败 run，不改动 `xgboost` 实现。

## 1. 目标与决定

将“两个可随意指定路径的样本”改为“一个受控、不可拆分的数据集配对”。下载、预处理、development 训练、test-opening 必须使用同一数据集身份。目录名称用于组织文件，协议和内容哈希用于证明身份。

本轮只注册两种数据集；统一参数名为必填的 `--dataset`，不同时引入 `--dataset-pair` 别名：

| 数据集名称 | Release / collection | Higgs | ZZ | 输入事件数 Higgs / ZZ | 约计大小 Higgs / ZZ |
|---|---|---:|---:|---:|---|
| `atlas2020_4lep` | 2020 / `4lep` | 345060 | 363490 | 164,716 / 554,279 | 50.52 / 179.08 MB |
| `atlas2025_exactly4lep` | 2025 / `exactly4lep` | 345060 | 700600 | 419,943 / 11,260 | 182.05 / 5.41 MB |

这些数量来自本次任务提供的已核实上下文，是上游输入数量，不是本项目 selection 后数量。MB 是展示值，不能代替下载校验所需的精确字节数。新方案的选后数量、有效样本量、OOF 和 test 指标均尚未知。

2025 `4lep` 不进入本轮下载和 CLI 白名单。此前对其优先级的讨论不改变本次明确要求；将来增加它必须单独登记、验证，不能与 `exactly4lep` 拼接。两种 collection 大量重叠。

核心决定：

1. 原始文件存放于仓库 `data/raw/<dataset>/`；一次初始化默认下载两套配对的四个 MC 文件。
2. 三个业务命令均显式指定数据集；训练、test 中该参数是身份断言，不能用于重标记上游数据。
3. 删除新运行链中的混用常量、旧路径回退和默认样本推断。旧协议、历史文档和冻结基准只作为历史证据保留。
4. 通用加载器负责 schema 和绑定校验，受控数据集定义负责文件身份，profile 负责 branch 和单位映射，科学协议负责选择、特征、权重及训练规则。
5. 两套新数据各自重新预处理和训练，建立独立验证证据。旧混用的 199,104 行不能作为新配对的 golden。
6. 不同时调整物理选择、15 个分类器特征、网络、候选 λ、epoch 规则、AUC/KS 或效率门槛。所有结果仍限于 educational/technical demo。

## 2. 当前实现核查

核查使用知识图谱定位，再读取当前工作区源码。图谱存在部分旧签名，因此实际文件内容为准。未读取 ROOT、canonical 事件表或模型；历史产物数值沿用用户提供的上下文，不宣称本次重新验证。

| 当前位置 | 已确认行为 | 对重构的影响 |
|---|---|---|
| `scripts/init_data.py` | `DATASETS` 写死新版 Higgs 与 2020 ZZ；平铺到 `data/raw`；Higgs URL 按 DSID 和大小解析 | 必须改成配对目录和精确 collection/file key 绑定；只改文件名不足以消除混用 |
| `src/config.py` | `load_preprocess_protocol` 对整个 v1 样本字典做固定值比较；`_HIGGS_BRANCHES` 为 release22，`_ZZ_BRANCHES` 为 2020；golden 也写死 | YAML 修改会被拒绝；须拆分受控数据定义、profile、科学协议、验证基准 |
| `config/preprocess_run.example.yaml` | 允许分别给 Higgs/ZZ 任意路径，默认平铺旧目录 | 改为数据根路径与资源配置，不再允许用户独立拼装样本 |
| `src/preprocessing/root_reader.py` | 已按 sample 的 tree/branches 读取，但 entry count 在遍历结束后验证 | 可复用分块读取；增加读取前元数据校验，分离 profile 与 label |
| `src/preprocessing/pipeline.py` | 逐样本哈希、重建、权重、split；按 `source_sample + source_entry` 唯一；发布单表 | 需要完整绑定对象、分区产物和新版 manifest；DSID 应逐条尽早拒绝 |
| `src/domain/selection.py` | 逐级过滤后要求恰好四个 good leptons | 保留；上游 `exactly4lep` 不等于项目选择，不能跳过 ID、隔离或质量窗 |
| `src/domain/splitting.py` | 对 `channelNumber:eventNumber` 作 BLAKE2b，6:2:2 | 同一键已有稳定 split；须明确跨 collection 的物理事件分组及碰撞处理 |
| `src/training/folds.py` | 对 `source_sample + NUL + source_entry` 作 SHA-256 五折 | 文件行号不是跨 collection 的物理身份，须改为物理分组键 |
| `src/training/development_reader.py` | manifest 限定 preprocess v1；校验整表哈希，gzip 逐行取 split 后才解码 development | 身份契约需升级；当前能声明“不解码 test 特征”，不能声明“不读取 test 文件字节” |
| `src/training/dataset.py` | development schema/数值/split 校验完整，但未校验受控样本名与 label、DSID 的全组合 | 应传入已验证数据集绑定，拒绝未知样本及错误标签 |
| `src/training/test_reader.py` | 样本白名单及 label 映射写死为 345060/363490 | 必须从同一个绑定对象获得，不能只给白名单增加 700600 |
| `src/training/config.py` | 固定输入列、fold 算法名、checkpoint 和 OOF 字段 | 新身份字段、fold 与产物 schema 必须版本化，不能修改旧协议原文 |
| `src/training/test_opening.py` | 严格验证 manifest、模型、阈值和上游输入；支持可选 authorization reference | 需同步更新所有严格 key 集合、模型载荷和 lineage，数据集不匹配必须在 claim 前拒绝 |
| `src/preprocessing/authority.py` | 固定 v1 协议路径、旧样本名称、旧 golden 与全表比较 | 新数据集使用独立证据；开发阶段不可直接调用全表特征比较 |

当前正式产物 `runs/preprocess-01/artifacts/` 的 Higgs/ZZ 选后数量为 187,128/11,976，development 为 149,792/9,603，ZZ 绝对权重有效样本量约 6,412。这些均标记为历史混用基准。不能把其中的 ZZ 保留率直接套用到 2025 的 700600。

## 3. 数据定义与协议结构

建议新增以下结构，避免下载器和 neural 各维护一份文件哈希常量：

```text
neural/
  config/
    datasets/
      atlas2020_4lep.json
      atlas2025_exactly4lep.json
    profiles/
      open_data_2020.yaml
      release22.yaml
    preprocess_protocol_v2.yaml
    adversarial_mlp_protocol_normal_v2.yaml
    adversarial_mlp_protocol_debug_v2.yaml
    preprocess_run.example.yaml
    validation/                         # 新数据集验证证据的受控引用
  src/
    data_contract.py                     # 新增：标准库实现的数据定义加载与绑定
    config.py                           # 组合 profile、科学协议和运行配置
```

数据清单使用 JSON，使根下载器继续可以仅用 Python 标准库运行；它与 neural 共用 `data_contract.py`，不导入训练、ROOT 或 `xgboost` 包。根脚本按自身绝对位置加载该模块，不依赖调用时 cwd 或另一个工程的 `src` 导入顺序。打包配置需包含这些受控资源，并测试从非仓库 cwd 加载。

每个定义必须绑定下列字段，字段集合和取值严格校验：

| 层级 | 必需字段/语义 |
|---|---|
| 数据集 | `schema_version`、`dataset_name`、`definition_revision`、release、collection、`mc_only: true`、成员集合、允许的协议/profile 引用 |
| 样本 | role、label、DSID、source sample、profile ID、生成样本/production 身份、归一化定义 |
| 文件 | 稳定 `file_id`、上游 record URL、精确 file key、下载 URL、文件名、精确大小、SHA-256、tree、entry count、release、collection |
| 归一化 | 参数来源及版本、截面单位、截面是否已含 k-factor/filter efficiency、完整生成样本 sum of weights 及其适用范围 |
| 重叠身份 | `event_identity_policy_id`、已证实的生产样本对应关系；不以相同 DSID 自动断言跨 release 事件等价 |

当前每个配对只允许一个 Higgs 文件和一个 ZZ 文件。将来分片可扩展文件列表，但重复文件哈希、重复 file ID 和物理重叠必须拒绝或按预注册规则处理，不能隐式多加一份权重。

`DatasetBinding` 为不可变对象，包含定义原始字节 SHA-256、profile 字节 SHA-256、科学协议 SHA-256、schema 和身份策略版本。CLI、pipeline、reader、模型发布均传递这一对象，不在下游重新按名字猜测定义。

通用不代表任意 YAML 均可运行：运行配置只能改路径/资源；受控定义须匹配随代码发布的名称、修订和摘要白名单。增加/修订定义需要版本化代码及测试变更；下载过程不能把观测值自动写回白名单。快照是复现证据，不能只保存一个将来可能被修改的路径。

## 4. 下载与原始目录

下载器的独立实施计划见 [init_data.py 数据集下载重构 Plan](init-data-refactor-plan.md)，涵盖函数改动、数据定义、并发与失败恢复、测试和交接边界。本节保留全链需要的目录及接口概要；下载器可先独立实施，下游适配仍按本文推进。

```text
data/raw/
  atlas2020_4lep/
    mc_345060.ggH125_ZZ4lep.4lep.root
    mc_363490.llll.4lep.root
    dataset_receipt.json
  atlas2025_exactly4lep/
    ODEO_FEB2025_v0_exactly4lep_mc_345060.PowhegPythia8EvtGen_NNLOPS_nnlo_30_ggH125_ZZ4l.exactly4lep.root
    ODEO_FEB2025_v0_exactly4lep_mc_700600.Sh_2212_llll.exactly4lep.root
    dataset_receipt.json
```

执行决定：按用户后续要求，所有本地 ROOT 保留官网原始文件名；目录已同步官网原名，精确输入证据见 [下载验证记录](init-data-verification.md)。目录只是第一层隔离；将错误 ROOT 放入正确目录必须被内容校验拒绝。

拟议下载命令从仓库根执行：

```powershell
python scripts/init_data.py
python scripts/init_data.py --dataset atlas2020_4lep
python scripts/init_data.py --dataset atlas2025_exactly4lep
```

无 `--dataset` 表示两套都下载，指定时只处理对应完整配对。下载器可保留 `--force` 的重新下载语义，但只能发布通过同一受控哈希的新文件，不能将其解释为允许切换版本或忽略校验。日常下载器不自动迁移旧平铺文件。用户另行授权的一次性旧 MC 移动已由下载任务完成并记录。

下载顺序：加载受控定义 → 检查目标与锁 → 使用直接 HTTP/HTTPS 下载到独占临时文件 → 校验大小和 SHA-256 → 原子发布文件 → 两个成员均成功后原子发布配对 receipt。使用有限超时及有界重试；重试只处理临时文件。并发初始化不能共享固定 `.part` 并互相删除；目标目录及成员拒绝链接/reparse point、路径穿越。

已有文件必须重新通过校验才跳过。中断时可以留下已校验的单个成员，但不发布完整 receipt；下一次补齐，预处理始终拒绝不完整配对。receipt 不是科学授权或哈希真值，预处理还必须自行对照受控定义验证文件。

继续使用 `urllib.request` 直接请求 CERN；不使用 webservice 工具或外部模型。需要解析记录时，按 release、collection、DSID、精确 file key 匹配，唯一性不满足即失败。仅凭 DSID+大小、首个匹配项或服务器 Content-Length 不足以确定配对。

执行更新：精确 URL/file key、字节数、SHA-256 与归一化已直接向官方来源核实，见下载验证记录和 dataset-v2-verification.md。四个文件分别绑定独立摘要。

## 5. CLI 与路径契约

预处理、训练、test 三个命令的 `--dataset` 都必填且只接受第 1 节两个名称。保留 `--protocol`、`--run-dir`、现有进度参数，以及各阶段上游 run 参数。

新预处理 run config 示例：

```yaml
schema_version: "2.0"
data_root: ../../data/raw
resources:
  chunk_size_events: 50000
```

相对 `data_root` 统一相对于 run config 文件所在目录解析；该示例放在 `neural/config/` 时指向仓库 `data/raw`。最终输入路径只能由 `data_root / dataset / registered_filename` 构造。移除 `samples.higgs.path`、`samples.zz.path`，不提供任意 URL/profile/DSID 的命令行覆盖。

以下为已实现接口的运行命令，从 `neural/` 执行。每次执行须使用全新 run 名称：

```powershell
conda run -n pytorch higgsml-preprocess --dataset atlas2020_4lep --protocol config/preprocess_protocol_v2.yaml --run-config config/preprocess_run.example.yaml --run-dir runs/atlas2020_4lep/preprocess-001
conda run -n pytorch higgsml-train --dataset atlas2020_4lep --input-run runs/atlas2020_4lep/preprocess-001 --protocol config/adversarial_mlp_protocol_normal_v2.yaml --run-dir runs/atlas2020_4lep/development-001
conda run -n pytorch higgsml-test --dataset atlas2020_4lep --train-run runs/atlas2020_4lep/development-001 --run-dir runs/atlas2020_4lep/test-001
```

2025 使用相同三个命令，将所有 `atlas2020_4lep` 一致替换为 `atlas2025_exactly4lep`。test 示例仅说明接口，实际开启仍须满足项目授权边界及 eligible 冻结 run 条件。保留当前可选 `--authorization-reference` 行为：提供时启用持久化一次性 claim；省略时允许不同新输出目录的重复评价。数据集参数不会授予 test 权限。

三阶段的校验顺序为：参数白名单 → 路径与绑定 → 上游协议/产物验证 → 科学计算或 test claim。`--dataset A` 配上 B 的 preprocess/development run、同名但不同定义哈希、旧无身份 manifest，均在读取事件特征前拒绝。训练/test 不重新下载原始 ROOT，也不要求联网。

业务退出码延续 `neural/AGENTS.md`：缺参/未知名为 2；数据/schema/哈希/配对不符为 3；run 事务失败为 4；资格/test-opening 拒绝为 5；意外错误为 70。下载器目前失败码为 1，本轮保留并在文档中与业务命令区分。

## 6. Profile、物理处理和归一化

### 6.1 Profile 适配

branch 映射按 `open_data_2020`、`release22` 组织，与 Higgs/ZZ 标签无关。2020 两个成员使用已验证的 2020 profile；2025 两个成员使用已验证的 release22 profile。实际 tree/branch/dtype/单位必须逐文件核实，不能凭年份强行套用。

单位转换仅发生一次。对 `lep_E/lep_e`、MeV/GeV、隔离量与 pT 同单位、d0 significance 无量纲、z0 单位、触发匹配和 Tight-ID 含义建立测试及来源说明。变量映射到同名 canonical 字段，只证明接口统一，不能证明两种 release 的物理定义等价。某一必需量不可等价获得时，停止该配对发布，不填默认值、假布尔值或静默换定义。

selection、SFOS 配对、Z1/Z2、四动量和 Angular5 的数学实现原则上复用。上游 `4lep` 至少四个预选轻子、`exactly4lep` 恰好四个预选轻子的区别保留在输入定义；项目仍执行自己的恰好四个 good leptons 与全部后续切选。

### 6.2 归一化

保留带符号物理权重与非负优化权重的职责分离。标准展开式为：

```text
physical_weight = L_pb × sigma_pb × k_factor × filter_efficiency
                  / sum_weights_generated × mcWeight
```

若官方截面已是有效截面，则显式使用 `effective_xsec_pb` 模式，公式为 `L_pb × effective_xsec_pb / sum_weights_generated × mcWeight`，不能再乘过滤效率/k-factor。两种模式互斥；不能根据数值“看起来合理”自动猜测。sum of weights 必须对应同一生成样本和官方归一化范围，不能用 collection 选后条数或当前文件内权重和替代。

对 2020 Higgs 新增独立官方归一化；不能从 ZZ 复制常量。2025 的 700600 同样独立验证 event normalization 字段及其稳定性。报告记录每个参数的值、单位、来源和最终采用的有效截面。

一个需要保留透明度的现状：pipeline 的 `train_weight` 是对每类全部选后事件的绝对物理权重除以均值，因此均值涵盖 test 权重；当前 fold 直接使用该列。此次保持这一冻结权重定义，不悄悄改成 fold-local 权重归一化。它不读取 test 特征，但也不能宣称“所有训练相关统计均独立于 test 权重”。若要进一步要求权重统计也严格 development-only，应另立科学协议变更及对照验证，不能夹带在目录重构中。

## 7. 文件行身份与物理事件身份

必须分开两个用途：

| 身份 | 建议字段 | 用途 |
|---|---|---|
| 来源行身份 | `(dataset_definition_sha256, source_file_id, source_entry)`；sample/DSID 另有绑定 | canonical 唯一性、预测回连、审计；换 collection 时允许改变 |
| 物理分组身份 | 受控 `event_group_id`，由已核实的生产样本身份与 event 标识确定 | split 和 fold；重叠物理事件必须同组 |

本轮优先保留现有 split 的 `channelNumber:eventNumber` 字节编码及 BLAKE2b 桶规则。相同 DSID/eventNumber 的重复记录保守地视为同一防泄漏组，即使属于碰撞也不能拆入不同 fold；不同来源行仍各自保留审计身份。不加 dataset 名称、collection、文件哈希或 source entry 到 split/fold 的分组键。

对已证实使用同一生成事件编号的 collection，直接共用上述组键。跨 release 不自动认定相同 DSID 就是同一事件；实施前只读取 MC 身份字段核实编号/production 关系。若发现同一物理事件改了标识，需要版本化 crosswalk 把它们映射到同一组；无法证实对应关系时不得宣称跨 release 的 test 隔离已证明，也不得进行跨数据集联合训练或共享候选选择。

新版 fold 对同一 `event_group_id` 的 UTF-8 字节执行 SHA-256，取前 8 字节大端整数 `% 5`。固定字符串编码、分隔符和策略 ID；每个分组只能出现于一个 split 和一个 fold，全部 λ 复用该 fold 分配。更换 fold 身份是明确的协议版本变化，不能声称新 OOF 与历史 OOF 数值等价。

新增 `source_file_id`、`event_group_id` 到 canonical schema，并更新 forbidden-feature 白名单、dtype、序列化和预测身份字段。`build_validated_fold` 除检查行身份交集，还需检查拟合/验证物理分组交集。不得简单把重复物理标识当作文件重复删除；保留或去重需要有预声明的来源解释。

本轮两套数据独立运行，不能把它们的 OOF 简单合并。已开启某配对的 test 结果不得反馈到另一套重叠事件的开发或方案选择；身份审计不能替代这条研究边界。

## 8. 预处理产物与 development/test 隔离

建议在本轮 v2 中将单表改为两个互斥物理分区，减少 reader 复杂度，并使 development 真正无需打开 test 事件文件：

```text
runs/<dataset>/preprocess-001/
  config.yaml                         # 精确协议与数据定义快照/摘要
  processed/development_events.csv.gz  # train + validation，保留 split 列
  processed/test_events.csv.gz         # 仅 test
  artifacts/cutflow.json
  artifacts/mc_summary.json
  artifacts/manifest.json
```

保留 deterministic gzip、列序、浮点格式和来源行稳定排序。两分区各有文件 SHA-256、canonical SHA-256、大小、行数；全体身份唯一，分组不跨分区。预处理是一次按冻结规则生成所有 MC 分区的受信阶段，可以计算 test 特征；此权限不延伸至 development 分析。

development 读取 manifest 和自己的分区，只验证/解码 development 文件；test 分区哈希在此阶段只是上游冻结 receipt 中的预期值，不能宣称已重算验证。必须替换当前 `_output_records` 对所有输出统一开文件哈希的逻辑，不能换了文件名却仍读 test 分区。test-opening gate 检查资格与身份后，按现有 claim 语义验证和读取 test 分区；失败按现有终态处理，不悄悄重试一次性开窗。

manifest 的通用 `dataset_binding` 至少包含名称、修订、定义 SHA-256、release、collection、成员 DSID/file ID/hash、profile 哈希、split/fold 身份策略。各阶段附加自己的协议和输入 manifest 摘要。

绑定须传递到 development manifest、最终模型/checkpoint、scaler、OOF 记录的归属 manifest、test manifest 与 failure/claim receipt。模型与阈值属于唯一 development lineage；即使 15 项特征完全相同，也不能把 A 模型配到 B 的 test 表。

不一定要在每一行重复长哈希，但独立导出的表必须附带绑定 receipt；表内 source file ID 能唯一回连所属数据集。所有新增列明确禁止进入分类器。

## 9. 全处理链改动与优化清单

下表路径除明确标记“根”外，均相对于 `neural/`。

| 模块/处理 | 本轮动作 | 保留或验证要点 |
|---|---|---|
| 根 `scripts/init_data.py` | 重构 | 受控配对、四文件、子目录、HTTP 校验与完整 receipt；不再生成旧平铺混用输入 |
| 新 `src/data_contract.py`、数据定义/profile 资源 | 新增 | 单一数据身份来源；标准库加载；精确快照与 schema 验证 |
| `src/config.py` | 重构 | 去除标签驱动映射和固定混用 expected_samples；新 run config 禁止任意两路径 |
| `src/cli/preprocess.py`、`train.py`、`test.py` | 适配 | 必填参数透传；结果标题含数据集；错配在计算/claim 前拒绝 |
| `src/preprocessing/root_reader.py` | 适配 | 预检 tree、num_entries、branch/type；生成 file ID；保留 chunk 迭代 |
| `src/preprocessing/pipeline.py` | 重构 | 数据绑定、逐事件 DSID 检查、归一化模式、身份分组、分区输出 |
| `src/domain/selection.py`、`four_vectors.py`、`reconstruction.py`、`features.py`、`angular5.py` | 复用并扩展验证 | 数学和切选不变；双 profile 的单位、边界及退化情况验证 |
| `src/domain/weights.py` | 适配参数契约 | 明确有效截面模式，保留 signed/abs 和现有归一化范围；负权重、零/无效归一化测试 |
| `src/domain/splitting.py`、`src/training/folds.py` | 身份契约升级 | 既有 split 桶优先保留；fold 使用事件组，版本化记录变化 |
| `src/preprocessing/outputs.py` | 适配 | 新列、分区和 deterministic 排序，拒绝 enum/身份异常 |
| `src/preprocessing/authority.py` | 重构 | 按数据集查证据；历史 golden 不作为新配对 gate；区分 development 验证与授权全量验证 |
| `src/training/development_reader.py` | 重构 | 新 schema/绑定；只打开 development 分区；拒绝旧单表输入 |
| `src/training/dataset.py` | 适配 | 从 binding 验证 sample-label-DSID；分组交集校验；15 维 scaler/tensor 保持 |
| `src/training/config.py`、normal/debug YAML | 新版协议 | 新输入列/fold/schema；normal 门槛保持，debug 仅原有两项例外 |
| `src/training/development.py` | 适配 | 数据身份贯穿 OOF、final fit、manifest；每套独立资格判断 |
| `src/training/trainer.py` | 适配载荷 | checkpoint/final 模型增加绑定；优化器、早停、随机种子和网络不变 |
| `src/training/network.py`、`losses.py` | 原则上不改算法 | 核查接口变化；对低背景/空有效 bin 运行既有语义测试，不自行降门槛 |
| `src/training/qualification.py` | 适配身份及报告 | OOF 完整性用新来源身份；AUC/KS/效率/λ tie rule 不变 |
| `src/training/test_reader.py` | 重构 | 删除固定样本表；接收冻结 binding，仅解码 test 分区 |
| `src/training/test_opening.py` | 适配全部严格 schema | 逐级比对 lineage、模型、scaler、阈值及 dataset；保留可选 claim 生命周期 |
| `src/artifacts/manifest.py`、`plots.py` | 适配 | 数据集标注、有效样本量与证据范围；图不把跨配对差异归因于网络 |
| `src/artifacts/transaction.py` | 原则上复用 | 验证 `runs/<dataset>/<run>` 嵌套路径和父目录创建；保留不可覆盖与链接拒绝 |
| `src/logging_config.py` | 少量适配或复用 | 阶段日志增加名称/摘要，不输出事件特征 |
| `pyproject.toml`、环境文件 | 资源打包检查 | 三个 console entry point 不增减；优先不新增依赖，不改权威环境锁 |
| `tests/unit`、`tests/integration`、`tests/golden` 与 fixtures | 更新/补充 | 两套参数化 fixture、新 schema/错配拒绝、身份和 test 文件访问哨兵 |
| 根 README、`neural/README.md`、`docs/engineering/runbook.md`、协议和 artifact 文档 | 更新当前运行指南 | 全部当前命令与目录改为数据集选择；历史报告保留历史事实及明确链接 |
| `neural/AGENTS.md`、根设计文档相关契约 | 实施时同步修订适用版本说明 | 不放松 MC-only、冻结 run、特征与资格边界；旧数值要求标注 v1 历史范围 |

性能优化采用有限范围：复用 ROOT 分块读取；尽早检查 schema/DSID；分区降低 development I/O；统计 wall time/峰值内存。pipeline 当前仍会累计所有选后行及 CSV bytes，先测实际峰值；只有构成瓶颈才改稳定分块写出。不要在同一轮引入并行重建、float32 物理计算、近似算法或更换存储引擎。

新增 development-only 统计报告：每类/每 fold 的事件数、负权重比例、`sum(abs(w))`、`sum(w²)`、`N_eff=(sum(abs(w)))²/sum(w²)`，以及背景质量 bin 的有效统计。零分母显式报告无效。2025 背景原始仅 11,260 行，不能保证其通过资格；统计不足也不允许降低 Normal 门槛。旧 ZZ 前级约 38.24%、质量窗相对保留约 5.65% 只是排查线索，不据此修改切选。

## 10. 历史实现退出与迁移

这是新运行接口的破坏性升级，不保留 mixed 数据集名称、旧参数默认值、两条任意路径或“遇到旧 manifest 就推断数据集”的运行兼容层。

1. 保留旧 v1 protocol 原字节、Git 历史、历史报告和所有冻结/失败 runs；旧平铺 ROOT 按用户后续授权移动并保留原始字节；不重写其 manifest，不补 dataset 字段，不覆盖 `preprocess-01`。
2. 新入口拒绝旧配置和旧产物，提示按新数据集重新预处理。旧程序复现只能使用历史 Git revision 与历史环境，不在新运行链留混用分支。
3. 历史 comparator/测试证据保留为历史资料或历史 revision；新 `authority.py` 不通过 v1 默认回退处理混用。允许保留纯数学 fixture 作为回归参照。
4. 新数据在新目录生成，两个配对各自新建 preprocess/development/test run。没有旧表改名或拼接迁移步骤。
5. 新 schema 升版本，所有 exact-key validator 同步更新；旧模型不能通过“补一个 dataset 参数”转换成新模型。
6. 回滚通过切回旧代码/环境完成，不删除新旧证据，不触碰冻结目录。旧 test claim 状态不能通过回滚清除。

## 11. 验证与实施阶段

| 阶段 | 工作 | 完成条件 |
|---|---|---|
| A：绑定核实 | 用直接 HTTPS 核实四个 MC 文件、归一化与 profile；身份字段审计；形成受控定义 | 无缺失哈希/精确大小/来源；跨 collection 身份结论有范围说明；尚未分析 test 特征 |
| B：输入隔离 | 实现共享加载器、下载子目录、完整 receipt、新 CLI/config | 从空目录下载/模拟下载两套；错配、损坏、半完成、并发与未知名称均正确处理 |
| C：预处理 v2 | 双 profile、权重模式、物理分组、分区、manifest | 两套 micro-ROOT 全链；改变 chunk 不改变 canonical 内容；旧配置被拒绝 |
| D：development/test 契约 | reader、fold、模型、scaler、OOF、claim lineage 全链适配 | dataset 错配在特征读取前失败；开发不打开 test 文件；正常/无资格/异常三种终态有证据 |
| E：科学与全量验证 | 锁定 ARM64 上分别生成新配对的预处理证据，运行预声明 development | 不把新输出自比自认定为 golden；不以旧混用计数验收；test 另按资格和授权执行 |
| F：切换文档和退出旧入口 | 当前文档、资源打包、错误信息与历史归档说明 | 新安装按文档可重建两套输入链；无可运行混用回退；冻结 runs 无变化 |

必须覆盖的测试：

- 2020 Higgs 不再被要求是 release22；2025 ZZ 不再被要求是 363490；交换两个文件、跨版本拼接、伪造同名目录和同名定义不同哈希全部拒绝。
- 下载少一个文件不产生完整配对；错误大小/哈希、记录匹配零项或多项、HTTP 中断、已有完整文件跳过及 `--force` 保持内容校验。
- 两个 profile 分别覆盖 energy、isolation、d0/z0、触发/Tight-ID、array 长度和单位；合成物理等价输入产生一致 canonical 运动学，但测试不被描述为真实跨 profile 等价性证明。
- 同一事件换 source entry、文件或 collection，split/fold 保持；物理分组不跨拟合/验证；同 DSID/eventNumber 碰撞采用保守同组；未知 crosswalk 不被默认“证明”。
- 更改 test 分区特征内容不会改变 development 输出或使 development 打开该文件；使用文件访问哨兵验证。到实际 test 阶段，篡改内容应因哈希不符被拒绝。
- A 的模型/阈值/scaler 配 B 的 lineage、旧 schema、篡改摘要、错误 sample-label-DSID 全部失败；非 eligible 不能进入 test；有引用一次性及无引用新目录重复模式均保持原行为。
- 15 项模型输入维度、forbidden fields、fold-local scaler、GRL/损失和 Normal 资格规则不回归；小型确定性训练重复结果一致。
- 新来源身份下 OOF 每行每 λ 恰有一次预测，test 预测完整；所有产物身份一致，嵌套 run 事务、失败 receipt 和不可覆盖性通过。

实现时先跑相关单测/集成测试，再从 `neural/` 执行：

```powershell
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
```

新全量基准的建立需要独立证据：官方元数据对照、手算/合成 fixture、选择逐级账目、确定性复跑、明确平台与哈希。不能将第一次新输出直接作为自己通过的 golden。旧 authority comparator 的全表 pandas 读取不得作为普通 development 分析捷径；未获相应 test 权限时只做 development 特征比较及非特征结构检查，完整 test 特征等价性标记为未执行。

## 12. 本方案的验收界限与待核实项

方案完成后，实现工作的最终验收标准是：四个正确 MC 文件分两目录保存；三个命令均强制选择数据集；错配不能通过；每个产物和模型可追溯到同一受控定义；开发不打开 test 分区；物理重叠的分组规则有证据；两套各自有新验证记录；旧混用不再可由新入口运行；冻结 runs 和 `xgboost` 未修改。

执行更新：四个文件的精确元数据、哈希、tree/branch 和归一化已核实，见输入证据和下载验证记录。真实跨 profile 物理等价及跨 release 生产事件映射仍未证明。任一缺失不能用 placeholder 发布可运行定义。可先完成 loader、synthetic fixture 和接口测试，不能据此宣称全数据已验证。

实施结果、软件回归和科学验证的未完成项以 [dataset-v2-verification.md](dataset-v2-verification.md) 为准。“41 项相关测试通过”为重构前历史记录。新运行指南见 [dataset-v2-runbook.md](dataset-v2-runbook.md)。
