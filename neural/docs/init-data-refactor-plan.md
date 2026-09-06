# init_data.py 数据集下载重构 Plan

状态：下载器已实施，验证记录见 [init-data-verification.md](init-data-verification.md)。日期：2026-09-05。

实施时用户追加要求覆盖下文原拟议约定：本地文件名保留官网原始 file key；已有平铺 MC 文件校验后一次性移动到对应新目录，不重复下载。下载器日常运行仍不做旧路径回退或自动迁移。

本计划从 [Neural 数据集隔离总方案](dataset-isolation-refactor-plan.md) 抽取，独立定义 `scripts/init_data.py` 的修改范围、步骤和验收标准。本文所有路径均相对于仓库根 `D:\code\HiggsML`。本文保留原计划范围；实际改动及验证以下载验证记录为准。

## 1. 目标与范围

将当前“2025 Higgs + 2020 ZZ”的平铺下载实现替换为两套同版本、同 collection 的完整 MC 配对，并分别存入以数据集名称命名的子目录。

| 数据集名称 | Collection | Higgs DSID / 输入事件数 | ZZ DSID / 输入事件数 | 约计大小 Higgs / ZZ |
|---|---|---|---|---|
| `atlas2020_4lep` | 2020 `4lep` | 345060 / 164,716 | 363490 / 554,279 | 50.52 / 179.08 MB |
| `atlas2025_exactly4lep` | 2025 `exactly4lep` | 345060 / 419,943 | 700600 / 11,260 | 182.05 / 5.41 MB |

表中数据来自总方案及任务上下文，尚未在本次重新联网核实。事件数为输入数量，展示大小不能用作精确字节校验。

本计划包含下载器、其必要的数据定义加载模块、测试和下载说明。预处理、训练、test CLI、物理选择、归一化计算、fold、模型与 run schema 的修改仍归总方案，不是本计划的完成条件。仅 MC；不读取、下载或检查 real data，不修改冻结/失败 run 或 `xgboost` 实现。

2025 `4lep` 不纳入白名单，也不与 `exactly4lep` 合并。不保留跨版本配对选项。

## 2. 当前实现与修改点

| 当前符号 | 当前行为 | 拟议修改 |
|---|---|---|
| `Dataset`、`DATASETS` | 单文件描述，固定新版 Higgs 和旧 ZZ | 改为受控配对及成员文件描述；不再用两项混用常量驱动下载 |
| `resolve_higgs_download_url()` | 在固定 Higgs record 中按 DSID 和大小找文件 | 改为通用文件 URL 解析；绑定 record、release、collection、精确 file key 与 DSID |
| `verify_file()`、`sha256_file()` | 校验大小与 SHA-256 | 复用核心逻辑，参数改为受控成员定义；已有文件也必须验证 |
| `download()` | 固定 `.part` 路径，下载前删除同名临时文件 | 使用本次调用独占的临时路径、有限重试和校验后原子发布；禁止删除其他调用的临时文件 |
| `initialize()` | 所有文件写到 `data/raw/` | 按数据集逐套处理，成员齐全后发布配对 receipt |
| `parse_args()` | 仅 `--force` | 增加可选 `--dataset`，无参数处理两套；保留 `--force` |
| `main()` | 按脚本位置定位仓库，成功后打印统一结果 | 保留 cwd 独立定位，输出每套配对结果；任一目标配对失败则非零退出 |

## 3. CLI 与目录契约

拟议命令从仓库根执行：

```powershell
python scripts/init_data.py
python scripts/init_data.py --dataset atlas2020_4lep
python scripts/init_data.py --dataset atlas2025_exactly4lep
python scripts/init_data.py --dataset atlas2020_4lep --force
```

| 参数 | 行为 |
|---|---|
| 不指定 `--dataset` | 按固定顺序初始化两套配对，总计四个 MC 文件 |
| `--dataset <name>` | 只初始化该名称的两个配套文件；只接受上述两个精确名称 |
| `--force` | 重新下载目标文件，仍必须通过同一受控大小/哈希校验；不允许忽略校验或切换版本 |

