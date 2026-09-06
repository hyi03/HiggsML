# MC 下载契约验证记录

日期：2026-09-05。仅 MC，educational/technical demo。

## 官方身份与摘要

直接通过 HTTPS 读取 CERN 官方记录，筛选指定 MC 成员。以下 file key、精确 bytes 和 Adler-32 均来自官方 `metadata.files`：

- https://opendata.cern.ch/api/records/15005：2020 at least four leptons collection。
- https://opendata.cern.ch/api/records/atlas-93928：FEB2025 exactly4lep MC beta release。

官方没有提供 SHA-256。本次直接 HTTPS 下载四个 MC 文件，先核对官方大小与 Adler-32，再计算并在代码清单中固定 SHA-256；不是用运行时观测值自动批准下载。没有读取或下载 real-data 文件。

| 数据集 / DSID | bytes | 官方 Adler-32 | 本次 SHA-256 |
|---|---:|---|---|
| atlas2020_4lep / 345060 | 50518236 | `adler32:1ea0e560` | `a7560ac94f2db7adf27ea1cecfd685e7f8c0b82ab2e7d7516411d1c7a621cab6` |
| atlas2020_4lep / 363490 | 179082866 | `adler32:6298e6cb` | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |
| atlas2025_exactly4lep / 345060 | 182051943 | `adler32:c675b786` | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| atlas2025_exactly4lep / 700600 | 5407367 | `adler32:1a80cedf` | `3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789` |

精确 file key 与 HTTPS 下载地址：

- [mc_345060.ggH125_ZZ4lep.4lep.root](https://opendata.cern.ch/record/15005/files/mc_345060.ggH125_ZZ4lep.4lep.root)
- [mc_363490.llll.4lep.root](https://opendata.cern.ch/record/15005/files/mc_363490.llll.4lep.root)
- [ODEO_FEB2025_v0_exactly4lep_mc_345060.PowhegPythia8EvtGen_NNLOPS_nnlo_30_ggH125_ZZ4l.exactly4lep.root](https://opendata.cern.ch/record/atlas-93928/files/ODEO_FEB2025_v0_exactly4lep_mc_345060.PowhegPythia8EvtGen_NNLOPS_nnlo_30_ggH125_ZZ4l.exactly4lep.root)
- [ODEO_FEB2025_v0_exactly4lep_mc_700600.Sh_2212_llll.exactly4lep.root](https://opendata.cern.ch/record/atlas-93928/files/ODEO_FEB2025_v0_exactly4lep_mc_700600.Sh_2212_llll.exactly4lep.root)

## 定义绑定与下游接口

schema 为 `higgsml.download-definition.v1`，两套定义修订均为 1。定义原始 UTF-8 字节摘要如下：

- `atlas2020_4lep`：`6bbce80f1e47495ea880fc5af33952d9c8b5c82c12c73f447a1a14188d658a86`
- `atlas2025_exactly4lep`：`0d8bdf64b78b5055ba1a7156b658086fcd9089efffc88c9ef97a325f2017786d`

`src.data_contract.load_dataset(name)` 返回 frozen `DatasetBinding`，含 dataset_name、definition_revision、definition_sha256、release、collection、mc_only 和 `tuple[Member, ...]`。成员 filename 等于官网 file_key；数据位于 `data/raw/<dataset>/<filename>`。receipt schema 为 `higgsml.download-receipt.v1`，validation_scope 固定为 `file_bytes_only`。下游组合科学契约时应再次验证定义与文件，不以 receipt 代替实际校验。

下载器仅使用受控精确 URL，已删除旧的记录动态解析路径。因此不存在零项/多项匹配或 DSID+大小启发式选文件；官方响应内容变化由固定大小/SHA-256 拒绝。

## 本地迁移与实际验收

用户追加要求优先于原计划：复用并移动旧 MC 文件，保留官网文件名。`higgs.root` 校验后移动为 2025 Higgs，`zz_363490.root` 校验后移动为 2020 ZZ；另外两份使用本次已通过官方 checksum 的下载文件。元数据核实阶段的四文件下载在用户提出复用要求前已启动，完成文件均未再次下载。

在 Conda pytorch 中仅打开这四个 MC 文件的 ROOT 元数据，确认 2020 tree `mini` 的 entries 为 164716 / 554279，2025 tree `analysis` 为 419943 / 11260。没有解码事件特征，也未执行物理选择、归一化、预处理或训练；此独立核查不使标准库下载器具备 ROOT 校验功能。

运行 `python scripts/init_data.py`：退出 0，四个文件均重新验证大小/SHA-256 后跳过下载，两套 complete receipt 成功发布。其后核对实际文件和 receipt，并验证重复调用保留 receipt 字节。

## 自动化验证

- Windows，`conda run -n pytorch python -m pytest -q tests/unit/test_init_data.py tests/unit/test_data_contract.py`：81 passed。
- `conda run -n pytorch python -m pip check`：No broken requirements found。
- 共享工作区完整 pytest：59 failed、273 passed、1 warning（171.71s）。同期另一任务正在实施下游全链重构，主要失败为旧测试未提供新必填 dataset、旧 CLI 参数/帮助断言未同步。失败已交接该任务；不能声明共享工作区全套通过。
- HEAD 加本次下载改动的独立快照完整 pytest：333 passed、1 skipped、2 failed、1 warning（196.23s）。其一为 HEAD 原有 `test_train_help_has_no_removed_subcommands`：断言帮助文本不含 `develop`，但 description 含 `development-only`。另一项 foreign-cwd 子进程受 editable 安装影响加载了共享工作区 CLI。
- 显式设置 `PYTHONPATH` 指向快照，重跑上述两个失败项：1 passed、1 failed（23.47s）；foreign-cwd 项通过，剩余为上述 HEAD 原有帮助文本断言。没有改动本任务范围外的 CLI 或测试；未声明全套通过。

普通测试全部使用临时目录、mock HTTP 和微小字节 fixture，不访问 CERN、不读取真实 `data/`；测试涵盖契约拒绝、角色/配对/collection、路径伪装、独占锁、其他调用临时文件、重试、截断、错误内容、原文件保留、半套恢复、receipt 失效与重跑、CLI 退出码及异地 cwd 的标准库导入。Windows 验证不替代锁定 osx-arm64 科学运行。