不增加 `--dataset-pair` 别名、任意 URL/DSID 覆盖或旧 mixed 名称。成功退出 0；下载、文件或绑定失败退出 1；参数错误由 argparse 退出 2。

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

本地名称按用户追加要求保留官网原始 file key，定义和 receipt 同步记录。路径始终由脚本定位的仓库根和受控名称构造，不依赖当前工作目录。已有 `data/raw/higgs.root`、`data/raw/zz_363490.root` 按用户追加要求经大小/哈希验证后一次性移动并改为官网原名；下载器日常不自动迁移、链接或用作旧路径回退。

## 4. 受控数据定义

沿用总方案确定的单一数据定义来源：

```text
neural/config/datasets/atlas2020_4lep.json
neural/config/datasets/atlas2025_exactly4lep.json
neural/src/data_contract.py
```

本阶段实现该模块中标准库可用的下载定义加载与校验部分；后续 neural 再组合 profile 和科学协议。根脚本按自身位置加载模块，不能依赖环境中其他工程的 `src` 包，也不要求安装 PyTorch、uproot 或 YAML 库。

下载所需的最小契约包含：

- 数据集：schema 版本、名称、定义修订、release、collection、`mc_only: true`、两个固定成员。
- 成员：role、label、DSID、稳定 file ID、上游 record URL、精确 file key、下载 URL、本地文件名、精确字节数、SHA-256、预期 tree/entry count。
- 绑定：定义原始字节的 SHA-256，并由随代码发布的名称/修订/摘要白名单验证；不接受运行时任意清单路径。

拒绝未知字段、重复 JSON key、非法名称/路径、重复 file ID/哈希、错误成员数量、错误 DSID 配对、非 MC 标记，以及 release/collection 不一致。不能仅因为目录名称正确就认定文件身份正确。

归一化和 profile 的科学验证继续由总方案负责。若本阶段只发布下载契约，必须使用明确的下载 schema，后续扩充升修订；不能填入假的科学参数，也不能把下载 receipt 宣称为可训练数据集资格。

实施前通过直接 HTTP/HTTPS 核实四个文件的官方来源、精确大小、file key 和摘要。2020 Higgs、2025 ZZ 的缺失元数据不得猜测；现有 2025 Higgs/2020 ZZ 的哈希不能复用于其他文件。若官方没有 SHA-256，独立核实官方身份及其提供的 checksum，再计算、记录并受控固定 SHA-256；运行时下载器不得把本次观测哈希自动作为期望值。

预期 tree/entry count 是来源元数据；标准库下载器不解码 ROOT 验证它们。实际 ROOT schema 和条数核验归后续预处理，receipt 要明确本阶段只验证文件字节。

## 5. 下载、并发和发布流程

每套配对按以下顺序处理：

1. 加载并校验受控定义，在网络访问前拒绝非法配对与路径。
2. 检查数据集目录和成员路径，拒绝路径穿越、symlink、junction/reparse point 及非普通文件目标；取得该数据集的独占锁。
3. 对已有成员检查大小和 SHA-256。有效且无 `--force` 时跳过；无效且无 `--force` 时失败，提示显式重下载，不自动覆盖。
4. 使用 `urllib.request` 直接 HTTP/HTTPS 请求，下载到本次调用独占临时文件。保留分块 I/O 与进度显示，设置有限连接/读取超时及有界重试；重试从新的或已清空的本次临时文件开始，不假定支持断点续传。
5. 校验临时文件大小和 SHA-256；通过后原子替换目标。失败只清理本次拥有的临时文件，保留原有目标文件。
6. 两个成员均通过最终校验后，原子发布 `dataset_receipt.json`，再释放锁。无变更且 receipt 已有效时可直接保留，避免重复调用制造无意义变化。

锁冲突应明确失败或有界等待；不得绕过有效锁。崩溃遗留锁需明确恢复说明，不盲目删除无法确认所有权的锁。两套数据集可分别完成；默认全量模式中一套失败时，已成功配对保留，但总命令不能报告全部成功。

URL 优先使用受控精确地址；确需解析官方记录时按精确 file key 等完整身份唯一匹配。零项、多项或元数据变化均失败。DSID+大小、首个匹配项、Content-Length 均不能单独作为身份依据。HTTP 状态错误、截断响应和错误内容必须失败；不使用 webservice 工具。

配对 receipt 至少记录 schema、数据集名称/修订、定义 SHA-256、release、collection、MC 标记、两个成员的 file ID/DSID、本地文件名、来源 URL/file key、期望与实际大小/哈希、验证时间和下载器版本。只有两个成员均有效才有 `status: complete`。

首次下载中断可留下已验证的单个文件，但不发布 complete receipt；下次补齐即可。若重试前发现旧 receipt 与当前成员不符，先使该 receipt 不再作为当前 complete 标记，再处理修复。`--force` 对仍完整且同哈希的已有配对重下载失败时，可保留原有效文件和 receipt，同时命令返回失败。receipt 永远不能替代使用方对实际成员重新校验。

## 6. 文件改动清单

| 文件 | 动作 |
|---|---|
| `scripts/init_data.py` | 配对驱动下载、参数、目录、锁/临时文件、receipt、错误处理 |
| `neural/src/data_contract.py` | 新增标准库下载契约加载与校验；为后续 neural 共享预留明确接口 |
| `neural/config/datasets/*.json` | 新增两套受控下载定义，固定官方文件身份 |
| `neural/tests/unit/test_init_data.py` | 新增下载器参数、校验、失败恢复和发布测试 |
| `neural/tests/unit/test_data_contract.py` | 新增受控定义和非法配对拒绝测试 |
| 根 `README.md` 下载章节 | 更新命令、四文件配对表、目录、重试与退出码说明 |

标准库模块加载测试需确认不会意外导入训练依赖。普通单测使用临时目录、mock HTTP 和微小字节 fixture，不访问 CERN、不写真实 `data/`。不为完成该独立计划而修改预处理/训练/test 入口。

## 7. 实施步骤与验证

| 步骤 | 交付 | 验收 |
|---|---|---|
| 1 | 四文件官方来源证据、两套受控定义、最小加载器 | 元数据齐全，schema/摘要/配对拒绝测试通过 |
| 2 | 新 CLI 与目标路径生成 | 默认两套、指定一套、未知名称、不同 cwd 测试通过 |
| 3 | 下载和发布事务 | 大小/哈希校验、并发锁、临时文件隔离、失败保留旧文件测试通过 |
| 4 | 配对 receipt 与重复执行 | 缺成员不 complete；已完整可跳过；损坏/强制下载/中断恢复正确 |
| 5 | 文档与验证证据 | 下载说明准确，目标测试与全套检查通过；实际下载与否明确报告 |

必须覆盖的失败案例包括：2025 Higgs 搭配 2020 ZZ、同 DSID 错 collection、成员互换、错误哈希/大小、目录伪装、记录解析零项/多项、HTTP 失败/截断、半套完成、旧 receipt 失效、两个调用冲突及其他调用临时文件不被删除。

实现后从 `neural/` 执行，先聚焦测试，再完整验证：

```powershell
conda run -n pytorch python -m pytest -q tests/unit/test_init_data.py tests/unit/test_data_contract.py
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
```

只有实际通过直接 HTTPS 下载、对照受控定义验证四个文件并检查两套 receipt 后，才可声明真实下载验收完成。mock 测试不替代此项；下载成功也不代表 ROOT schema、物理归一化、预处理或训练通过。

## 8. 完成标准与下游交接

完成本计划后，下载器能按两种名称生成完整、可重复验证的原始 MC 配对；不再创建旧混用平铺输入；所有新成员及 receipt 可追溯到受控定义。除用户授权的一次性旧 MC 路径迁移外，冻结 runs 和 `xgboost` 保持原状。

交接给总方案的接口为：数据集名称、定义文件及摘要、固定目录、成员文件身份和 receipt schema。后续预处理须自行验证它们，并完成 ROOT/profile/归一化检查。本计划可以先实施，但在下游适配完成前，不将新文件接入旧混用协议，也不把下载器完成描述为全链重构完成。
